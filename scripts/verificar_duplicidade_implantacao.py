"""Confere se alguma implantação está sendo contada mais de uma vez.

A medida oficial conta `Cód. Protocolo Origem` distintos, e a chave única do
fato é `data + matricula + servico + equipe`. Uma mesma ligação, portanto,
vira várias linhas na base quando é lançada em outra data ou por outra
equipe — este script mostra quantas são e de que arquivo vieram.

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
from app.models.db import criar_banco  # noqa: E402


def _contadas(mes: str | None) -> pd.DataFrame:
    """As linhas que entram no total do painel."""
    # O banco pode ter sido criado por uma versão anterior. Sem alinhar as
    # colunas primeiro, a consulta quebra com "no such column".
    criar_banco()
    dados = consultas.dados("implantacao")
    if dados.empty:
        return dados
    if "conta_realizado" in dados.columns:
        dados = dados[dados["conta_realizado"] == True]  # noqa: E712
    if mes:
        dados = dados[dados["ano_mes"] == mes]
    return dados


def _por_mes() -> None:
    """Quanto cada mês tem, por frente — a base inteira, sem recorte.

    Responde de imediato se um total alto é a soma de vários meses ou se
    está concentrado num mês só.
    """
    criar_banco()
    dados = consultas.dados("implantacao")
    if dados.empty:
        print("Base de implantação vazia.")
        return
    if "conta_realizado" in dados.columns:
        dados = dados[dados["conta_realizado"] == True]  # noqa: E712
    if dados.empty:
        print("Nenhuma implantação finalizada na base.")
        return

    identificador = next(
        (c for c in ("matricula", "protocolo")
         if c in dados.columns and dados[c].notna().any()), None)

    print("IMPLANTAÇÃO POR MÊS (base inteira, só finalizadas)")
    print("=" * 62)
    colunas = ["ano_mes"] + (["frente"] if "frente" in dados.columns else [])
    agregacoes = {"linhas": ("ano_mes", "size")}
    if identificador:
        agregacoes["distintos"] = (identificador, "nunique")
    resumo = (dados.groupby(colunas, as_index=False)
              .agg(**agregacoes)
              .sort_values(colunas))
    print(resumo.to_string(index=False))

    print("\nTotal por mês:")
    total = dados.groupby("ano_mes", as_index=False).agg(**agregacoes).sort_values("ano_mes")
    print(total.to_string(index=False))
    print(f"\nMeses na base: {dados['ano_mes'].nunique()} "
          f"({dados['ano_mes'].min()} a {dados['ano_mes'].max()})")
    if identificador:
        print(f"Identificador usado na contagem distinta: {identificador}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mes", help="Recorte AAAA-MM (padrão: todos os meses)")
    parser.add_argument("--por-mes", action="store_true",
                        help="Mostra quanto cada mês tem, por frente, e encerra")
    parser.add_argument("--listar", type=int, default=10,
                        help="Quantos identificadores repetidos detalhar (padrão: 10)")
    parser.add_argument("--resumo", action="store_true",
                        help="Só os números, sem o detalhe linha a linha")
    args = parser.parse_args()

    if args.por_mes:
        _por_mes()
        return 0

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

    # A medida do PBIX conta Cód. Protocolo Origem; a matrícula só entra
    # quando a planilha não traz o protocolo.
    identificador = next(
        (c for c in ("protocolo", "matricula")
         if c in dados.columns and dados[c].notna().any()), None)
    if identificador is None:
        print("\nA base não tem protocolo nem matrícula; não dá para medir repetição.")
        return 0
    print(f"Identificador ........... {identificador}")

    # De onde vêm as linhas: mais de um arquivo alimentando a mesma frente é
    # a explicação usual para o painel divergir de uma planilha isolada.
    if "origem_arquivo" in dados.columns:
        print("\nPor arquivo de origem:")
        origem = (dados.groupby("origem_arquivo", as_index=False)
                  .agg(linhas=(identificador, "size"),
                       distintos=(identificador, "nunique"))
                  .sort_values("linhas", ascending=False))
        print(origem.to_string(index=False))

    if "frente" in dados.columns:
        # É por Frente que as medidas recortam. Um total de VCG muito acima do
        # esperado costuma ser frente classificada errada, não fórmula.
        print("\nPor frente (é assim que as medidas recortam):")
        frente = (dados.groupby("frente", as_index=False)
                  .agg(linhas=(identificador, "size"),
                       distintos=(identificador, "nunique"))
                  .sort_values("linhas", ascending=False))
        print(frente.to_string(index=False))

    if "data" in dados.columns and dados["data"].notna().any():
        # Datas fora do mês recortado indicam ano_mes gravado errado.
        print(f"\nDatas no recorte: de {dados['data'].min()} a {dados['data'].max()}")
    print()

    com_matricula = dados[dados[identificador].notna()]
    sem_matricula = linhas - len(com_matricula)
    distintas = com_matricula[identificador].nunique()
    excedente = len(com_matricula) - distintas

    print(f"{identificador.capitalize()}s distintos ...... {distintas}")
    if sem_matricula:
        print(f"Linhas sem identificador  {sem_matricula} (não dá para conferir)")

    if excedente <= 0:
        print(f"\nOK: cada {identificador} é contado uma única vez.")
        return 0

    pct = excedente / total * 100 if total else 0
    print(f"\nATENÇÃO: {excedente} linha(s) a mais que {identificador}s distintos "
          f"({pct:.1f}% do total).")
    print("A mesma ligação está entrando mais de uma vez.\n")

    repetidas = (com_matricula.groupby(identificador).size()
                 .sort_values(ascending=False))
    repetidas = repetidas[repetidas > 1]

    colunas = [c for c in ("data", "cidade", "equipe", "frente", "servico")
               if c in dados.columns]

    # A decisão da correção depende disto: repetição com o MESMO serviço é a
    # mesma implantação lançada duas vezes; com serviço diferente pode ser
    # duas atividades legítimas na mesma ligação.
    mesmo_servico, servico_diferente = [], []
    for matricula in repetidas.index:
        grupo = com_matricula[com_matricula[identificador] == matricula]
        alvo = (servico_diferente
                if "servico" in grupo and grupo["servico"].nunique(dropna=False) > 1
                else mesmo_servico)
        alvo.append((matricula, grupo))

    def _excedente(pares: list) -> int:
        return sum(len(g) - 1 for _, g in pares)

    print(f"{len(repetidas)} {identificador}(s) repetido(s):")
    print(f"  mesmo serviço ......... {len(mesmo_servico)} caso(s), "
          f"{_excedente(mesmo_servico)} linha(s) a mais")
    print(f"  serviço diferente ..... {len(servico_diferente)} caso(s), "
          f"{_excedente(servico_diferente)} linha(s) a mais")

    if not args.resumo:
        print(f"\nDetalhando as {min(args.listar, len(repetidas))} maiores:\n")
        for matricula in repetidas.head(args.listar).index:
            grupo = com_matricula[com_matricula[identificador] == matricula]
            difere = [c for c in colunas if grupo[c].nunique(dropna=False) > 1]
            print(f"  {identificador} {matricula}: {len(grupo)} linhas — "
                  f"difere em {', '.join(difere) if difere else 'nada visível'}")
            print(grupo[colunas].to_string(index=False, max_rows=6))
            print()

    # Repetido no fim porque o detalhe rola a tela e esconde o cabeçalho.
    print("-" * 60)
    print(f"RESUMO ({recorte})")
    print(f"  total do painel ....... {total:.0f}")
    print(f"  {identificador}s distintos . {distintas}")
    print(f"  contadas a mais ....... {excedente} ({pct:.1f}% do total)")
    print(f"  total sem repetir ..... {total - excedente:.0f}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
