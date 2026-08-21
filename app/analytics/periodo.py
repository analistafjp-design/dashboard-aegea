"""Resolução do período de referência.

Quando o usuário não escolhe ano/mês, o dashboard usa o mês mais recente
COM DADOS — nunca o mês do relógio, que poderia mostrar tudo zerado.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.analytics import consultas
from app.analytics.base import Filtros
from app.analytics.calendario import (
    ABREV_MES,
    NOMES_MES,
    dias_uteis_entre,
    mes_anterior,
    primeiro_dia_mes,
    ultimo_dia_mes,
)


@dataclass
class Periodo:
    ano: int
    mes: int
    inicio: date
    fim: date
    referencia: date            # última data com dado dentro do mês
    dias_uteis_totais: int
    dias_uteis_decorridos: int
    dias_uteis_restantes: int
    tem_dados: bool = True

    @property
    def ano_mes(self) -> str:
        return f"{self.ano:04d}-{self.mes:02d}"

    @property
    def rotulo(self) -> str:
        return f"{NOMES_MES[self.mes - 1]}/{self.ano}"

    @property
    def rotulo_curto(self) -> str:
        return f"{ABREV_MES[self.mes - 1]}/{self.ano}"

    @property
    def fracao_decorrida(self) -> float:
        if not self.dias_uteis_totais:
            return 0.0
        return self.dias_uteis_decorridos / self.dias_uteis_totais

    def anterior(self) -> "Periodo":
        ano, mes = mes_anterior(self.ano, self.mes)
        return montar(ano, mes)

    def to_dict(self) -> dict:
        return {
            "ano": self.ano, "mes": self.mes, "ano_mes": self.ano_mes,
            "rotulo": self.rotulo, "rotulo_curto": self.rotulo_curto,
            "inicio": self.inicio.isoformat(), "fim": self.fim.isoformat(),
            "referencia": self.referencia.isoformat(),
            "dias_uteis_totais": self.dias_uteis_totais,
            "dias_uteis_decorridos": self.dias_uteis_decorridos,
            "dias_uteis_restantes": self.dias_uteis_restantes,
            "tem_dados": self.tem_dados,
        }


def montar(ano: int, mes: int, referencia: date | None = None) -> Periodo:
    inicio = date(ano, mes, 1)
    fim = ultimo_dia_mes(inicio)
    _, ultima_data = consultas.periodo_disponivel()
    if referencia is None:
        candidata = ultima_data if ultima_data else date.today()
        referencia = min(max(candidata, inicio), fim)
    totais = dias_uteis_entre(inicio, fim)
    decorridos = dias_uteis_entre(inicio, min(referencia, fim))
    return Periodo(
        ano=ano, mes=mes, inicio=inicio, fim=fim, referencia=referencia,
        dias_uteis_totais=totais, dias_uteis_decorridos=decorridos,
        dias_uteis_restantes=max(totais - decorridos, 0),
    )


def resolver(filtros: Filtros) -> Periodo:
    """Período de referência considerando os filtros e os dados existentes."""
    _, ultima_data = consultas.periodo_disponivel()
    base = ultima_data or date.today()

    ano = filtros.ano or base.year
    mes = filtros.mes or (base.month if filtros.ano in (None, base.year) else 12)

    if filtros.data_fim is not None:
        ano, mes = filtros.data_fim.year, filtros.data_fim.month
        return montar(ano, mes, filtros.data_fim)

    referencia = base if (ano, mes) == (base.year, base.month) else None
    periodo = montar(ano, mes, referencia)
    periodo.tem_dados = ultima_data is not None
    return periodo


def intervalo_do_filtro(filtros: Filtros, periodo: Periodo) -> tuple[date, date]:
    """Intervalo efetivo considerado nos cálculos."""
    inicio = filtros.data_inicio or primeiro_dia_mes(periodo.inicio)
    fim = filtros.data_fim or periodo.fim
    return inicio, fim
