"""Dashboard Executivo — aplicação FastAPI.

Execução local:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.analytics import cache
from app.config import config
from app.models.db import criar_banco
from app.routes import api, paginas
from app.utils.autenticacao import AutenticacaoBasicaMiddleware
from app.utils.erros import ErroDashboard
from app.utils.ativos import garantir_plotly
from app.utils.log import configurar_logs, get_logger

logger = get_logger("main")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    configurar_logs()
    logger.info("Iniciando %s v%s", config.APP_NOME, config.APP_VERSAO)
    if config.AUTENTICACAO_ATIVA:
        logger.info("Autenticação HTTP Basic ativa (usuário '%s')", config.AUTH_USUARIO)
    else:
        logger.warning(
            "Autenticação desativada — defina AUTH_USUARIO e AUTH_SENHA para exigir "
            "login (recomendado sempre que a URL for acessível publicamente)."
        )
    criar_banco()
    garantir_plotly()
    cache.invalidar()
    yield
    logger.info("Encerrando %s", config.APP_NOME)


app = FastAPI(
    title=config.APP_NOME,
    version=config.APP_VERSAO,
    description="Dashboard executivo consolidando Termos/Faturamento, "
                "Venda/Implantação e Programação Diária.",
    lifespan=ciclo_de_vida,
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(AutenticacaoBasicaMiddleware)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.include_router(api.router)
app.include_router(paginas.router)


@app.exception_handler(ErroDashboard)
async def erro_negocio(request: Request, erro: ErroDashboard):
    """Erro de negócio: mensagem clara, sem stack trace."""
    logger.warning("Erro de negócio em %s: %s", request.url.path, erro.mensagem)
    return JSONResponse(status_code=400, content=erro.to_dict())


@app.exception_handler(Exception)
async def erro_inesperado(request: Request, erro: Exception):
    """Qualquer falha não prevista vira log técnico + mensagem amigável."""
    logger.exception("Erro inesperado em %s", request.url.path)
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=500, content={
            "ok": False,
            "mensagem": "Ocorreu um erro interno. O problema foi registrado no log "
                        "do sistema para análise.",
        })
    return HTMLResponse(status_code=500, content=(
        "<h1>Ocorreu um erro interno</h1>"
        "<p>O problema foi registrado no log do sistema. "
        "<a href='/'>Voltar para a Visão Executiva</a></p>"
    ))
