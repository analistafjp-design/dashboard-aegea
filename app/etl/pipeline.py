"""Orquestração completa: arquivo -> validação -> leitura -> tratamento ->
banco -> recálculo dos indicadores -> histórico."""
from __future__ import annotations

import gc
import shutil
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import config
from app.etl.carga import ResultadoCarga, carregar
from app.etl.datasets import DATASETS, ORDEM_CARGA
from app.etl.deteccao import Identificacao, analisar_arquivo, identificar
from app.etl.leitura import estimar_linhas_xlsx, ler_em_blocos
from app.etl.transformacao import RelatorioValidacao, transformar
from app.models.tabelas import HistoricoUpload
from app.services.upload import nome_exibicao
from app.utils.erros import ErroDashboard, ErroImportacao, ErroValidacaoArquivo
from app.utils.log import get_logger

logger = get_logger("etl.pipeline")

ETAPAS = (
    "Validando arquivos",
    "Lendo planilhas",
    "Tratando dados",
    "Atualizando banco",
    "Recalculando indicadores",
    "Concluído",
)


@dataclass
class ResultadoArquivo:
    arquivo: str
    dataset: str | None = None
    titulo_dataset: str | None = None
    status: str = "ERRO"
    mensagem: str = ""
    detalhes: list[str] = field(default_factory=list)
    lidos: int = 0
    inseridos: int = 0
    atualizados: int = 0
    descartados: int = 0
    validacao: dict | None = None
    confianca_deteccao: float | None = None
    campos_detectados: list[str] = field(default_factory=list)
    qualidade_dados: float | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("SUCESSO", "ATENCAO")

    def to_dict(self) -> dict:
        return {
            "arquivo": self.arquivo, "dataset": self.dataset,
            "titulo_dataset": self.titulo_dataset, "status": self.status,
            "mensagem": self.mensagem, "detalhes": self.detalhes,
            "lidos": self.lidos, "inseridos": self.inseridos,
            "atualizados": self.atualizados, "descartados": self.descartados,
            "validacao": self.validacao,
            "confianca_deteccao": self.confianca_deteccao,
            "campos_detectados": self.campos_detectados,
            "qualidade_dados": self.qualidade_dados,
        }


def _em_blocos(caminho: Path) -> bool:
    """Arquivo grande demais para caber na memória de uma vez."""
    if caminho.suffix.lower() not in (".xlsx", ".xlsm"):
        return False
    return estimar_linhas_xlsx(caminho) > config.LIMITE_LINHAS_ARQUIVO


def _processar_em_blocos(sessao: Session, caminho: Path, dataset_forcado: str | None):
    """Lê o arquivo em pedaços e carrega cada um, mantendo a memória constante.

    O primeiro bloco decide a base e o mapa de colunas; os seguintes
    reaproveitam a mesma decisão (todos têm o mesmo cabeçalho). Cada bloco é
    gravado antes de o próximo ser lido, então o consumo de memória não
    depende do tamanho do arquivo.
    """
    identificacao_base: Identificacao | None = None
    validacao_total: RelatorioValidacao | None = None
    carga_total = ResultadoCarga()
    blocos = 0

    for planilha in ler_em_blocos(caminho):
        if identificacao_base is None:
            identificacao_base = identificar([planilha], caminho.name, dataset_forcado)
            if identificacao_base.dataset is None:
                raise ErroImportacao(
                    f"Não foi possível identificar o tipo de base do arquivo "
                    f"'{caminho.name}'. Selecione o tipo manualmente na tela de atualização.",
                    [f"Aderência máxima encontrada: {identificacao_base.pontuacao:.0%}"],
                )
            atual = identificacao_base
        else:
            atual = replace(identificacao_base, planilha=planilha)

        dados, validacao = transformar(atual)
        carga = carregar(sessao, atual.dataset, dados, caminho.name)

        carga_total.inseridos += carga.inseridos
        carga_total.atualizados += carga.atualizados
        carga_total.ignorados += carga.ignorados
        if validacao_total is None:
            validacao_total = validacao
        else:
            validacao_total.somar(validacao)
        blocos += 1

        # Libera o bloco antes de ler o próximo — é isso que mantém o
        # consumo de memória estável num arquivo de centenas de milhares
        # de linhas.
        del dados, validacao
        gc.collect()

    if identificacao_base is None or validacao_total is None:
        raise ErroValidacaoArquivo(
            f"O arquivo '{caminho.name}' não possui nenhuma planilha com dados.")

    logger.info("Arquivo %s processado em %s bloco(s): %s linhas lidas",
                caminho.name, blocos, validacao_total.linhas_lidas)
    return identificacao_base, validacao_total, carga_total


def processar_arquivo(sessao: Session, caminho: Path, dataset_forcado: str | None = None,
                      usuario: str = "local", arquivar: bool = True) -> ResultadoArquivo:
    """Processa um arquivo do início ao fim e registra o histórico."""
    resultado = ResultadoArquivo(arquivo=nome_exibicao(caminho.name))
    try:
        if _em_blocos(caminho):
            identificacao, validacao, carga = _processar_em_blocos(
                sessao, caminho, dataset_forcado)
        else:
            identificacao = analisar_arquivo(caminho, dataset_forcado)
            if identificacao.dataset is None:
                raise ErroImportacao(
                    f"Não foi possível identificar o tipo de base do arquivo "
                    f"'{caminho.name}'. Selecione o tipo manualmente na tela de atualização.",
                    [f"Aderência máxima encontrada: {identificacao.pontuacao:.0%}"],
                )
            dados, validacao = transformar(identificacao)
            carga = carregar(sessao, identificacao.dataset, dados, caminho.name)

        resultado.dataset = identificacao.dataset.nome
        resultado.titulo_dataset = identificacao.dataset.titulo
        resultado.lidos = validacao.linhas_lidas
        resultado.descartados = validacao.linhas_descartadas
        resultado.inseridos = carga.inseridos
        resultado.atualizados = carga.atualizados
        resultado.validacao = validacao.to_dict()
        resultado.status = validacao.status
        resultado.detalhes = validacao.mensagens()
        # Regra 22: mesmo com o arquivo aceito, mostrar a confiança da
        # identificação e quais campos foram reconhecidos na planilha.
        resultado.confianca_deteccao = identificacao.pontuacao
        resultado.campos_detectados = sorted(identificacao.mapeamento.keys())
        resultado.qualidade_dados = validacao.qualidade_dados
        resultado.mensagem = (
            f"{identificacao.dataset.titulo}: {carga.inseridos} novo(s) e "
            f"{carga.atualizados} atualizado(s) de {validacao.linhas_lidas} linha(s) lidas."
        )
        if arquivar:
            _arquivar(caminho, identificacao.dataset.nome)

    except ErroDashboard as erro:
        logger.warning("Arquivo %s rejeitado: %s", caminho.name, erro.mensagem)
        resultado.status = "ERRO"
        resultado.mensagem = erro.mensagem
        resultado.detalhes = erro.detalhes
    except Exception as erro:  # noqa: BLE001 - nunca vaza stack trace para a tela
        logger.exception("Falha inesperada ao processar %s", caminho.name)
        resultado.status = "ERRO"
        resultado.mensagem = (
            f"Não foi possível processar o arquivo '{caminho.name}'. "
            "O erro foi registrado no log do sistema."
        )
        resultado.detalhes = [type(erro).__name__]

    sessao.add(HistoricoUpload(
        data_hora=datetime.now(),
        arquivo=resultado.arquivo,
        dataset=resultado.dataset or "não identificado",
        registros_lidos=resultado.lidos,
        registros_inseridos=resultado.inseridos,
        registros_atualizados=resultado.atualizados,
        registros_ignorados=resultado.descartados,
        status=resultado.status,
        mensagem=(resultado.mensagem + (" " + "; ".join(resultado.detalhes)
                                        if resultado.detalhes else ""))[:1000],
        usuario=usuario,
    ))
    sessao.flush()
    return resultado


def ordenar_para_carga(caminhos: list[Path],
                       datasets_forcados: dict[str, str] | None = None) -> list[Path]:
    """Ordena os arquivos na ordem correta de carga (metas antes dos fatos).

    Separado de `processar_lote` porque o processamento em segundo plano
    (`app.services.processamento`) percorre os arquivos um a um, com uma
    sessão de banco por arquivo, mas precisa da mesma ordem.
    """
    datasets_forcados = datasets_forcados or {}

    def prioridade(caminho: Path) -> int:
        forcado = datasets_forcados.get(caminho.name)
        if forcado in ORDEM_CARGA:
            return ORDEM_CARGA.index(forcado)
        nome = caminho.name.lower()
        for indice, dataset in enumerate(ORDEM_CARGA):
            if any(dica in nome for dica in DATASETS[dataset].dicas_nome_arquivo):
                return indice
        return len(ORDEM_CARGA)

    return sorted(caminhos, key=prioridade)


def processar_lote(sessao: Session, caminhos: list[Path],
                   datasets_forcados: dict[str, str] | None = None,
                   usuario: str = "local") -> list[ResultadoArquivo]:
    """Processa vários arquivos na ordem correta (metas antes dos fatos)."""
    datasets_forcados = datasets_forcados or {}
    return [
        processar_arquivo(sessao, caminho, datasets_forcados.get(caminho.name), usuario)
        for caminho in ordenar_para_carga(caminhos, datasets_forcados)
    ]


def _arquivar(caminho: Path, dataset: str) -> None:
    """Guarda o arquivo processado com carimbo de data/hora."""
    destino_dir = config.PROCESSED_DIR / dataset
    destino_dir.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = destino_dir / f"{carimbo}_{caminho.name}"
    try:
        shutil.copy2(caminho, destino)
    except OSError as erro:  # pragma: no cover - falha de disco não invalida a carga
        logger.warning("Não foi possível arquivar %s: %s", caminho.name, erro)
