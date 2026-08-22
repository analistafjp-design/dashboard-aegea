"""Autenticação HTTP Basic opcional para toda a aplicação.

Desligada por padrão (desenvolvimento local): sem AUTH_USUARIO/AUTH_SENHA
configuradas, nenhuma rota pede senha. Quando as duas variáveis existem
(tipicamente em produção), toda rota exige login — exceto o healthcheck,
que o Render (ou qualquer orquestrador) precisa conseguir chamar sem
credenciais para saber se o serviço está de pé.
"""
from __future__ import annotations

import base64
import binascii
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import config

ROTAS_PUBLICAS = {"/api/status"}


def _credenciais_validas(cabecalho: str | None) -> bool:
    if not cabecalho or not cabecalho.startswith("Basic "):
        return False
    try:
        decodificado = base64.b64decode(cabecalho[6:]).decode("utf-8")
        usuario, _, senha = decodificado.partition(":")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    # compare_digest evita vazar, por tempo de resposta, quantos caracteres
    # da senha estão corretos.
    usuario_ok = secrets.compare_digest(usuario, config.AUTH_USUARIO)
    senha_ok = secrets.compare_digest(senha, config.AUTH_SENHA)
    return usuario_ok and senha_ok


class AutenticacaoBasicaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, chamar_proximo):
        if not config.AUTENTICACAO_ATIVA or request.url.path in ROTAS_PUBLICAS:
            return await chamar_proximo(request)

        if not _credenciais_validas(request.headers.get("authorization")):
            return Response(
                status_code=401,
                content="Login necessário para acessar o Dashboard Executivo.",
                headers={"WWW-Authenticate": 'Basic realm="Dashboard Executivo"'},
            )
        return await chamar_proximo(request)
