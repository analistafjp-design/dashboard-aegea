"""Sistema de logs da aplicação.

Regra do projeto: o usuário final nunca vê stack trace. Toda exceção é
registrada em arquivo com detalhe técnico e devolvida à interface como
mensagem em português.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys

from app.config import config

_CONFIGURADO = False
FORMATO = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"


def configurar_logs() -> None:
    global _CONFIGURADO
    if _CONFIGURADO:
        return

    raiz = logging.getLogger("dashboard")
    raiz.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    raiz.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(FORMATO))
    raiz.addHandler(console)

    arquivo = logging.handlers.RotatingFileHandler(
        config.LOG_DIR / "dashboard.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    arquivo.setFormatter(logging.Formatter(FORMATO))
    raiz.addHandler(arquivo)

    raiz.propagate = False
    _CONFIGURADO = True


def get_logger(nome: str) -> logging.Logger:
    configurar_logs()
    return logging.getLogger(f"dashboard.{nome}")
