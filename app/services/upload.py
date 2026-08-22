"""Recebimento seguro dos arquivos enviados pelo navegador."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from app.config import config
from app.utils.erros import ErroValidacaoArquivo
from app.utils.log import get_logger

logger = get_logger("upload")

TAMANHO_BLOCO = 1024 * 1024

# Carimbo AAAAMMDD_HHMMSS_ que `salvar()` põe na frente do arquivo em disco
# para dois envios do mesmo nome não se sobrescreverem.
_CARIMBO = re.compile(r"^\d{8}_\d{6}_")


def nome_exibicao(nome: str) -> str:
    """Nome como o usuário conhece — sem o carimbo de data/hora interno.

    O arquivo em disco precisa do carimbo para não colidir, mas mostrar
    "20260822_102235_Atividades-INTERIOR_01_08_26.xlsx" na tela de
    progresso e no histórico só confunde quem enviou.
    """
    return _CARIMBO.sub("", nome)


def nome_seguro(nome: str) -> str:
    """Remove caminho, acentos e caracteres perigosos do nome do arquivo."""
    base = Path(nome).name
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return base or "arquivo.xlsx"


async def salvar(arquivo: UploadFile) -> Path:
    """Grava o upload em disco validando extensão e tamanho durante a escrita."""
    nome = nome_seguro(arquivo.filename or "")
    extensao = Path(nome).suffix.lower()
    if extensao not in config.EXTENSOES_PERMITIDAS:
        permitidas = ", ".join(sorted(config.EXTENSOES_PERMITIDAS))
        raise ErroValidacaoArquivo(
            f"O arquivo '{nome}' não é aceito. Envie um arquivo {permitidas}.")

    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = config.UPLOAD_DIR / f"{carimbo}_{nome}"
    limite = config.TAMANHO_MAXIMO_MB * 1024 * 1024
    total = 0

    try:
        with destino.open("wb") as saida:
            while bloco := await arquivo.read(TAMANHO_BLOCO):
                total += len(bloco)
                if total > limite:
                    saida.close()
                    destino.unlink(missing_ok=True)
                    raise ErroValidacaoArquivo(
                        f"O arquivo '{nome}' passa de {config.TAMANHO_MAXIMO_MB} MB.")
                saida.write(bloco)
    finally:
        await arquivo.close()

    if total == 0:
        destino.unlink(missing_ok=True)
        raise ErroValidacaoArquivo(f"O arquivo '{nome}' está vazio.")

    logger.info("Upload recebido: %s (%.1f KB)", destino.name, total / 1024)
    return destino
