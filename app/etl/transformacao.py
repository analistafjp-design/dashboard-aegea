"""Normalização, conversão e validação dos dados lidos da planilha.

Saída: um DataFrame padronizado (colunas internas) + um relatório de
validação legível pelo usuário. Nada é convertido para zero para "não dar
erro": linha inválida é descartada e contabilizada.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.etl import dominio
from app.etl.datasets import Dataset
from app.etl.deteccao import Identificacao
from app.etl.tipos import CONVERSORES, esta_vazio
from app.utils.erros import ErroValidacaoArquivo
from app.utils.log import get_logger
from app.utils.texto import titulo

logger = get_logger("etl.transformacao")


@dataclass
class RelatorioValidacao:
    dataset: str
    aba: str
    linhas_lidas: int = 0
    linhas_validas: int = 0
    linhas_descartadas: int = 0
    duplicadas_no_arquivo: int = 0
    problemas: dict[str, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    colunas_mapeadas: dict[str, str] = field(default_factory=dict)
    colunas_ignoradas: list[str] = field(default_factory=list)
    colunas_ausentes: list[str] = field(default_factory=list)

    def registrar_problema(self, descricao: str) -> None:
        self.problemas[descricao] = self.problemas.get(descricao, 0) + 1

    @property
    def status(self) -> str:
        if self.linhas_validas == 0:
            return "ERRO"
        if self.linhas_descartadas or self.problemas:
            return "ATENCAO"
        return "SUCESSO"

    def mensagens(self) -> list[str]:
        saida = [f"{qtd} {descricao}" for descricao, qtd in sorted(
            self.problemas.items(), key=lambda item: item[1], reverse=True)]
        saida.extend(self.avisos)
        return saida

    def resumo(self) -> str:
        base = (f"{self.linhas_validas} de {self.linhas_lidas} registros válidos "
                f"na aba '{self.aba}'")
        mensagens = self.mensagens()
        return f"{base}. " + "; ".join(mensagens) if mensagens else base + "."

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "aba": self.aba,
            "linhas_lidas": self.linhas_lidas,
            "linhas_validas": self.linhas_validas,
            "linhas_descartadas": self.linhas_descartadas,
            "duplicadas_no_arquivo": self.duplicadas_no_arquivo,
            "problemas": self.problemas,
            "avisos": self.avisos,
            "colunas_mapeadas": self.colunas_mapeadas,
            "colunas_ignoradas": self.colunas_ignoradas,
            "colunas_ausentes": self.colunas_ausentes,
            "status": self.status,
            "resumo": self.resumo(),
        }


def _rotulo(campo: str) -> str:
    return campo.replace("_", " ")


def transformar(identificacao: Identificacao) -> tuple[pd.DataFrame, RelatorioValidacao]:
    dataset = identificacao.dataset
    if dataset is None:
        raise ErroValidacaoArquivo(
            "Arquivo incompatível: não foi possível reconhecer o tipo de base pelas "
            "colunas encontradas.",
            [f"Colunas lidas: {', '.join(map(str, identificacao.planilha.dados.columns[:15]))}"],
        )
    if identificacao.faltantes:
        faltando = ", ".join(f"'{_rotulo(c)}'" for c in identificacao.faltantes)
        raise ErroValidacaoArquivo(
            f"Arquivo incompatível com a base {dataset.titulo}. "
            f"A(s) coluna(s) {faltando} não foi(ram) encontrada(s).",
            [f"Colunas do arquivo: {', '.join(map(str, identificacao.planilha.dados.columns[:20]))}"],
        )

    origem = identificacao.planilha.dados
    relatorio = RelatorioValidacao(
        dataset=dataset.nome,
        aba=identificacao.planilha.nome,
        linhas_lidas=len(origem),
        colunas_mapeadas=dict(identificacao.mapeamento),
        colunas_ignoradas=identificacao.colunas_ignoradas,
        colunas_ausentes=[c.nome for c in dataset.campos if c.nome not in identificacao.mapeamento],
    )
    if relatorio.colunas_ausentes:
        relatorio.avisos.append(
            "colunas opcionais ausentes: " + ", ".join(map(_rotulo, relatorio.colunas_ausentes))
        )

    linhas: list[dict] = []
    for _, linha_bruta in origem.iterrows():
        registro: dict = {}
        descartar = False

        for campo in dataset.campos:
            coluna = identificacao.mapeamento.get(campo.nome)
            bruto = linha_bruta[coluna] if coluna is not None else None
            if coluna is None or esta_vazio(bruto):
                if campo.obrigatorio and campo.padrao is None:
                    relatorio.registrar_problema(
                        f"registro(s) sem '{_rotulo(campo.nome)}' (descartado)")
                    descartar = True
                    break
                registro[campo.nome] = campo.padrao
                continue

            valor, ok = CONVERSORES[campo.tipo](bruto)
            if not ok:
                tipo_legivel = {"data": "data inválida", "numero": "número inválido",
                                "inteiro": "número inválido",
                                "booleano": "valor Sim/Não inválido"}.get(
                                    campo.tipo, "valor inválido")
                relatorio.registrar_problema(
                    f"registro(s) com {tipo_legivel} em '{_rotulo(campo.nome)}'"
                    + (" (descartado)" if campo.obrigatorio else " (campo ignorado)")
                )
                if campo.obrigatorio:
                    descartar = True
                    break
                registro[campo.nome] = campo.padrao
                continue

            if valor is None and campo.obrigatorio:
                relatorio.registrar_problema(
                    f"registro(s) sem '{_rotulo(campo.nome)}' (descartado)")
                descartar = True
                break
            registro[campo.nome] = valor if valor is not None else campo.padrao

        if descartar:
            relatorio.linhas_descartadas += 1
            continue
        linhas.append(registro)

    if not linhas:
        raise ErroValidacaoArquivo(
            f"Nenhum registro válido foi encontrado na base {dataset.titulo}.",
            relatorio.mensagens(),
        )

    dados = pd.DataFrame(linhas)
    dados = _derivar(dataset, dados)
    dados = _remover_duplicadas(dataset, dados, relatorio)

    relatorio.linhas_validas = len(dados)
    logger.info("Transformação %s: %s", dataset.nome, relatorio.resumo())
    return dados, relatorio


def _derivar(dataset: Dataset, dados: pd.DataFrame) -> pd.DataFrame:
    """Colunas calculadas a partir das colunas lidas."""
    if "data" in dados.columns:
        dados["ano_mes"] = dados["data"].map(lambda d: f"{d.year:04d}-{d.month:02d}")
        dados["ano"] = dados["data"].map(lambda d: d.year)
        dados["mes"] = dados["data"].map(lambda d: d.month)

    for coluna in ("cidade", "equipe", "regiao", "projeto", "setor", "recurso"):
        if coluna in dados.columns:
            dados[coluna] = dados[coluna].map(lambda v: titulo(v) or None)

    if "frente" in dados.columns:
        dados["frente"] = dados["frente"].map(dominio.normalizar_frente)

    if dataset.nome == "vendas":
        dados["canal"] = dados["frente"].map(dominio.canal_venda)

    if dataset.nome in ("termos", "implantacao"):
        colunas_tipo = [c for c in ("tipo", "frente", "servico") if c in dados.columns]
        dados["tipo"] = dados.apply(
            lambda linha: dominio.classificar_tipo(*[linha[c] for c in colunas_tipo]), axis=1
        )

    if dataset.nome == "termos" and "status_termo" in dados.columns:
        dados["status_termo"] = dados["status_termo"].map(dominio.normalizar_status_termo)

    if dataset.nome == "faturamento":
        dados["situacao"] = dados["situacao"].map(dominio.normalizar_situacao_faturamento)
        dados["inicio_mes"] = dados["data"].map(lambda d: d.replace(day=1))

    if dataset.nome == "implantacao":
        # "faturado" ausente é diferente de "não faturado": mantém-se False, mas o
        # relatório avisa para que o indicador não seja lido como certeza.
        if "faturado" not in dados.columns:
            dados["faturado"] = False
        dados["faturado"] = dados["faturado"].map(lambda v: bool(v) if v is not None else False)

    if dataset.nome == "metas":
        dados["modulo"] = dados["modulo"].map(dominio.normalizar_modulo_meta)
        dados["segmento"] = dados["segmento"].map(dominio.normalizar_segmento_meta)

    if "quantidade" in dados.columns:
        dados["quantidade"] = dados["quantidade"].fillna(1.0)
    if "qtd_os" in dados.columns:
        dados["qtd_os"] = dados["qtd_os"].fillna(1.0)
    return dados


def montar_chave(dataset: Dataset, linha: pd.Series) -> str:
    partes = []
    for campo in dataset.chave_unica:
        valor = linha.get(campo)
        partes.append("" if valor is None or (isinstance(valor, float) and pd.isna(valor))
                      else str(valor).strip().lower())
    return "|".join([dataset.nome, *partes])


def _remover_duplicadas(dataset: Dataset, dados: pd.DataFrame,
                        relatorio: RelatorioValidacao) -> pd.DataFrame:
    """Aplica a chave única do dataset; a última ocorrência prevalece."""
    dados = dados.copy()
    dados["chave_unica"] = dados.apply(lambda linha: montar_chave(dataset, linha), axis=1)
    duplicadas = int(dados["chave_unica"].duplicated().sum())
    if duplicadas:
        relatorio.duplicadas_no_arquivo = duplicadas
        relatorio.avisos.append(
            f"{duplicadas} registro(s) duplicado(s) no próprio arquivo "
            f"(chave: {' + '.join(dataset.chave_unica)}) — manteve-se a última ocorrência"
        )
        dados = dados.drop_duplicates(subset="chave_unica", keep="last")
    return dados.reset_index(drop=True)
