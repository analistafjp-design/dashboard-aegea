"""Ponto único de montagem dos dados do dashboard (com cache)."""
from __future__ import annotations

from app.analytics import (
    cache,
    cidades as mod_cidades,
    consultas,
    equipes as mod_equipes,
    faturamento as mod_faturamento,
    home as mod_home,
    implantacao as mod_implantacao,
    programacao as mod_programacao,
    termos as mod_termos,
    vendas as mod_vendas,
)
from app.analytics.base import Filtros
from app.analytics.periodo import Periodo, resolver

CALCULADORES = {
    "termos": mod_termos.calcular,
    "faturamento": mod_faturamento.calcular,
    "vendas": mod_vendas.calcular,
    "implantacao": mod_implantacao.calcular,
    "programacao": mod_programacao.calcular,
    "cidades": mod_cidades.calcular,
}


def modulo(nome: str, filtros: Filtros, periodo: Periodo | None = None, **extras) -> dict:
    periodo = periodo or resolver(filtros)
    chave = f"modulo:{nome}:{filtros.chave_cache()}:{periodo.ano_mes}:{extras}"

    def calcular() -> dict:
        if nome == "equipes":
            return mod_equipes.calcular(filtros, periodo, **extras)
        return CALCULADORES[nome](filtros, periodo)

    return cache.obter(chave, calcular)


def todos(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    payloads = {nome: modulo(nome, filtros, periodo) for nome in CALCULADORES}
    payloads["equipes"] = modulo("equipes", filtros, periodo)
    return payloads


def home(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    chave = f"home:{filtros.chave_cache()}:{periodo.ano_mes}"
    return cache.obter(chave, lambda: mod_home.montar(todos(filtros, periodo), filtros, periodo))


def opcoes_filtros() -> dict:
    """Valores existentes nos dados para alimentar os filtros globais."""
    return {
        "anos": consultas.anos_disponiveis(),
        "cidades": consultas.valores_dimensao("cidade"),
        "frentes": consultas.valores_dimensao("frente"),
        "equipes": consultas.valores_dimensao("equipe"),
        "regioes": consultas.valores_dimensao("regiao"),
        "projetos": consultas.valores_dimensao("projeto"),
        "setores": consultas.valores_dimensao("setor"),
    }
