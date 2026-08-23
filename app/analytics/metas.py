"""Leitura das metas oficiais e das constantes presentes nos PBIX."""
from __future__ import annotations

import pandas as pd

from app.analytics import consultas
from app.analytics.base import Filtros

MENSAGEM_SEM_META = "Meta não cadastrada"

# Valores encontrados literalmente nas medidas DAX dos PBIX enviados.
# Não são estimativas: Venda/Implantação usa 234 + 188 = 422 e Termos usa
# 250 + 180 = 430. Uma planilha de metas importada continua tendo prioridade.
METAS_POWER_BI = {
    ("VENDA", "TOTAL"): 234.0,
    ("VENDA", "COMERCIAL"): 234.0,
    ("IMPLANTACAO", "TOTAL"): 422.0,
    ("IMPLANTACAO", "SERVICOS"): 234.0,
    ("IMPLANTACAO", "VCG"): 188.0,
    ("TERMOS", "TOTAL"): 430.0,
    ("TERMOS", "SERVICOS"): 250.0,
    ("TERMOS", "VCG"): 180.0,
}


def _filtrar(df: pd.DataFrame, modulo: str, ano: int, mes: int | None,
             segmento: str, filtros: Filtros | None) -> pd.DataFrame:
    if df.empty:
        return df
    saida = df[(df["modulo"] == modulo) & (df["ano"] == ano)]
    if mes is not None:
        saida = saida[saida["mes"] == mes]
    if segmento is not None:
        saida = saida[saida["segmento"] == segmento]

    cidade = getattr(filtros, "cidade", None) if filtros else None
    equipe = getattr(filtros, "equipe", None) if filtros else None
    # Meta específica de cidade/equipe tem prioridade; sem filtro usa-se a meta geral.
    saida = saida[saida["cidade"] == cidade] if cidade else saida[saida["cidade"].isna()]
    saida = saida[saida["equipe"] == equipe] if equipe else saida[saida["equipe"].isna()]
    return saida


def meta(modulo: str, ano: int, mes: int | None = None, segmento: str = "TOTAL",
         filtros: Filtros | None = None) -> float | None:
    """Meta oficial do período. `None` = não cadastrada."""
    encontradas = _filtrar(consultas.metas_df(), modulo, ano, mes, segmento, filtros)
    if encontradas.empty:
        # Metas por cidade/equipe não existem nos PBIX; nesse caso não se
        # aplica a constante geral ao recorte para não inventar uma meta local.
        if filtros and (filtros.cidade or filtros.equipe):
            return None
        return METAS_POWER_BI.get((modulo, segmento))
    return float(encontradas["valor_meta"].sum())


def meta_total_composta(modulo: str, ano: int, mes: int | None = None,
                        filtros: Filtros | None = None) -> float | None:
    """Meta TOTAL; se não houver, soma as metas por segmento (Serviços + VCG)."""
    df = consultas.metas_df()
    total_cadastrado = _filtrar(df, modulo, ano, mes, "TOTAL", filtros)
    if not total_cadastrado.empty:
        return float(total_cadastrado["valor_meta"].sum())

    partes_cadastradas = []
    for segmento in ("SERVICOS", "VCG", "COMERCIAL", "OUTROS"):
        parte = _filtrar(df, modulo, ano, mes, segmento, filtros)
        if not parte.empty:
            partes_cadastradas.append(float(parte["valor_meta"].sum()))
    if partes_cadastradas:
        return float(sum(partes_cadastradas))
    if filtros and (filtros.cidade or filtros.equipe):
        return None
    return METAS_POWER_BI.get((modulo, "TOTAL"))


def meta_acumulada(valor_meta: float | None, fracao_decorrida: float) -> float | None:
    """Parcela da meta que já deveria estar realizada (pelos dias úteis)."""
    if valor_meta is None:
        return None
    return round(valor_meta * max(min(fracao_decorrida, 1.0), 0.0), 2)


def tem_metas() -> bool:
    return bool(METAS_POWER_BI) or not consultas.metas_df().empty


def metas_do_periodo(ano: int, mes: int | None = None) -> pd.DataFrame:
    df = consultas.metas_df()
    if df.empty:
        return df
    saida = df[df["ano"] == ano]
    return saida[saida["mes"] == mes] if mes is not None else saida
