"""Conversores de tipos tolerantes ao que sai do Excel.

Todo conversor devolve `(valor, ok)`. Quando `ok` é False o registro é
contabilizado no relatório de validação em vez de virar zero silencioso —
regra 60 do projeto: 0, "Sem dados" e "Erro" são coisas diferentes.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

import pandas as pd

from app.utils.texto import sem_acento

VAZIOS = {"", "-", "--", "n/a", "na", "nan", "nat", "none", "null", "sem informacao", "#n/d"}

_FORMATOS_DATA = (
    "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
)

_VERDADEIROS = {"sim", "s", "1", "true", "verdadeiro", "faturado", "x", "ok"}
_FALSOS = {"nao", "n", "0", "false", "falso", "nao faturado", "pendente", ""}


def esta_vazio(valor: object) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    if valor is pd.NaT:
        return True
    if isinstance(valor, str):
        return sem_acento(valor).strip().lower() in VAZIOS
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def converter_data(valor: object) -> tuple[date | None, bool]:
    if esta_vazio(valor):
        return None, True  # vazio é permitido; obrigatoriedade é checada à parte
    if isinstance(valor, datetime):
        return valor.date(), True
    if isinstance(valor, date):
        return valor, True
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime().date(), True
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        # Número de série do Excel (base 1899-12-30).
        numero = float(valor)
        if 20000 <= numero <= 80000:
            return (datetime(1899, 12, 30) + timedelta(days=numero)).date(), True
        return None, False
    texto = str(valor).strip()
    for formato in _FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date(), True
        except ValueError:
            continue
    try:
        convertido = pd.to_datetime(texto, dayfirst=True, errors="raise")
        return convertido.date(), True
    except (ValueError, TypeError, pd.errors.ParserError):
        return None, False


def converter_numero(valor: object) -> tuple[float | None, bool]:
    if esta_vazio(valor):
        return None, True
    if isinstance(valor, bool):
        return float(valor), True
    if isinstance(valor, (int, float)):
        return float(valor), True
    texto = str(valor).strip()
    texto = re.sub(r"(?i)^(r\$|us\$)\s*", "", texto).replace("%", "").strip()
    negativo = texto.startswith("(") and texto.endswith(")")
    if negativo:
        texto = texto[1:-1]
    if "," in texto and "." in texto:
        # 1.234,56 (BR) ou 1,234.56 (US) — decide pelo separador mais à direita.
        texto = texto.replace(".", "").replace(",", ".") if texto.rfind(",") > texto.rfind(".") \
            else texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    texto = texto.replace(" ", "").replace("\xa0", "")
    try:
        numero = float(texto)
    except ValueError:
        return None, False
    return (-numero if negativo else numero), True


def converter_inteiro(valor: object) -> tuple[int | None, bool]:
    numero, ok = converter_numero(valor)
    if numero is None or not ok:
        return None, ok
    return int(round(numero)), True


def converter_texto(valor: object) -> tuple[str | None, bool]:
    if esta_vazio(valor):
        return None, True
    texto = re.sub(r"\s+", " ", str(valor)).strip()
    return (texto or None), True


def converter_booleano(valor: object) -> tuple[bool | None, bool]:
    if esta_vazio(valor):
        return None, True
    if isinstance(valor, bool):
        return valor, True
    if isinstance(valor, (int, float)):
        return bool(valor), True
    texto = sem_acento(str(valor)).strip().lower()
    if texto in _VERDADEIROS:
        return True, True
    if texto in _FALSOS:
        return False, True
    return None, False


def converter_data_hora(valor: object) -> tuple[datetime | None, bool]:
    """Converte para datetime, aceitando formatos variados com hora."""
    if esta_vazio(valor):
        return None, True
    if isinstance(valor, datetime):
        return valor, True
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return datetime.combine(valor, datetime.min.time()), True
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime(), True
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        # Número de série do Excel (base 1899-12-30).
        numero = float(valor)
        if 20000 <= numero <= 80000:
            return datetime(1899, 12, 30) + timedelta(days=numero), True
        return None, False
    texto = str(valor).strip()
    # Tenta formatos com hora primeiro
    formatos_com_hora = (
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d/%m/%y %H:%M:%S", "%d/%m/%y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
        "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
    )
    for formato in formatos_com_hora:
        try:
            return datetime.strptime(texto, formato), True
        except ValueError:
            continue
    # Fallback para formatos apenas de data
    for formato in _FORMATOS_DATA:
        try:
            dt = datetime.strptime(texto, formato)
            return dt, True
        except ValueError:
            continue
    try:
        convertido = pd.to_datetime(texto, dayfirst=True, errors="raise")
        return convertido.to_pydatetime(), True
    except (ValueError, TypeError, pd.errors.ParserError):
        return None, False


CONVERSORES = {
    "data": converter_data,
    "data_hora": converter_data_hora,
    "numero": converter_numero,
    "inteiro": converter_inteiro,
    "texto": converter_texto,
    "booleano": converter_booleano,
}
