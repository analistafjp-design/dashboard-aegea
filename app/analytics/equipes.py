"""Desempenho das Equipes.

Equipes logadas (PBIX 2): Medidas.Equipes Logadas Serviços / Venda /
VCG Rio Bonito / VCG SFI. Aqui "logada" é lida como equipe COM produção
registrada no período — é o que a base operacional permite afirmar.

Os módulos NÃO são somados: a tabela mostra Termos, Venda e Implantação
em colunas separadas e o ranking usa a base escolhida pelo usuário.
"""
from __future__ import annotations

import pandas as pd

from app.analytics import consultas, metas, nucleo
from app.analytics.base import Filtros, status_por_atingimento
from app.analytics.dominio_tipos import TIPO_SERVICOS, TIPO_VCG
from app.analytics.periodo import Periodo, resolver

BASES = {"implantacao": "Implantação", "vendas": "Venda", "termos": "Termos"}
MODULO_DA_BASE = {"implantacao": "IMPLANTACAO", "vendas": "VENDA", "termos": "TERMOS"}


def _do_mes(nome: str, filtros: Filtros, periodo: Periodo) -> pd.DataFrame:
    dados = consultas.dados(nome, filtros)
    return dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados


def _equipes_logadas(dados: pd.DataFrame, coluna: str | None = None,
                     valor: str | None = None) -> float | None:
    if dados.empty:
        return None
    recorte = dados if coluna is None else dados[dados[coluna] == valor]
    return float(recorte["equipe"].replace("Não Informado", pd.NA).dropna().nunique())


def calcular(filtros: Filtros, periodo: Periodo | None = None,
             base: str = "implantacao") -> dict:
    periodo = periodo or resolver(filtros)
    base = base if base in BASES else "implantacao"

    termos = _do_mes("termos", filtros, periodo)
    vendas = _do_mes("vendas", filtros, periodo)
    implantacao = _do_mes("implantacao", filtros, periodo)
    programacao = _do_mes("programacao", filtros, periodo)

    indicadores = [
        nucleo.indicador_realizado(
            "equipes_servicos", "Equipes Logadas Serviços",
            _equipes_logadas(implantacao, "tipo", TIPO_SERVICOS),
            pergunta="Quantas equipes produziram em Serviços?",
            explicacao="Equipes distintas com implantação de Serviços no mês."),
        nucleo.indicador_realizado(
            "equipes_venda", "Equipes Logadas Venda", _equipes_logadas(vendas),
            pergunta="Quantas equipes venderam?",
            explicacao="Equipes distintas com venda registrada no mês."),
        nucleo.indicador_realizado(
            "equipes_vcg", "Equipes Logadas VCG",
            _equipes_logadas(implantacao, "tipo", TIPO_VCG),
            pergunta="Quantas equipes produziram em VCG?",
            explicacao="Equipes distintas com implantação VCG no mês."),
        nucleo.indicador_realizado(
            "equipes_programadas", "Equipes Programadas",
            nucleo.distintos(programacao, "equipe"),
            pergunta="Quantas equipes foram programadas?",
            explicacao="Recursos distintos na programação do mês."),
    ]

    tabela = _montar_tabela(termos, vendas, implantacao, base, filtros, periodo)
    ranking_base = {"implantacao": implantacao, "vendas": vendas, "termos": termos}[base]

    return {
        "titulo": "Desempenho das Equipes",
        "periodo": periodo.to_dict(),
        "base_selecionada": base,
        "bases": BASES,
        "tem_dados": bool(tabela),
        "indicadores": [i.to_dict() for i in indicadores],
        "tabela": tabela,
        "ranking": nucleo.ranking(ranking_base, "equipe", top=15).to_dict("records"),
        "producao_diaria": nucleo.evolucao_diaria(ranking_base).to_dict("records"),
        "por_frente": nucleo.ranking(ranking_base, "frente").to_dict("records")
                      if "frente" in ranking_base.columns else [],
    }


def _montar_tabela(termos, vendas, implantacao, base: str, filtros: Filtros,
                   periodo: Periodo) -> list[dict]:
    def soma_por_equipe(dados: pd.DataFrame) -> dict[str, float]:
        if dados.empty:
            return {}
        return (dados.groupby("equipe")["quantidade"].sum()).to_dict()

    def frente_por_equipe(dados: pd.DataFrame) -> dict[str, str]:
        if dados.empty or "frente" not in dados.columns:
            return {}
        return (dados.groupby("equipe")["frente"]
                .agg(lambda s: s.value_counts().idxmax())).to_dict()

    totais = {
        "termos": soma_por_equipe(termos),
        "vendas": soma_por_equipe(vendas),
        "implantacao": soma_por_equipe(implantacao),
    }
    frentes = {**frente_por_equipe(termos), **frente_por_equipe(vendas),
               **frente_por_equipe(implantacao)}

    equipes = sorted({e for mapa in totais.values() for e in mapa})
    modulo = MODULO_DA_BASE[base]

    linhas = []
    for equipe in equipes:
        realizado = totais[base].get(equipe)
        meta_equipe = metas.meta(
            modulo, periodo.ano, periodo.mes, "TOTAL",
            Filtros(**{**filtros.__dict__, "equipe": equipe}),
        )
        atingimento = (round(realizado / meta_equipe * 100, 1)
                       if realizado is not None and meta_equipe else None)
        linhas.append({
            "equipe": equipe,
            "frente": frentes.get(equipe, "Não Informado"),
            "termos": totais["termos"].get(equipe),
            "vendas": totais["vendas"].get(equipe),
            "implantacao": totais["implantacao"].get(equipe),
            "realizado": realizado,
            "meta": meta_equipe,
            "atingimento": atingimento,
            "media_dia": nucleo.media_diaria(realizado, periodo.dias_uteis_decorridos),
            "status": status_por_atingimento(atingimento),
            "mensagem_meta": None if meta_equipe is not None else "Meta não cadastrada",
        })
    linhas.sort(key=lambda linha: (linha["realizado"] is None, -(linha["realizado"] or 0)))
    return linhas
