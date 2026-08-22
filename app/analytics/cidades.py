"""Ranking e desempenho por cidade.

Fontes: Interior.Cidade (venda/implantação), Faturamento Termos.
d_Cadastro.CIDADE (faturamento) e a cidade da base de termos.
Cada módulo é ranqueado separadamente — nada é somado entre módulos.
"""
from __future__ import annotations

import pandas as pd

from app.analytics import consultas, metas, nucleo
from app.analytics.base import Filtros, status_por_atingimento
from app.analytics.dominio_tipos import SIT_FATURADO
from app.analytics.periodo import Periodo, resolver


def _do_mes(nome: str, filtros: Filtros, periodo: Periodo) -> pd.DataFrame:
    dados = consultas.dados(nome, filtros)
    return dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)

    termos = _do_mes("termos", filtros, periodo)
    vendas = _do_mes("vendas", filtros, periodo)
    implantacao = _do_mes("implantacao", filtros, periodo)
    faturamento = _do_mes("faturamento", filtros, periodo)
    faturados = (faturamento[faturamento["situacao"] == SIT_FATURADO]
                 if not faturamento.empty else faturamento)

    tabela = _tabela(termos, vendas, implantacao, faturados, filtros, periodo)
    abaixo = [linha for linha in tabela
              if linha["atingimento"] is not None and linha["atingimento"] < 100]
    abaixo.sort(key=lambda linha: linha["atingimento"])

    return {
        "titulo": "Cidades",
        "periodo": periodo.to_dict(),
        "tem_dados": bool(tabela),
        "tabela": tabela,
        "maior_venda": nucleo.ranking(vendas, "cidade", top=10).to_dict("records"),
        "maior_implantacao": nucleo.ranking(implantacao, "cidade", top=10).to_dict("records"),
        "maior_faturamento": nucleo.ranking(faturados, "cidade", top=10).to_dict("records"),
        "maior_termos": nucleo.ranking(termos, "cidade", top=10).to_dict("records"),
        "melhor_desempenho": [linha for linha in tabela
                              if linha["atingimento"] is not None][:10],
        "abaixo_da_meta": abaixo[:10],
        "cidades": sorted({linha["cidade"] for linha in tabela}),
    }


def _tabela(termos, vendas, implantacao, faturados, filtros: Filtros,
            periodo: Periodo) -> list[dict]:
    def soma(dados: pd.DataFrame, coluna: str = "quantidade") -> dict[str, float]:
        if dados.empty or "cidade" not in dados.columns:
            return {}
        return dados.groupby("cidade")[coluna].sum().to_dict()

    mapas = {
        "termos": soma(termos), "vendas": soma(vendas),
        "implantacao": soma(implantacao), "faturamento": soma(faturados),
    }
    cidades = sorted({c for mapa in mapas.values() for c in mapa})

    linhas = []
    for cidade in cidades:
        realizado = mapas["implantacao"].get(cidade)
        meta_cidade = metas.meta(
            "IMPLANTACAO", periodo.ano, periodo.mes, "TOTAL",
            Filtros(**{**filtros.__dict__, "cidade": cidade}),
        )
        atingimento = (round(realizado / meta_cidade * 100, 1)
                       if realizado is not None and meta_cidade else None)
        linhas.append({
            "cidade": cidade,
            "termos": mapas["termos"].get(cidade),
            "vendas": mapas["vendas"].get(cidade),
            "implantacao": realizado,
            "faturamento": mapas["faturamento"].get(cidade),
            "meta": meta_cidade,
            "atingimento": atingimento,
            "status": status_por_atingimento(atingimento),
            "mensagem_meta": None if meta_cidade is not None else "Meta não cadastrada",
        })
    linhas.sort(key=lambda linha: -(linha["implantacao"] or linha["vendas"] or 0))
    return linhas
