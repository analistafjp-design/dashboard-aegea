"""Conversores de tipos vindos do Excel."""
from datetime import date, datetime

import pandas as pd
import pytest

from app.etl.dominio import classificar_tipo
from app.etl.tipos import (
    converter_booleano,
    converter_data,
    converter_inteiro,
    converter_numero,
    converter_texto,
    esta_vazio,
)


def test_valor_ausente_do_pandas_nao_quebra_classificacao():
    assert classificar_tipo(pd.NA, None) == "NAO_CLASSIFICADO"


@pytest.mark.parametrize("entrada,esperado", [
    ("21/08/2026", date(2026, 8, 21)),
    ("2026-08-21", date(2026, 8, 21)),
    ("21-08-2026", date(2026, 8, 21)),
    (datetime(2026, 8, 21, 10, 30), date(2026, 8, 21)),
    (date(2026, 8, 21), date(2026, 8, 21)),
    (46255, date(2026, 8, 21)),  # número de série do Excel
])
def test_datas_validas(entrada, esperado):
    valor, ok = converter_data(entrada)
    assert ok and valor == esperado


def test_data_invalida_nao_vira_zero():
    valor, ok = converter_data("data errada")
    assert valor is None and ok is False


def test_data_vazia_e_permitida_mas_nula():
    valor, ok = converter_data("")
    assert valor is None and ok is True


@pytest.mark.parametrize("entrada,esperado", [
    ("1.234,56", 1234.56), ("1,234.56", 1234.56), ("R$ 1.500,00", 1500.0),
    ("42", 42.0), (7, 7.0), ("(50)", -50.0), ("15%", 15.0), ("1 234", 1234.0),
])
def test_numeros_validos(entrada, esperado):
    valor, ok = converter_numero(entrada)
    assert ok and valor == pytest.approx(esperado)


def test_numero_invalido_sinaliza_erro():
    valor, ok = converter_numero("muitos")
    assert valor is None and ok is False


def test_inteiro_arredonda():
    assert converter_inteiro("12,6") == (13, True)


@pytest.mark.parametrize("entrada,esperado", [
    ("Sim", True), ("NÃO", False), ("Faturado", True), ("Não Faturado", False),
    (1, True), (0, False), ("S", True), ("N", False),
])
def test_booleanos(entrada, esperado):
    valor, ok = converter_booleano(entrada)
    assert ok and valor is esperado


def test_booleano_desconhecido_sinaliza_erro():
    assert converter_booleano("talvez") == (None, False)


def test_texto_normaliza_espacos():
    assert converter_texto("  Rio   Bonito ") == ("Rio Bonito", True)


@pytest.mark.parametrize("entrada", [None, "", "  ", "-", "N/A", "nan", float("nan")])
def test_valores_vazios(entrada):
    assert esta_vazio(entrada) is True


def test_zero_nao_e_vazio():
    assert esta_vazio(0) is False
    assert converter_numero(0) == (0.0, True)
