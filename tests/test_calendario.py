"""Dimensão calendário, dias úteis e feriados."""
from datetime import date

from app.analytics.calendario import (
    data_no_enesimo_dia_util,
    descrever_data,
    dias_uteis_entre,
    feriados_do_ano,
    gerar_calendario,
    pascoa,
    resumo_mes,
    ultimo_dia_mes,
)
from app.models.db import sessao


def test_pascoa_conhecida():
    assert pascoa(2024) == date(2024, 3, 31)
    assert pascoa(2025) == date(2025, 4, 20)
    assert pascoa(2026) == date(2026, 4, 5)


def test_feriados_incluem_fixos_e_moveis():
    feriados = feriados_do_ann = feriados_do_ano(2026)
    assert date(2026, 1, 1) in feriados          # Confraternização
    assert date(2026, 12, 25) in feriados        # Natal
    assert date(2026, 4, 3) in feriados          # Sexta-feira Santa (Páscoa 05/04)
    assert date(2026, 6, 4) in feriados          # Corpus Christi


def test_fim_de_semana_e_feriado_nao_sao_dia_util():
    assert descrever_data(date(2026, 8, 22))["dia_util"] is False   # sábado
    assert descrever_data(date(2026, 12, 25))["dia_util"] is False  # Natal
    assert descrever_data(date(2026, 8, 21))["dia_util"] is True    # sexta comum


def test_dias_uteis_entre_conta_intervalo_fechado():
    # 03/08/2026 (seg) a 07/08/2026 (sex) = 5 dias úteis
    assert dias_uteis_entre(date(2026, 8, 3), date(2026, 8, 7)) == 5
    assert dias_uteis_entre(date(2026, 8, 8), date(2026, 8, 9)) == 0   # fim de semana
    assert dias_uteis_entre(date(2026, 8, 7), date(2026, 8, 3)) == 0   # invertido


def test_resumo_mes_separa_decorridos_e_restantes():
    resumo = resumo_mes(date(2026, 8, 21))
    assert resumo["dias_uteis_totais"] == dias_uteis_entre(date(2026, 8, 1),
                                                           ultimo_dia_mes(date(2026, 8, 1)))
    assert resumo["dias_uteis_decorridos"] + resumo["dias_uteis_restantes"] == \
        resumo["dias_uteis_totais"]


def test_enesimo_dia_util():
    # 1º dia útil de agosto/2026 é 03/08 (dia 1 é sábado)
    assert data_no_enesimo_dia_util(date(2026, 8, 1), 1) == date(2026, 8, 3)
    assert data_no_enesimo_dia_util(date(2026, 8, 1), 5) == date(2026, 8, 7)
    assert data_no_enesimo_dia_util(date(2026, 8, 1), 0) == date(2026, 8, 1)


def test_gerar_calendario_e_idempotente():
    with sessao() as s:
        primeiro = gerar_calendario(s, 2026, 2026)
        segundo = gerar_calendario(s, 2026, 2026)
    assert primeiro == 365
    assert segundo == 0
