"""Dimensão calendário e regras de dias úteis.

Todos os cálculos de ritmo (média diária, meta acumulada, projeção e dias
restantes) usam DIAS ÚTEIS — feriados nacionais fixos, Carnaval, Sexta-feira
Santa e Corpus Christi são excluídos, assim como sábados e domingos.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.models.tabelas import DimCalendario
from app.utils.log import get_logger

logger = get_logger("calendario")

NOMES_MES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
ABREV_MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
NOMES_DIA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def pascoa(ano: int) -> date:
    """Algoritmo de Meeus/Jones/Butcher."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados_moveis(ano: int) -> dict[date, str]:
    domingo_pascoa = pascoa(ano)
    return {
        domingo_pascoa - timedelta(days=48): "Carnaval (segunda)",
        domingo_pascoa - timedelta(days=47): "Carnaval",
        domingo_pascoa - timedelta(days=2): "Sexta-feira Santa",
        domingo_pascoa + timedelta(days=60): "Corpus Christi",
    }


def feriados_do_ano(ano: int) -> dict[date, str]:
    feriados = {date(ano, m, d): nome for (m, d), nome in config.FERIADOS_FIXOS.items()}
    feriados.update(feriados_moveis(ano))
    return feriados


def descrever_data(dia: date, feriados: dict[date, str] | None = None) -> dict:
    feriados = feriados if feriados is not None else feriados_do_ano(dia.year)
    nome_feriado = feriados.get(dia)
    fim_de_semana = dia.weekday() >= 5
    return {
        "data": dia,
        "ano": dia.year,
        "mes": dia.month,
        "nome_mes": NOMES_MES[dia.month - 1],
        "ano_mes": f"{dia.year:04d}-{dia.month:02d}",
        "rotulo_mes": f"{ABREV_MES[dia.month - 1]}/{dia.year}",
        "dia": dia.day,
        "dia_semana": dia.weekday(),
        "nome_dia_semana": NOMES_DIA[dia.weekday()],
        "dia_util": (not fim_de_semana) and nome_feriado is None,
        "feriado": nome_feriado is not None,
        "nome_feriado": nome_feriado,
        "trimestre": (dia.month - 1) // 3 + 1,
    }


def gerar_calendario(sessao: Session, ano_inicio: int, ano_fim: int) -> int:
    """Popula dim_calendario para o intervalo (idempotente)."""
    existentes = {
        d for (d,) in sessao.execute(
            select(DimCalendario.data).where(
                DimCalendario.ano >= ano_inicio, DimCalendario.ano <= ano_fim
            )
        )
    }
    novos = []
    for ano in range(ano_inicio, ano_fim + 1):
        feriados = feriados_do_ano(ano)
        dia = date(ano, 1, 1)
        fim = date(ano, 12, 31)
        while dia <= fim:
            if dia not in existentes:
                novos.append(DimCalendario(**descrever_data(dia, feriados)))
            dia += timedelta(days=1)
    if novos:
        sessao.add_all(novos)
        sessao.flush()
    logger.info("Calendário %s-%s: %s dias inseridos", ano_inicio, ano_fim, len(novos))
    return len(novos)


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Quantidade de dias úteis no intervalo fechado [inicio, fim]."""
    if fim < inicio:
        return 0
    total = 0
    cache: dict[int, dict[date, str]] = {}
    dia = inicio
    while dia <= fim:
        feriados = cache.setdefault(dia.year, feriados_do_ano(dia.year))
        if dia.weekday() < 5 and dia not in feriados:
            total += 1
        dia += timedelta(days=1)
    return total


def primeiro_dia_mes(referencia: date) -> date:
    return referencia.replace(day=1)


def ultimo_dia_mes(referencia: date) -> date:
    if referencia.month == 12:
        return date(referencia.year, 12, 31)
    return date(referencia.year, referencia.month + 1, 1) - timedelta(days=1)


def mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def resumo_mes(referencia: date) -> dict:
    """Dias úteis totais, decorridos e restantes do mês de referência."""
    inicio = primeiro_dia_mes(referencia)
    fim = ultimo_dia_mes(referencia)
    totais = dias_uteis_entre(inicio, fim)
    decorridos = dias_uteis_entre(inicio, min(referencia, fim))
    return {
        "inicio": inicio,
        "fim": fim,
        "dias_uteis_totais": totais,
        "dias_uteis_decorridos": decorridos,
        "dias_uteis_restantes": max(totais - decorridos, 0),
        "ano_mes": f"{referencia.year:04d}-{referencia.month:02d}",
    }


def data_no_enesimo_dia_util(inicio: date, quantidade: int) -> date:
    """Data do n-ésimo dia útil a partir de `inicio` (inclusive).

    Usada para comparar meses de forma justa: um mês parcial só pode ser
    comparado com o MESMO número de dias úteis do mês anterior.
    """
    if quantidade <= 0:
        return inicio
    restantes, dia, ultimo = quantidade, inicio, inicio
    feriados_cache: dict[int, dict[date, str]] = {}
    while restantes > 0:
        feriados = feriados_cache.setdefault(dia.year, feriados_do_ano(dia.year))
        if dia.weekday() < 5 and dia not in feriados:
            restantes -= 1
            ultimo = dia
        dia += timedelta(days=1)
        if (dia - inicio).days > 366:  # trava de segurança
            break
    return ultimo
