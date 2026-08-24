#!/usr/bin/env python3
"""Apaga e reconstrói somente Implantação a partir das fontes atuais."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import delete

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROJETO))

from app.analytics import cache, consultas  # noqa: E402
from app.analytics.base import Filtros  # noqa: E402
from app.analytics.implantacao import _realizadas_unicas  # noqa: E402
from app.etl.carga import carregar  # noqa: E402
from app.etl.datasets import IMPLANTACAO  # noqa: E402
from app.etl.deteccao import analisar_arquivo  # noqa: E402
from app.etl.transformacao import transformar  # noqa: E402
from app.models.db import criar_banco, sessao  # noqa: E402
from app.models.tabelas import FatoImplantacao  # noqa: E402
from scripts.atualizar_dashboard_local import (  # noqa: E402
    PastaMonitorada,
    encontrar_arquivos,
    invalidar_cache_do_painel,
    selecionar_fontes_implantacao,
)


def _fontes_atuais(pasta: Path) -> list[Path]:
    encontrados = encontrar_arquivos([
        PastaMonitorada(pasta, ("implantacao",)),
    ])
    selecionados = selecionar_fontes_implantacao(encontrados)
    return sorted(
        caminho for caminho, tipos in selecionados.items()
        if "implantacao" in tipos
    )


def _preparar(fontes: list[Path]) -> list[tuple[Path, pd.DataFrame]]:
    preparados: list[tuple[Path, pd.DataFrame]] = []
    for fonte in fontes:
        identificacao = analisar_arquivo(fonte, "implantacao")
        dados, validacao = transformar(identificacao)
        if dados.empty:
            raise RuntimeError(f"Nenhuma implantação válida em: {fonte.name}")
        print(
            f"Validado: {fonte.name} - {validacao.linhas_validas} linha(s) válida(s)."
        )
        preparados.append((fonte, dados))
    return preparados


def _resumo(dados: pd.DataFrame) -> dict[str, dict[str, int]]:
    unicas = _realizadas_unicas(dados)
    if unicas.empty:
        return {}
    resumo: dict[str, dict[str, int]] = {}
    for (ano_mes, tipo), grupo in unicas.groupby(["ano_mes", "tipo"]):
        resumo.setdefault(str(ano_mes), {})[str(tipo)] = int(grupo["quantidade"].sum())
    return resumo


def executar(pasta: Path) -> int:
    pasta = pasta.expanduser().resolve()
    if not pasta.is_dir():
        print(f"ERRO: pasta Interior não encontrada: {pasta}")
        return 1

    fontes = _fontes_atuais(pasta)
    if not fontes:
        print("ERRO: nenhum arquivo próprio de implantação foi encontrado.")
        return 1

    print("Fontes que serão usadas:")
    for fonte in fontes:
        print(f"  - {fonte.name}")

    # Tudo é validado antes do DELETE. Se uma planilha estiver inválida, o
    # banco atual permanece intacto.
    preparados = _preparar(fontes)
    combinado = pd.concat([dados for _, dados in preparados], ignore_index=True)
    esperado = _resumo(combinado)
    tipos = {
        tipo for por_tipo in esperado.values() for tipo in por_tipo
    }
    if not {"SERVICOS", "VCG"}.issubset(tipos):
        print(
            "ERRO: as fontes não produziram as duas frentes esperadas "
            "(SERVICOS e VCG). Nada foi apagado."
        )
        return 1

    criar_banco()
    with sessao() as banco:
        apagados = banco.query(FatoImplantacao).count()
        banco.execute(delete(FatoImplantacao))
        inseridos = 0
        for fonte, dados in preparados:
            inseridos += carregar(
                banco, IMPLANTACAO, dados=dados, arquivo=fonte.name
            ).inseridos

    cache.invalidar()
    invalidar_cache_do_painel()

    conferido = _resumo(consultas.dados("implantacao", Filtros()))
    if conferido != esperado:
        print(f"ERRO: conferência divergente. Esperado={esperado}; banco={conferido}")
        return 2

    print(f"Registros antigos apagados: {apagados}")
    print(f"Registros atuais carregados: {inseridos}")
    for ano_mes, por_tipo in sorted(conferido.items()):
        servicos = por_tipo.get("SERVICOS", 0)
        vcg = por_tipo.get("VCG", 0)
        print(
            f"{ano_mes}: Serviços={servicos}; VCG={vcg}; Geral={servicos + vcg}"
        )
    print("IMPLANTAÇÃO RECONSTRUÍDA E CONFERIDA COM SUCESSO.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apaga e reconstrói somente a tabela de implantação."
    )
    parser.add_argument("--pasta-interior", required=True, type=Path)
    args = parser.parse_args()
    return executar(args.pasta_interior)


if __name__ == "__main__":
    raise SystemExit(main())
