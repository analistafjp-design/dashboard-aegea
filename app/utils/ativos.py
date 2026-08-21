"""Provisionamento do Plotly local.

O dashboard não usa CDN: o `plotly.min.js` é servido pela própria aplicação.
O arquivo vem do pacote `plotly` já instalado pelo requirements.txt e é
copiado para `frontend/static/js/` na primeira execução — assim o repositório
não precisa versionar 4,7 MB de biblioteca e o sistema funciona offline.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from app.config import config
from app.utils.log import get_logger

logger = get_logger("ativos")

DESTINO = config.STATIC_DIR / "js" / "plotly.min.js"


def origem_plotly() -> Path | None:
    try:
        import plotly
    except ImportError:  # pragma: no cover - dependência obrigatória
        return None
    caminho = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    return caminho if caminho.exists() else None


def garantir_plotly() -> bool:
    """Copia o plotly.min.js para os estáticos se ainda não estiver lá."""
    if DESTINO.exists() and DESTINO.stat().st_size > 100_000:
        return True

    origem = origem_plotly()
    if origem is None:
        logger.error(
            "plotly.min.js não encontrado no pacote 'plotly'. Os gráficos não serão "
            "exibidos. Execute: pip install -r requirements.txt"
        )
        return False

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, DESTINO)
    logger.info("plotly.min.js provisionado em %s (%.1f MB)",
                DESTINO, DESTINO.stat().st_size / 1024 / 1024)
    return True
