#!/usr/bin/env python3
"""Importa planilhas pela linha de comando (mesma lógica da tela de upload).

Uso:
    python scripts/carregar_planilhas.py data/exemplos/*.xlsx
    python scripts/carregar_planilhas.py --tipo vendas caminho/venda_2026.xlsx
    python scripts/carregar_planilhas.py --limpar data/exemplos/*.xlsx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics import cache  # noqa: E402
from app.etl.datasets import DATASETS  # noqa: E402
from app.etl.pipeline import processar_lote  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.db import criar_banco, engine, sessao  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa planilhas para o dashboard")
    parser.add_argument("arquivos", nargs="+", help="Caminhos das planilhas")
    parser.add_argument("--tipo", choices=sorted(DATASETS), default=None,
                        help="Força o tipo de base (padrão: detectar pelas colunas)")
    parser.add_argument("--limpar", action="store_true",
                        help="Apaga todos os dados antes de importar")
    args = parser.parse_args()

    caminhos = [Path(a) for a in args.arquivos]
    ausentes = [c for c in caminhos if not c.exists()]
    if ausentes:
        print("Arquivo(s) não encontrado(s):", ", ".join(map(str, ausentes)))
        return 1

    if args.limpar:
        Base.metadata.drop_all(engine)
        print("Banco de dados limpo.")
    criar_banco()

    forcados = {c.name: args.tipo for c in caminhos} if args.tipo else {}
    with sessao() as s:
        resultados = processar_lote(s, caminhos, forcados)
    cache.invalidar()

    print()
    print(f"{'ARQUIVO':<32} {'BASE':<14} {'STATUS':<9} {'LIDOS':>7} {'NOVOS':>7} {'ATUAL.':>7}")
    print("-" * 82)
    for resultado in resultados:
        print(f"{resultado.arquivo[:31]:<32} {(resultado.dataset or '-'):<14} "
              f"{resultado.status:<9} {resultado.lidos:>7} {resultado.inseridos:>7} "
              f"{resultado.atualizados:>7}")
        for detalhe in resultado.detalhes:
            print(f"    · {detalhe}")
        if resultado.status == "ERRO":
            print(f"    ! {resultado.mensagem}")

    return 0 if all(r.ok for r in resultados) else 2


if __name__ == "__main__":
    raise SystemExit(main())
