"""Leitura dos filtros globais a partir da query string."""
from __future__ import annotations

from datetime import date

from fastapi import Query

from app.analytics.base import Filtros


def _texto(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpo = valor.strip()
    return limpo if limpo and limpo.lower() not in ("todos", "todas", "") else None


def filtros_da_query(
    ano: int | None = Query(None, ge=2000, le=2100),
    mes: int | None = Query(None, ge=1, le=12),
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    cidade: str | None = Query(None, max_length=120),
    frente: str | None = Query(None, max_length=120),
    equipe: str | None = Query(None, max_length=120),
    regiao: str | None = Query(None, max_length=120),
    projeto: str | None = Query(None, max_length=120),
    setor: str | None = Query(None, max_length=120),
) -> Filtros:
    return Filtros(
        ano=ano, mes=mes, data_inicio=data_inicio, data_fim=data_fim,
        cidade=_texto(cidade), frente=_texto(frente), equipe=_texto(equipe),
        regiao=_texto(regiao), projeto=_texto(projeto), setor=_texto(setor),
    )
