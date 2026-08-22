#!/usr/bin/env python3
"""Compara os indicadores calculados em Python com os valores do Power BI.

Preencha `docs/referencia_powerbi.csv` com os números lidos nos três PBIX
para um mês fechado e rode este script. Ele imprime a tabela de conferência
e devolve código de saída 2 se houver divergência acima da tolerância.

Uso:
    python scripts/validar_indicadores.py --ano 2026 --mes 7
    python scripts/validar_indicadores.py --referencia docs/referencia_powerbi.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics import painel  # noqa: E402
from app.analytics.base import Filtros  # noqa: E402
from app.utils.formato import numero  # noqa: E402

TOLERANCIA_PADRAO = 0.0


def valor_calculado(modulo: str, indicador: str, filtros: Filtros) -> float | None:
    """Busca o indicador no payload do módulo correspondente."""
    if modulo == "home":
        dados = painel.home(filtros)
        card = next((c for c in dados["cards"] if c["chave"] == indicador), None)
        return card["valor"] if card else None

    dados = painel.modulo(modulo, filtros)
    item = next((i for i in dados.get("indicadores", []) if i["chave"] == indicador), None)
    if item is not None:
        return item["valor"]
    bloco = dados.get("bloco_principal") or {}
    return bloco.get(indicador)


def main() -> int:
    parser = argparse.ArgumentParser(description="Conferência Power BI x Python")
    parser.add_argument("--referencia", default="docs/referencia_powerbi.csv")
    parser.add_argument("--ano", type=int, default=None)
    parser.add_argument("--mes", type=int, default=None)
    parser.add_argument("--tolerancia", type=float, default=TOLERANCIA_PADRAO,
                        help="Diferença absoluta aceita (padrão: 0)")
    args = parser.parse_args()

    arquivo = Path(args.referencia)
    if not arquivo.exists():
        print(f"Arquivo de referência não encontrado: {arquivo}")
        print("Preencha o modelo em docs/referencia_powerbi.csv com os valores dos PBIX.")
        return 1

    with arquivo.open(encoding="utf-8-sig", newline="") as origem:
        linhas = [l for l in csv.DictReader(origem, delimiter=";")
                  if l.get("indicador") and not l["indicador"].startswith("#")]

    if not linhas:
        print("Nenhuma linha preenchida em", arquivo)
        return 1

    print(f"\n{'INDICADOR':<34} {'POWER BI':>12} {'PYTHON':>12} {'DIFERENÇA':>12}  STATUS")
    print("-" * 88)

    divergencias = 0
    for linha in linhas:
        ano = args.ano or int(linha.get("ano") or 0)
        mes = args.mes or int(linha.get("mes") or 0)
        filtros = Filtros(ano=ano or None, mes=mes or None,
                          cidade=(linha.get("cidade") or None) or None)
        try:
            calculado = valor_calculado(linha["modulo"], linha["indicador"], filtros)
        except Exception as erro:  # noqa: BLE001 - relatório não pode parar
            print(f"{linha['indicador']:<34} {'-':>12} {'ERRO':>12} {'-':>12}  {erro}")
            divergencias += 1
            continue

        esperado = float(str(linha["valor_powerbi"]).replace(".", "").replace(",", "."))
        if calculado is None:
            print(f"{linha['indicador']:<34} {numero(esperado):>12} {'sem dados':>12} "
                  f"{'-':>12}  DIVERGENTE")
            divergencias += 1
            continue

        diferenca = calculado - esperado
        ok = abs(diferenca) <= args.tolerancia
        divergencias += 0 if ok else 1
        print(f"{linha['indicador']:<34} {numero(esperado):>12} {numero(calculado):>12} "
              f"{numero(diferenca):>12}  {'OK' if ok else 'DIVERGENTE'}")

    print("-" * 88)
    print(f"{len(linhas)} indicador(es) conferido(s), {divergencias} divergência(s).\n")
    if divergencias:
        print("Investigue a regra do indicador antes de considerar o projeto concluído.")
    return 2 if divergencias else 0


if __name__ == "__main__":
    raise SystemExit(main())
