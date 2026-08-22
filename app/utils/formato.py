"""Formatação numérica no padrão brasileiro."""
from __future__ import annotations

from datetime import date, datetime


def numero(valor: float | int | None, casas: int = 0) -> str:
    if valor is None:
        return "Sem dados"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def moeda(valor: float | None) -> str:
    if valor is None:
        return "Sem dados"
    return f"R$ {numero(valor, 2)}"


def percentual(valor: float | None, casas: int = 1) -> str:
    if valor is None:
        return "Sem dados"
    return f"{numero(valor, casas)}%"


def data_br(valor: date | datetime | None) -> str:
    if valor is None:
        return "-"
    return valor.strftime("%d/%m/%Y")


def data_hora_br(valor: datetime | None) -> str:
    if valor is None:
        return "-"
    return valor.strftime("%d/%m/%Y %H:%M")
