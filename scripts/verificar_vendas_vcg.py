"""Abre a composição de Venda Comercial e Venda VCG por código.

Mostra de onde vem cada unidade das duas medidas — equipe, tipo de atividade
e código — para decidir qual grupo deve entrar em cada uma sem depender de
leitura de tela.

Uso:
    .venv\\Scripts\\python.exe scripts\\verificar_vendas_vcg.py --mes 2026-08
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics import consultas  # noqa: E402
from app.etl.regras_powerbi import EQUIPES_VCG, _texto  # noqa: E402
from app.models.db import criar_banco  # noqa: E402


def _codigo(valor: object) -> str:
    """Só o número do Código/Descrição: 313001, 113001..."""
    texto = _texto(valor)
    if not texto:
        return "(sem codigo)"
    return texto.split("-", 1)[0].strip() or "(sem codigo)"


def _grupo_equipe(valor: object) -> str:
    texto = _texto(valor)
    for prefixo in EQUIPES_VCG:
        if prefixo in texto:
            return prefixo
    return "(equipe comum)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mes", help="Recorte AAAA-MM (padrão: todos)")
    args = parser.parse_args()

    # O banco pode ter sido criado por uma versão anterior; alinhar as colunas
    # antes evita quebrar com "no such column".
    criar_banco()
    dados = consultas.dados("vendas")
    if args.mes and not dados.empty:
        dados = dados[dados["ano_mes"] == args.mes]
    if dados.empty:
        print("Nenhuma venda no recorte.")
        return 0

    if "conta_vcg" not in dados.columns or "codigo_descricao" not in dados.columns:
        print("A base ainda nao tem as colunas de auditoria.")
        print("Rode ATUALIZAR_DASHBOARD.cmd antes deste script.")
        return 1

    interior = dados[dados["canal"] != "OUTROS"].copy()
    comercial = int(interior["conta_comercial"].sum())
    vcg = int(interior["conta_vcg"].sum())
    ambas = int((interior["conta_comercial"] & interior["conta_vcg"]).sum())

    print(f"Recorte ............. {args.mes or 'todos os meses'}")
    print(f"Linhas do Interior .. {len(interior)}")
    print(f"Outros Canais ....... {len(dados) - len(interior)}")
    print()
    print(f"Venda Comercial ..... {comercial}")
    print(f"Venda VCG ........... {vcg}")
    print(f"  nas duas medidas .. {ambas}")
    print()

    interior["grupo"] = interior["equipe"].map(_grupo_equipe)
    interior["codigo"] = interior["codigo_descricao"].map(_codigo)
    interior["atividade"] = interior["tipo_atividade"].map(
        lambda v: _texto(v)[:34] or "(sem tipo)")

    print("=" * 78)
    print("COMPOSICAO — cada grupo e o que ele soma em cada medida")
    print("=" * 78)
    resumo = (
        interior.groupby(["grupo", "codigo", "atividade"], as_index=False)
        .agg(linhas=("quantidade", "size"),
             comercial=("conta_comercial", "sum"),
             vcg=("conta_vcg", "sum"))
        .sort_values(["grupo", "vcg", "linhas"], ascending=[True, False, False])
    )
    print(resumo.to_string(index=False))
    print()
    print("Leitura: 'linhas' e quanto existe na base; 'comercial' e 'vcg' sao")
    print("quantas dessas linhas cada medida conta hoje.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
