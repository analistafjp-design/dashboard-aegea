"""MÓDULO 1 — Termos Aplicados (PBIX 1).

Equivalências com o Power BI:

| Indicador Python        | Referência no PBIX                    |
|-------------------------|---------------------------------------|
| realizado_total         | f_Fild.Realizado Total / Medidas.Realizado Total |
| realizado_servicos      | f_Fild.Realizado Serviços             |
| realizado_vcg           | f_Fild.Realizado VCG                  |
| atingimento             | Medidas.% Atingimento                 |
| dias_restantes          | Medidas.Dias Restantes                |
| qtd_termos_aplicados    | Termos.Qtd Termos Aplicados           |
| status dos termos       | Termos.Status Termo                   |
| distribuição por setor  | Setor do Recurso.Setor do Recurso     |
"""
from __future__ import annotations

from app.analytics import consultas, metas, nucleo
from app.analytics.base import Filtros
from app.analytics.dominio_tipos import TIPO_SERVICOS, TIPO_VCG
from app.analytics.periodo import Periodo, resolver


def _por_tipo(dados, tipo: str):
    return dados[dados["tipo"] == tipo] if "tipo" in dados.columns else dados.iloc[0:0]


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    todos = consultas.dados("termos", Filtros(**{**filtros.__dict__, "ano": None, "mes": None}))
    dados = consultas.dados("termos", filtros)
    do_mes = dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados

    realizado_total = nucleo.total(do_mes)
    realizado_servicos = nucleo.total(_por_tipo(do_mes, TIPO_SERVICOS))
    realizado_vcg = nucleo.total(_por_tipo(do_mes, TIPO_VCG))

    meta_total = metas.meta_total_composta("TERMOS", periodo.ano, periodo.mes, filtros)
    meta_servicos = metas.meta("TERMOS", periodo.ano, periodo.mes, "SERVICOS", filtros)
    meta_vcg = metas.meta("TERMOS", periodo.ano, periodo.mes, "VCG", filtros)

    _, anterior_total = nucleo.comparar_meses(todos, periodo)

    blocos = [
        nucleo.bloco_meta(realizado_servicos, meta_servicos, periodo, "Serviços"),
        nucleo.bloco_meta(realizado_vcg, meta_vcg, periodo, "VCG"),
        nucleo.bloco_meta(realizado_total, meta_total, periodo, "Total"),
    ]

    indicadores = [
        nucleo.indicador_realizado(
            "realizado_total", "Realizado Total", realizado_total, meta_total, anterior_total,
            pergunta="Como estamos no mês?",
            explicacao="Soma dos termos aplicados no mês de referência."),
        nucleo.indicador_realizado(
            "realizado_servicos", "Realizado Serviços", realizado_servicos, meta_servicos,
            pergunta="Como está a frente de Serviços?",
            explicacao="Termos classificados como Serviços."),
        nucleo.indicador_realizado(
            "realizado_vcg", "Realizado VCG", realizado_vcg, meta_vcg,
            pergunta="Como está a frente VCG?",
            explicacao="Termos classificados como VCG."),
        nucleo.indicador_realizado(
            "qtd_termos", "Termos Aplicados", nucleo.contar(do_mes),
            pergunta="Quantos termos foram aplicados?",
            explicacao="Quantidade de registros de termo no período."),
        nucleo.indicador_realizado(
            "media_dia", "Realizado por Dia",
            nucleo.media_diaria(realizado_total, periodo.dias_uteis_decorridos), casas=1,
            pergunta="Qual o ritmo diário?",
            explicacao=f"Realizado dividido por {periodo.dias_uteis_decorridos} dia(s) útil(eis) decorrido(s)."),
        nucleo.indicador_realizado(
            "dias_restantes", "Dias Úteis Restantes", float(periodo.dias_uteis_restantes),
            pergunta="Quanto tempo resta?",
            explicacao=f"Dias úteis até {periodo.fim.strftime('%d/%m/%Y')}."),
    ]

    return {
        "modulo": "TERMOS",
        "titulo": "Termos Aplicados",
        "periodo": periodo.to_dict(),
        "tem_dados": not do_mes.empty,
        "indicadores": [i.to_dict() for i in indicadores],
        "blocos_meta": nucleo.matriz_meta(blocos),
        "bloco_principal": blocos[-1],
        "evolucao_mensal": nucleo.evolucao_mensal(dados).to_dict("records"),
        "evolucao_diaria": nucleo.evolucao_diaria(do_mes).to_dict("records"),
        "por_cidade": nucleo.ranking(do_mes, "cidade", top=15).to_dict("records"),
        "por_setor": nucleo.ranking(do_mes, "setor", top=15).to_dict("records"),
        "por_frente": nucleo.ranking(do_mes, "frente").to_dict("records"),
        "por_status": nucleo.ranking(do_mes, "status_termo").to_dict("records"),
        "meta_acumulada": metas.meta_acumulada(meta_total, periodo.fracao_decorrida),
    }
