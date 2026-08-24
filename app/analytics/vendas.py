"""MÓDULO 2 — Venda (PBIX 2).

Equivalências: Medidas.Total Venda, Venda Comercial, Venda VCG,
Vendas Outros Canais, Venda por Dia, Falta Venda.
"""
from __future__ import annotations

from app.analytics import consultas, metas, nucleo
from app.analytics.base import Filtros
from app.analytics.dominio_tipos import CANAL_COMERCIAL, CANAL_OUTROS, CANAL_VCG
from app.analytics.periodo import Periodo, resolver


def _canal(dados, canal: str):
    return dados[dados["canal"] == canal] if "canal" in dados.columns else dados.iloc[0:0]


def _marcadas(dados, coluna: str, canal: str):
    """Linhas de uma medida do PBIX.

    Comercial e VCG se sobrepõem — a mesma venda pode contar nas duas —, por
    isso cada uma tem sua marca. Bases carregadas antes dessas colunas
    existirem caem no canal exclusivo antigo.
    """
    if coluna in dados.columns:
        return dados[dados[coluna] == True]  # noqa: E712
    return _canal(dados, canal)


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    todos = consultas.dados("vendas", Filtros(**{**filtros.__dict__, "ano": None, "mes": None}))
    dados = consultas.dados("vendas", filtros)
    do_mes = dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados

    # O total é a venda do Interior: Outros Canais vem de outra base e fica
    # de fora. Somar Comercial + VCG contaria duas vezes as vendas que
    # entram nas duas medidas, então o total conta as linhas uma só vez.
    def _sem_outros(base):
        return base[base["canal"] != CANAL_OUTROS] if not base.empty else base

    do_interior = _sem_outros(do_mes)
    interior_todos = _sem_outros(dados)   # histórico, para a evolução mensal
    total_venda = nucleo.total(do_interior)
    comercial = nucleo.total(_marcadas(do_mes, "conta_comercial", CANAL_COMERCIAL))
    vcg = nucleo.total(_marcadas(do_mes, "conta_vcg", CANAL_VCG))
    outros = nucleo.total(_canal(do_mes, CANAL_OUTROS))

    meta_total = metas.meta_total_composta("VENDA", periodo.ano, periodo.mes, filtros)
    meta_comercial = metas.meta("VENDA", periodo.ano, periodo.mes, "COMERCIAL", filtros)
    meta_vcg = metas.meta("VENDA", periodo.ano, periodo.mes, "VCG", filtros)

    _, anterior = nucleo.comparar_meses(_sem_outros(todos), periodo)
    bloco = nucleo.bloco_meta(total_venda, meta_total, periodo, "Venda Total")

    indicadores = [
        nucleo.indicador_realizado(
            "total_venda", "Total de Vendas", total_venda, meta_total, anterior,
            pergunta="Como está a venda no mês?",
            explicacao="Soma de todas as vendas do mês de referência."),
        nucleo.indicador_realizado(
            "venda_comercial", "Venda Comercial", comercial, meta_comercial,
            pergunta="Como está o canal Comercial?",
            explicacao="Vendas do canal Comercial."),
        nucleo.indicador_realizado(
            "venda_vcg", "Venda VCG", vcg, meta_vcg,
            pergunta="Como está o canal VCG?",
            explicacao="Vendas das frentes VCG (inclui Rio Bonito e Bairro Legal/SFI)."),
        nucleo.indicador_realizado(
            "venda_outros", "Outros Canais", outros,
            pergunta="Quanto vem de outros canais?",
            explicacao="Vendas que não são Comercial nem VCG."),
        nucleo.indicador_realizado(
            "venda_dia", "Venda por Dia", bloco["media_dia"], casas=1,
            pergunta="Qual o ritmo diário de venda?",
            explicacao="Total de vendas dividido pelos dias úteis decorridos."),
        nucleo.indicador_realizado(
            "falta_venda", "Falta para a Meta", bloco["falta"],
            pergunta="Quanto falta para bater a meta?",
            explicacao="Meta menos realizado (zero quando a meta já foi atingida)."),
    ]

    return {
        "modulo": "VENDA",
        "titulo": "Venda",
        "periodo": periodo.to_dict(),
        "tem_dados": not do_mes.empty,
        "indicadores": [i.to_dict() for i in indicadores],
        "bloco_principal": bloco,
        "blocos_meta": nucleo.matriz_meta([
            nucleo.bloco_meta(comercial, meta_comercial, periodo, "Comercial"),
            nucleo.bloco_meta(vcg, meta_vcg, periodo, "VCG"),
            nucleo.bloco_meta(outros, None, periodo, "Outros Canais"),
            bloco,
        ]),
        # Todo o restante acompanha o total: Outros Canais fora.
        "evolucao_mensal": nucleo.evolucao_mensal(interior_todos).to_dict("records"),
        "evolucao_diaria": nucleo.evolucao_diaria(do_interior).to_dict("records"),
        "por_frente": nucleo.ranking(do_interior, "frente").to_dict("records"),
        "por_cidade": nucleo.ranking(do_interior, "cidade", top=15).to_dict("records"),
        "top_cidades": nucleo.ranking(do_interior, "cidade", top=10).to_dict("records"),
        "top_equipes": nucleo.ranking(do_interior, "equipe", top=10).to_dict("records"),
        "valor_total": nucleo.total(do_interior, "valor"),
    }
