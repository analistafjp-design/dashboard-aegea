"""Leitura das metas oficiais.

Meta NUNCA é estimada. Quando não existe registro para o período, os
indicadores devolvem `None` e a interface mostra "Meta não cadastrada".
"""
from __future__ import annotations

import pandas as pd

from app.analytics import consultas
from app.analytics.base import Filtros

MENSAGEM_SEM_META = "Meta não cadastrada"


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
        return None
    return float(encontradas["valor_meta"].sum())


def meta_total_composta(modulo: str, ano: int, mes: int | None = None,
                        filtros: Filtros | None = None) -> float | None:
    """Meta TOTAL; se não houver, soma as metas por segmento (Serviços + VCG)."""
    valor = meta(modulo, ano, mes, "TOTAL", filtros)
    if valor is not None:
        return valor
    partes = [meta(modulo, ano, mes, seg, filtros)
              for seg in ("SERVICOS", "VCG", "COMERCIAL", "OUTROS")]
    validas = [p for p in partes if p is not None]
    return float(sum(validas)) if validas else None


def meta_acumulada(valor_meta: float | None, fracao_decorrida: float) -> float | None:
    """Parcela da meta que já deveria estar realizada (pelos dias úteis)."""
    if valor_meta is None:
        return None
    return round(valor_meta * max(min(fracao_decorrida, 1.0), 0.0), 2)


def tem_metas() -> bool:
    return not consultas.metas_df().empty


def metas_do_periodo(ano: int, mes: int | None = None) -> pd.DataFrame:
    df = consultas.metas_df()
    if df.empty:
        return df
    saida = df[df["ano"] == ano]
    return saida[saida["mes"] == mes] if mes is not None else saida
