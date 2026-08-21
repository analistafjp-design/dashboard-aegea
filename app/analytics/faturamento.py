"""MÓDULO 1 — Faturamento de Termos (PBIX 1).

Equivalências: Faturamento Termos.Qtd Negociação / Qtd Aguardando /
Qtd Cancelado / Situação / Situação do Termo / d_Cadastro.CIDADE.

Funil: TERMOS -> NEGOCIAÇÃO -> AGUARDANDO -> FATURAMENTO -> CONCLUÍDO.
A conversão é calculada sobre os termos aplicados do mesmo período.
"""
from __future__ import annotations

from app.analytics import consultas, nucleo
from app.analytics.base import AZUL, CINZA, VERDE, VERMELHO, Filtros, Indicador
from app.analytics.dominio_tipos import (
    SIT_AGUARDANDO,
    SIT_CANCELADO,
    SIT_FATURADO,
    SIT_NEGOCIACAO,
)
from app.analytics.periodo import Periodo, resolver


def _qtd(dados, situacao: str) -> float | None:
    if dados.empty:
        return None
    recorte = dados[dados["situacao"] == situacao]
    return float(recorte["quantidade"].sum()) if not recorte.empty else 0.0


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    todos = consultas.dados("faturamento",
                            Filtros(**{**filtros.__dict__, "ano": None, "mes": None}))
    dados = consultas.dados("faturamento", filtros)
    do_mes = dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados

    negociacao = _qtd(do_mes, SIT_NEGOCIACAO)
    aguardando = _qtd(do_mes, SIT_AGUARDANDO)
    faturado = _qtd(do_mes, SIT_FATURADO)
    cancelado = _qtd(do_mes, SIT_CANCELADO)
    total_registros = nucleo.total(do_mes)

    faturados_df = do_mes[do_mes["situacao"] == SIT_FATURADO] if not do_mes.empty else do_mes
    valor_faturado = nucleo.total(faturados_df, "valor")

    # Conversão: quantos termos aplicados do período viraram faturamento.
    termos_periodo = consultas.dados("termos", filtros)
    termos_mes = (termos_periodo[termos_periodo["ano_mes"] == periodo.ano_mes]
                  if not termos_periodo.empty else termos_periodo)
    base_termos = nucleo.total(termos_mes)
    conversao = (round(faturado / base_termos * 100, 1)
                 if faturado is not None and base_termos else None)

    _, anterior = nucleo.comparar_meses(
        todos[todos["situacao"] == SIT_FATURADO] if not todos.empty else todos, periodo)

    indicadores = [
        nucleo.indicador_realizado(
            "qtd_faturado", "Termos Faturados", faturado, anterior=anterior,
            pergunta="Quanto já foi faturado?",
            explicacao="Termos com situação Faturado no mês."),
        nucleo.indicador_realizado(
            "qtd_negociacao", "Em Negociação", negociacao,
            pergunta="O que está em tratativa?",
            explicacao="Termos com situação Negociação."),
        nucleo.indicador_realizado(
            "qtd_aguardando", "Aguardando", aguardando,
            pergunta="O que está parado aguardando?",
            explicacao="Termos com situação Aguardando."),
        nucleo.indicador_realizado(
            "qtd_cancelado", "Cancelados", cancelado,
            pergunta="Quanto se perdeu?",
            explicacao="Termos cancelados no mês."),
        Indicador(
            chave="valor_faturado", titulo="Valor Faturado", valor=valor_faturado,
            formato="moeda", disponivel=valor_faturado is not None,
            mensagem=None if valor_faturado is not None else "Valor não informado na base",
            status=AZUL if valor_faturado is not None else CINZA,
            pergunta="Qual o valor faturado?",
            explicacao="Soma da coluna de valor dos termos faturados."),
        Indicador(
            chave="conversao", titulo="Conversão Termo → Faturamento", valor=conversao,
            formato="percentual", casas=1, disponivel=conversao is not None,
            mensagem=None if conversao is not None else "Sem termos no período para comparar",
            status=(CINZA if conversao is None else (VERDE if conversao >= 70 else
                    (AZUL if conversao >= 40 else VERMELHO))),
            pergunta="Quanto do que foi aplicado virou faturamento?",
            explicacao="Termos faturados dividido pelos termos aplicados no mesmo mês."),
    ]

    funil = [
        {"etapa": "Termos Aplicados", "valor": base_termos},
        {"etapa": "Negociação", "valor": negociacao},
        {"etapa": "Aguardando", "valor": aguardando},
        {"etapa": "Faturamento", "valor": faturado},
        {"etapa": "Concluído", "valor": faturado},
    ]

    return {
        "modulo": "TERMOS",
        "titulo": "Faturamento de Termos",
        "periodo": periodo.to_dict(),
        "tem_dados": not do_mes.empty,
        "indicadores": [i.to_dict() for i in indicadores],
        "funil": funil,
        "total_registros": total_registros,
        "evolucao_mensal": nucleo.evolucao_mensal(dados).to_dict("records"),
        "evolucao_faturado": nucleo.evolucao_mensal(
            todos[todos["situacao"] == SIT_FATURADO] if not todos.empty else todos
        ).to_dict("records"),
        "por_situacao": nucleo.ranking(do_mes, "situacao").to_dict("records"),
        "por_cidade": nucleo.ranking(do_mes, "cidade", top=15).to_dict("records"),
        "valor_por_cidade": nucleo.ranking(faturados_df, "cidade", "valor", top=10)
                                   .to_dict("records"),
    }
