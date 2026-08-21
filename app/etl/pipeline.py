"""Orquestração completa: arquivo -> validação -> leitura -> tratamento ->
banco -> recálculo dos indicadores -> histórico."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import config
from app.etl.carga import carregar
from app.etl.datasets import DATASETS, ORDEM_CARGA
from app.etl.deteccao import analisar_arquivo
from app.etl.transformacao import transformar
from app.models.tabelas import HistoricoUpload
from app.utils.erros import ErroDashboard, ErroImportacao
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
        }


def processar_arquivo(sessao: Session, caminho: Path, dataset_forcado: str | None = None,
                      usuario: str = "local", arquivar: bool = True) -> ResultadoArquivo:
    """Processa um arquivo do início ao fim e registra o histórico."""
    resultado = ResultadoArquivo(arquivo=caminho.name)
    try:
        identificacao = analisar_arquivo(caminho, dataset_forcado)
        if identificacao.dataset is None:
            raise ErroImportacao(
                f"Não foi possível identificar o tipo de base do arquivo '{caminho.name}'. "
                "Selecione o tipo manualmente na tela de atualização.",
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


def processar_lote(sessao: Session, caminhos: list[Path],
                   datasets_forcados: dict[str, str] | None = None,
                   usuario: str = "local") -> list[ResultadoArquivo]:
    """Processa vários arquivos na ordem correta (metas antes dos fatos)."""
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

    resultados = []
    for caminho in sorted(caminhos, key=prioridade):
        resultados.append(
            processar_arquivo(sessao, caminho, datasets_forcados.get(caminho.name), usuario)
        )
    return resultados


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
