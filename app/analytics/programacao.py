"""MÓDULO 3 — Programação Diária (PBIX 3).

Equivalências: Medidas.Qtd OS Programadas, Qtd Equipes Programadas,
Data Programação, Programação.Regiao, Programação.Recurso,
Medidas.Projeto Principal.

Carga operacional: uma equipe é considerada sobrecarregada quando fica
50% acima da média de O.S. por equipe do dia, e subutilizada quando fica
50% abaixo — sempre com pelo menos 3 equipes programadas para a média
fazer sentido.
"""
from __future__ import annotations

import pandas as pd

from app.analytics import consultas, nucleo
from app.analytics.base import AMARELO, AZUL, CINZA, VERMELHO, Filtros, Indicador
from app.analytics.periodo import Periodo, resolver

LIMITE_SOBRECARGA = 1.5
LIMITE_SUBUTILIZACAO = 0.5
MINIMO_EQUIPES_PARA_MEDIA = 3


def _data_referencia(dados: pd.DataFrame, filtros: Filtros):
    if dados.empty:
        return None
    if filtros.data_fim is not None:
        candidatas = [d for d in dados["data"].unique() if d <= filtros.data_fim]
        return max(candidatas) if candidatas else None
    return max(dados["data"])


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    dados = consultas.dados("programacao", filtros)
    do_mes = dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados

    data_ref = _data_referencia(do_mes, filtros)
    do_dia = do_mes[do_mes["data"] == data_ref] if data_ref else do_mes.iloc[0:0]

    os_dia = nucleo.total(do_dia, "qtd_os")
    equipes_dia = nucleo.distintos(do_dia, "equipe")
    os_mes = nucleo.total(do_mes, "qtd_os")
    equipes_mes = nucleo.distintos(do_mes, "equipe")
    media_os_equipe = (round(os_dia / equipes_dia, 1)
                       if os_dia is not None and equipes_dia else None)

    carga_equipe = nucleo.ranking(do_dia, "equipe", "qtd_os")
    desequilibrios = _detectar_desequilibrios(carga_equipe, media_os_equipe)

    indicadores = [
        nucleo.indicador_realizado(
            "os_programadas_dia", "O.S. Programadas (dia)", os_dia,
            pergunta="Quanto está programado para hoje?",
            explicacao=f"O.S. da data {data_ref.strftime('%d/%m/%Y') if data_ref else '-'}."),
        nucleo.indicador_realizado(
            "equipes_programadas", "Equipes Programadas", equipes_dia,
            pergunta="Quantas equipes estão em campo?",
            explicacao="Recursos distintos programados na data de referência."),
        Indicador(
            chave="media_os_equipe", titulo="Média de O.S. por Equipe",
            valor=media_os_equipe, casas=1, disponivel=media_os_equipe is not None,
            mensagem=None if media_os_equipe is not None else "Sem programação na data",
            status=AZUL if media_os_equipe is not None else CINZA,
            pergunta="A carga está equilibrada?",
            explicacao="O.S. do dia dividido pelas equipes programadas."),
        nucleo.indicador_realizado(
            "os_programadas_mes", "O.S. Programadas (mês)", os_mes,
            pergunta="Qual o volume do mês?",
            explicacao=f"Total de O.S. programadas em {periodo.rotulo}."),
        nucleo.indicador_realizado(
            "equipes_mes", "Equipes no Mês", equipes_mes,
            pergunta="Quantas equipes atuaram?",
            explicacao="Recursos distintos programados no mês."),
        Indicador(
            chave="desequilibrios", titulo="Desequilíbrios Detectados",
            valor=float(len(desequilibrios)) if data_ref else None,
            disponivel=data_ref is not None,
            mensagem=None if data_ref else "Sem programação",
            status=(CINZA if data_ref is None else
                    (VERMELHO if len(desequilibrios) > 2 else
                     (AMARELO if desequilibrios else AZUL))),
            pergunta="Onde a carga está desbalanceada?",
            explicacao="Equipes 50% acima ou abaixo da média de O.S. do dia."),
    ]

    agenda = (do_dia if not do_dia.empty else do_mes)
    colunas_agenda = [c for c in ("data", "regiao", "equipe", "projeto", "cidade", "qtd_os")
                      if c in agenda.columns]
    agenda_registros = (
        agenda[colunas_agenda].sort_values(["data", "regiao", "equipe"]).head(500)
        .assign(data=lambda d: d["data"].map(lambda x: x.strftime("%d/%m/%Y")))
        .to_dict("records") if not agenda.empty else []
    )

    return {
        "modulo": "PROGRAMACAO",
        "titulo": "Programação Diária",
        "periodo": periodo.to_dict(),
        "data_referencia": data_ref.isoformat() if data_ref else None,
        "data_referencia_br": data_ref.strftime("%d/%m/%Y") if data_ref else None,
        "tem_dados": not do_mes.empty,
        "indicadores": [i.to_dict() for i in indicadores],
        "agenda": agenda_registros,
        "por_equipe": carga_equipe.to_dict("records"),
        "por_regiao": nucleo.ranking(do_dia, "regiao", "qtd_os").to_dict("records"),
        "por_projeto": nucleo.ranking(do_dia, "projeto", "qtd_os").to_dict("records"),
        "por_dia": nucleo.evolucao_diaria(do_mes, "qtd_os").to_dict("records"),
        "desequilibrios": desequilibrios,
        "datas_disponiveis": sorted({d.isoformat() for d in do_mes["data"]}, reverse=True)[:31]
                             if not do_mes.empty else [],
    }


def _detectar_desequilibrios(carga: pd.DataFrame, media: float | None) -> list[dict]:
    if carga.empty or not media or len(carga) < MINIMO_EQUIPES_PARA_MEDIA:
        return []
    achados = []
    for _, linha in carga.iterrows():
        proporcao = linha["total"] / media
        if proporcao >= LIMITE_SOBRECARGA:
            achados.append({
                "equipe": linha["equipe"], "os": linha["total"], "tipo": "sobrecarregada",
                "texto": (f"{linha['equipe']} com {int(linha['total'])} O.S. — "
                          f"{proporcao:.1f}x a média do dia"),
                "status": VERMELHO,
            })
        elif proporcao <= LIMITE_SUBUTILIZACAO:
            achados.append({
                "equipe": linha["equipe"], "os": linha["total"], "tipo": "subutilizada",
                "texto": (f"{linha['equipe']} com apenas {int(linha['total'])} O.S. — "
                          f"{proporcao:.0%} da média do dia"),
                "status": AMARELO,
            })
    return achados
