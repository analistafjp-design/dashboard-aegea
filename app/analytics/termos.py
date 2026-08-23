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

import pandas as pd

from app.analytics import consultas, metas, nucleo
from app.analytics.base import Filtros
from app.analytics.calendario import descrever_data
from app.analytics.dominio_tipos import TIPO_SERVICOS, TIPO_VCG
from app.analytics.periodo import Periodo, resolver


def _por_tipo(dados, tipo: str):
    return dados[dados["tipo"] == tipo] if "tipo" in dados.columns else dados.iloc[0:0]


def _comparativo_por_dimensao(dados: pd.DataFrame, dimensao: str,
                              top: int | None = None) -> list[dict]:
    """Serviços x VCG lado a lado, sem alterar o total oficial do PBIX."""
    colunas = [dimensao, "servicos", "vcg", "total", "participacao"]
    if dados.empty or dimensao not in dados.columns:
        return []
    agrupado = (
        dados.groupby([dimensao, "tipo"], dropna=False)["quantidade"].sum()
        .unstack(fill_value=0)
    )
    saida = pd.DataFrame(index=agrupado.index)
    saida["servicos"] = agrupado.get(TIPO_SERVICOS, 0.0)
    saida["vcg"] = agrupado.get(TIPO_VCG, 0.0)
    saida["total"] = saida["servicos"] + saida["vcg"]
    saida = saida[saida["total"] > 0]
    soma = float(saida["total"].sum())
    saida["participacao"] = (saida["total"] / soma * 100).round(1) if soma else 0.0
    saida = saida.sort_values("total", ascending=False)
    if top:
        saida = saida.head(top)
    return saida.reset_index()[colunas].to_dict("records")


def _diario_por_tipo(dados: pd.DataFrame, meta_total: float | None,
                     periodo: Periodo) -> list[dict]:
    if dados.empty:
        return []
    diario = sorted(_comparativo_por_dimensao(dados, "data"), key=lambda item: item["data"])
    meta_dia = None if meta_total is None or not periodo.dias_uteis_totais else round(
        meta_total / periodo.dias_uteis_totais, 2
    )
    acumulado = 0.0
    for linha in diario:
        acumulado += float(linha["total"])
        linha["acumulado"] = acumulado
        linha["meta_dia"] = meta_dia if descrever_data(linha["data"])["dia_util"] else None
    return diario


def _insights(bloco: dict, por_cidade: list[dict], realizado_total: float | None,
              realizado_vcg: float | None, periodo: Periodo,
              sinais_operacionais: list[dict]) -> list[dict]:
    itens: list[dict] = []
    projetado = bloco.get("projecao")
    meta = bloco.get("meta")
    diferenca = bloco.get("diferenca_projetada")
    if projetado is not None and meta is not None:
        em_risco = diferenca is not None and diferenca < 0
        itens.append({
            "tipo": "alerta" if em_risco else "positivo",
            "titulo": "Projeção do fechamento",
            "texto": (
                f"Ritmo atual projeta {projetado:.0f} termos: "
                f"{'déficit' if em_risco else 'saldo'} de {abs(diferenca or 0):.0f} frente à meta."
            ),
        })
    necessario = bloco.get("necessario_por_dia")
    media = bloco.get("media_dia")
    if necessario is not None and media is not None:
        itens.append({
            "tipo": "alerta" if necessario > media else "positivo",
            "titulo": "Ritmo diário necessário",
            "texto": (
                f"São necessários {necessario:.1f} termos por dia útil; "
                f"a média realizada está em {media:.1f}."
            ),
        })
    if por_cidade:
        lider = por_cidade[0]
        itens.append({
            "tipo": "info",
            "titulo": "Concentração geográfica",
            "texto": (
                f"{lider['cidade']} concentra {lider['participacao']:.1f}% do realizado "
                f"({lider['total']:.0f} termos)."
            ),
        })
    if realizado_total:
        participacao = (realizado_vcg or 0) / realizado_total * 100
        itens.append({
            "tipo": "info",
            "titulo": "Participação VCG",
            "texto": (
                f"VCG responde por {participacao:.1f}% do total. "
                f"Restam {periodo.dias_uteis_restantes} dias úteis para ajuste de rota."
            ),
        })
    if sinais_operacionais:
        total_sinais = sum(item["total"] for item in sinais_operacionais)
        itens.append({
            "tipo": "alerta",
            "titulo": "Sinais fora do realizado oficial",
            "texto": (
                f"Foram identificadas {total_sinais:.0f} ocorrências de não conformidade "
                "ou vistoria pós-varredura para acompanhamento, sem somá-las à meta."
            ),
        })
    return itens


def _sinais_operacionais(dados: pd.DataFrame) -> list[dict]:
    if dados.empty or "status_termo" not in dados.columns:
        return []
    sinais = dados[dados["quantidade"] == 0]
    if sinais.empty:
        return []
    return (
        sinais.groupby("status_termo", as_index=False).size()
        .rename(columns={"status_termo": "sinal", "size": "total"})
        .sort_values("total", ascending=False)
        .to_dict("records")
    )


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
            "qtd_termos", "Termos Aplicados", realizado_total,
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

    por_cidade_tipo = _comparativo_por_dimensao(do_mes, "cidade", top=12)
    por_equipe_tipo = _comparativo_por_dimensao(do_mes, "equipe", top=12)
    sinais_operacionais = _sinais_operacionais(do_mes)

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
        "evolucao_diaria_tipo": _diario_por_tipo(do_mes, meta_total, periodo),
        "por_cidade": nucleo.ranking(do_mes, "cidade", top=15).to_dict("records"),
        "por_cidade_tipo": por_cidade_tipo,
        "por_equipe_tipo": por_equipe_tipo,
        "por_setor": nucleo.ranking(do_mes, "setor", top=15).to_dict("records"),
        "por_frente": nucleo.ranking(do_mes, "frente").to_dict("records"),
        "por_status": nucleo.ranking(do_mes, "status_termo").to_dict("records"),
        "sinais_operacionais": sinais_operacionais,
        "meta_acumulada": metas.meta_acumulada(meta_total, periodo.fracao_decorrida),
        "insights_executivos": _insights(
            blocos[-1], por_cidade_tipo, realizado_total, realizado_vcg, periodo,
            sinais_operacionais,
        ),
    }
