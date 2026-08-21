"""Cache em memória com invalidação por versão dos dados.

Toda carga de dados chama `invalidar()`; o dashboard nunca serve número
velho depois de um upload.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from app.config import config
from app.utils.log import get_logger

logger = get_logger("cache")

_lock = threading.Lock()
_versao = 0
_itens: dict[str, tuple[int, float, Any]] = {}


def versao_atual() -> int:
    return _versao


def invalidar() -> None:
    """Marca todo o cache como obsoleto (chamado após cada carga)."""
    global _versao
    with _lock:
        _versao += 1
        _itens.clear()
    logger.info("Cache invalidado (versão %s)", _versao)


def obter(chave: str, produtor: Callable[[], Any]) -> Any:
    agora = time.time()
    with _lock:
        entrada = _itens.get(chave)
        if entrada and entrada[0] == _versao and agora - entrada[1] < config.CACHE_TTL:
            return entrada[2]
    valor = produtor()
    with _lock:
        _itens[chave] = (_versao, agora, valor)
    return valor


def estatisticas() -> dict:
    return {"versao": _versao, "itens": len(_itens), "ttl_segundos": config.CACHE_TTL}
