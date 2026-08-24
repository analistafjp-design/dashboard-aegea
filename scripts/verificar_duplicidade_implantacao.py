"""Confere se alguma implantação está sendo contada mais de uma vez.

A medida oficial conta linhas (COUNTROWS de Ligação de Água finalizada), e a
chave única do fato é `data + matricula + servico + equipe`. Uma mesma
ligação, portanto, vira duas linhas contadas se aparecer na planilha com
serviço ou equipe diferentes — é exatamente esse caso que este script mede.

Uso:
    .venv\\Scripts\\python.exe scripts\\verificar_duplicidade_implantacao.py
    .venv\\Scripts\\python.exe scripts\\verificar_duplicidade_implantacao.py --mes 2026-08
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics import consultas  # noqa: E402


def _contadas(mes: str | None) -> pd.DataFrame:
    """As linhas que entram no total do painel."""
    dados = consultas.dados("implantacao")
    if dados.empty:
        return dados
    if "conta_realizado" in dados.columns:
        dados = dados[dados["conta_realizado"] == True]  # noqa: E712
    if mes:
        dados = dados[dados["ano_mes"] == mes]
    return dados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mes", help="Recorte AAAA-MM (padrão: todos os meses)")
    parser.add_argument("--listar", type=int, default=10,
                        help="Quantas matrículas repetidas detalhar (padrão: 10)")
    args = parser.parse_args()

    dados = _contadas(args.mes)
    if dados.empty:
        print("Nenhuma implantação contada na base para esse recorte.")
        return 0

    recorte = args.mes or "todos os meses"
    total = float(pd.to_numeric(dados["quantidade"], errors="coerce").fillna(1).sum())
    linhas = len(dados)

    print(f"Recorte ................. {recorte}")
    print(f"Total do painel ......... {total:.0f}")
    print(f"Linhas contadas ......... {linhas}")

    if "matricula" not in dados.columns:
        print("\nA base não tem matrícula; não dá para medir repetição.")
        return 0

    com_matricula = dados[dados["matricula"].notna()]
    sem_matricula = linhas - len(com_matricula)
    distintas = com_matricula["matricula"].nunique()
    excedente = len(com_matricula) - distintas

    print(f"Matrículas distintas .... {distintas}")
    if sem_matricula:
        print(f"Linhas sem matrícula .... {sem_matricula} (não dá para conferir)")

    if excedente <= 0:
        print("\nOK: cada matrícula é contada uma única vez.")
        return 0

    pct = excedente / total * 100 if total else 0
    print(f"\nATENÇÃO: {excedente} linha(s) a mais que matrículas distintas "
          f"({pct:.1f}% do total).")
    print("A mesma ligação está entrando mais de uma vez.\n")

    repetidas = (com_matricula.groupby("matricula").size()
                 .sort_values(ascending=False))
    repetidas = repetidas[repetidas > 1]
    print(f"{len(repetidas)} matrícula(s) repetida(s). "
          f"Detalhando as {min(args.listar, len(repetidas))} maiores:\n")

    colunas = [c for c in ("data", "cidade", "equipe", "frente", "servico")
               if c in dados.columns]
    for matricula in repetidas.head(args.listar).index:
        grupo = com_matricula[com_matricula["matricula"] == matricula]
        # Mostrar só o que difere entre as linhas explica por que a chave
        # única não as uniu.
        difere = [c for c in colunas if grupo[c].nunique(dropna=False) > 1]
        print(f"  matrícula {matricula}: {len(grupo)} linhas — "
              f"difere em {', '.join(difere) if difere else 'nada visível'}")
        print(grupo[colunas].to_string(index=False, max_rows=6))
        print()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
