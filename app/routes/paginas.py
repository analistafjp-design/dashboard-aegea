"""Rotas das páginas HTML (com suporte a navegação sem recarregar)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.analytics import consultas, painel
from app.analytics.base import Filtros
from app.config import config
from app.schemas.filtros import filtros_da_query
from app.services import configuracoes as servico_config
from app.utils.formato import data_hora_br

router = APIRouter(tags=["páginas"])
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))

ROTAS = [
    {"rota": "/", "chave": "home", "titulo": "Venda e Implantação", "icone": "home", "grupo": "Painéis"},
    {"rota": "/termos", "chave": "termos", "titulo": "Termos Aplicados", "icone": "termos",
     "grupo": "Termos / Faturamento"},
    {"rota": "/faturamento", "chave": "faturamento", "titulo": "Faturamento de Termos",
     "icone": "faturamento", "grupo": "Termos / Faturamento"},
    {"rota": "/vendas", "chave": "vendas", "titulo": "Venda", "icone": "venda",
     "grupo": "Venda / Implantação"},
    {"rota": "/implantacao", "chave": "implantacao", "titulo": "Implantação", "icone": "implantacao",
     "grupo": "Venda / Implantação"},
    {"rota": "/programacao", "chave": "programacao", "titulo": "Programação Diária",
     "icone": "programacao", "grupo": "Programação"},
    {"rota": "/equipes", "chave": "equipes", "titulo": "Equipes", "icone": "equipes",
     "grupo": "Análise"},
    {"rota": "/cidades", "chave": "cidades", "titulo": "Cidades", "icone": "cidades",
     "grupo": "Análise"},
    {"rota": "/metas", "chave": "metas", "titulo": "Metas", "icone": "metas", "grupo": "Análise"},
    {"rota": "/analises", "chave": "analises", "titulo": "Análises", "icone": "analises",
     "grupo": "Análise"},
    {"rota": "/alertas", "chave": "alertas", "titulo": "Alertas", "icone": "alertas",
     "grupo": "Análise"},
    {"rota": "/atualizacao", "chave": "atualizacao", "titulo": "Atualização de Dados",
     "icone": "upload", "grupo": "Sistema"},
    {"rota": "/configuracoes", "chave": "configuracoes", "titulo": "Configurações",
     "icone": "config", "grupo": "Sistema"},
]

# Menu enxuto para o uso diário. As demais rotas continuam disponíveis por
# endereço direto e para exportações, mas não poluem a navegação principal.
MENU = [item for item in ROTAS if item["chave"] in {
    "home", "termos"
}]

TITULOS = {item["chave"]: item["titulo"] for item in ROTAS}


def _contexto(request: Request, pagina: str, filtros: Filtros, fragmento: bool) -> dict:
    ultima = consultas.ultima_atualizacao()
    return {
        "request": request,
        "pagina": pagina,
        "titulo_pagina": TITULOS.get(pagina, "Dashboard"),
        "menu": MENU,
        "fragmento": fragmento,
        "app_nome": config.APP_NOME,
        "app_versao": config.APP_VERSAO,
        "ultima_atualizacao": data_hora_br(ultima) if ultima is not None else "Sem importações",
        "tem_dados": consultas.ha_dados(),
        "opcoes": painel.opcoes_filtros(),
        "filtros": filtros,
        "descricao_filtros": " | ".join(filtros.descricao()),
        "configuracoes": servico_config.ler_todas(),
    }


def _pagina(nome: str, template: str):
    async def rota(request: Request,
                   filtros: Filtros = Depends(filtros_da_query),
                   fragmento: int = Query(0)) -> HTMLResponse:
        contexto = _contexto(request, nome, filtros, bool(fragmento))
        return templates.TemplateResponse(request, template, contexto)

    return rota


for item in ROTAS:
    router.add_api_route(
        item["rota"],
        _pagina(item["chave"], f"paginas/{item['chave']}.html"),
        methods=["GET"],
        response_class=HTMLResponse,
        name=f"pagina_{item['chave']}",
        include_in_schema=False,
    )

router.add_api_route(
    "/dicionario",
    _pagina("dicionario", "paginas/dicionario.html"),
    methods=["GET"], response_class=HTMLResponse, name="pagina_dicionario",
    include_in_schema=False,
)

router.add_api_route(
    "/relatorio-geral",
    _pagina("relatorio_geral", "paginas/relatorio_geral.html"),
    methods=["GET"], response_class=HTMLResponse, name="relatorio_geral",
    include_in_schema=False,
)
