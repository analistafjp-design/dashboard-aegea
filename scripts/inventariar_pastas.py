"""Lista as planilhas monitoradas e o que cada uma contém.

Serve para descobrir qual arquivo é a fonte certa quando o painel diverge do
Power BI: um export mensal consolidado e vários exports diários do mesmo mês
convivendo na pasta fazem o total ser somado mais de uma vez.

Uso:
    .venv\\Scripts\\python.exe scripts\\inventariar_pastas.py
    .venv\\Scripts\\python.exe scripts\\inventariar_pastas.py --mes 2026-08
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atualizar_dashboard_local import (  # noqa: E402
    carregar_pastas,
    encontrar_arquivos,
)

# Cabeçalhos possíveis para as colunas que interessam ao diagnóstico.
COLUNAS = {
    "data": ("data", "data da atividade", "data da implantacao", "data implantacao"),
    "matricula": ("matricula", "matrícula", "numero da conta", "número da conta"),
    "atividade": ("tipo de atividade",),
    "status": ("status da atividade",),
    "recurso": ("recurso", "equipe"),
}


def _coluna(df: pd.DataFrame, nomes: tuple[str, ...]) -> str | None:
    baixa = {str(c).strip().lower(): c for c in df.columns}
    for nome in nomes:
        if nome in baixa:
            return baixa[nome]
    return None


def _resumir(caminho: Path, mes: str | None) -> dict | None:
    try:
        df = pd.read_excel(caminho)
    except Exception as erro:  # noqa: BLE001 - queremos seguir para os demais
        return {"arquivo": caminho.name, "erro": str(erro)[:40]}
    if df.empty:
        return {"arquivo": caminho.name, "linhas": 0}

    col_data = _coluna(df, COLUNAS["data"])
    col_mat = _coluna(df, COLUNAS["matricula"])
    col_ativ = _coluna(df, COLUNAS["atividade"])

    if col_ativ is not None:
        eh_agua = df[col_ativ].astype(str).str.upper().str.contains(
            "LIGA", na=False) & df[col_ativ].astype(str).str.upper().str.contains(
            "GUA", na=False)
        df = df[eh_agua]
    if col_data is not None:
        datas = pd.to_datetime(df[col_data], errors="coerce")
        if mes:
            df = df[datas.dt.strftime("%Y-%m") == mes]
            datas = datas[datas.dt.strftime("%Y-%m") == mes]
    else:
        datas = pd.Series(dtype="datetime64[ns]")

    if df.empty:
        return None

    dias = datas.dt.date.nunique() if not datas.empty else 0
    return {
        "arquivo": caminho.name,
        "linhas": len(df),
        "matriculas": int(df[col_mat].nunique()) if col_mat else 0,
        "dias": int(dias),
        "de": str(datas.min().date()) if not datas.dropna().empty else "-",
        "ate": str(datas.max().date()) if not datas.dropna().empty else "-",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mes", help="Só as linhas deste mês (AAAA-MM)")
    parser.add_argument("--pastas", default="scripts/pastas-monitoradas.txt")
    args = parser.parse_args()

    config = Path(args.pastas)
    if not config.is_absolute():
        config = Path(__file__).resolve().parent.parent / config
    if not config.exists():
        print(f"Configuração não encontrada: {config}")
        return 1

    arquivos = encontrar_arquivos(carregar_pastas(config))
    candidatos = sorted(c for c, tipos in arquivos.items()
                        if not tipos or "implantacao" in tipos)
    print(f"Planilhas que podem alimentar a implantação: {len(candidatos)}")
    print(f"Recorte: {args.mes or 'todos os meses'}")
    print("Lendo cada arquivo — isso demora um pouco.\n")

    linhas = []
    for caminho in candidatos:
        resumo = _resumir(caminho, args.mes)
        if resumo:
            linhas.append(resumo)
    if not linhas:
        print("Nenhuma planilha com Ligação de Água no recorte.")
        return 0

    tabela = pd.DataFrame(linhas).sort_values("linhas", ascending=False)
    print(tabela.to_string(index=False))

    if "linhas" in tabela and "dias" in tabela:
        total = int(tabela["linhas"].sum())
        print(f"\nSoma de todas as planilhas: {total} linha(s)")
        # Um arquivo que cobre muitos dias é um consolidado; os de 1 dia são
        # fotografias diárias, e somá-las conta a mesma ordem várias vezes.
        consolidados = tabela[tabela["dias"] > 3]
        if not consolidados.empty and len(tabela) > len(consolidados):
            print("\nParecem consolidados (cobrem mais de 3 dias):")
            print(consolidados[["arquivo", "linhas", "dias", "de", "ate"]]
                  .to_string(index=False))
            print("\nOs demais cobrem 1 a 3 dias — são exports diários.")
            print("Manter os dois tipos na mesma pasta soma a produção "
                  "mais de uma vez.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
