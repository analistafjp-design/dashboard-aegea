"""Normalização de texto usada pelo ETL (nomes de colunas, cidades, equipes)."""
from __future__ import annotations

import re
import unicodedata


def sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def normalizar_coluna(nome: object) -> str:
    """'Data da Atividade ' -> 'data_da_atividade'."""
    texto = sem_acento(str(nome)).strip().lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return texto.strip("_")


def chave_comparacao(nome: object) -> str:
    """Versão agressiva usada só para casar sinônimos: remove separadores."""
    return normalizar_coluna(nome).replace("_", "")


def titulo(valor: object) -> str:
    """Padroniza um rótulo de dimensão: 'rio  bonito ' -> 'Rio Bonito'."""
    if valor is None:
        return ""
    texto = re.sub(r"\s+", " ", str(valor)).strip()
    if not texto:
        return ""
    return texto.title() if texto.isupper() or texto.islower() else texto


def slug(valor: object) -> str:
    return normalizar_coluna(valor)
