#!/usr/bin/env python3
"""Gera planilhas de EXEMPLO para demonstrar e testar o sistema.

Os dados são sintéticos e servem apenas para validar o funcionamento do
ETL, dos indicadores e das telas enquanto as bases reais não são enviadas.
Os cabeçalhos usam variações propositais ("Data da Atividade", "Município",
"Recurso"...) para exercitar o mapa de colunas.

Uso:
    python scripts/gerar_dados_exemplo.py [--saida data/exemplos] [--meses 6]
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.calendario import dias_uteis_entre, ultimo_dia_mes  # noqa: E402

SEMENTE = 20260821

CIDADES = ["Rio Bonito", "Itaboraí", "Maricá", "Tanguá", "Silva Jardim",
           "Cachoeiras de Macacu", "São Gonçalo"]
EQUIPES = [f"Equipe {i:02d}" for i in range(1, 15)]
FRENTES_VENDA = ["Comercial", "VCG Rio Bonito", "VCG Bairro Legal/SFI", "Outros Canais"]
FRENTES_PRODUCAO = ["Serviços", "VCG Rio Bonito", "VCG Bairro Legal/SFI"]
SETORES = ["Manutenção", "Comercial", "Operação", "Perdas"]
REGIOES = ["Região A", "Região B", "Região C"]
PROJETOS = ["Projeto Interior", "Projeto Perdas", "Projeto VCG", "Projeto Serviços"]
SITUACOES = ["Negociação", "Aguardando", "Faturado", "Cancelado"]
SERVICOS = ["Ligação Nova", "Religação", "Troca de Hidrômetro", "Regularização"]


def dias_uteis_do_periodo(inicio: date, fim: date) -> list[date]:
    dias, atual = [], inicio
    while atual <= fim:
        if dias_uteis_entre(atual, atual):
            dias.append(atual)
        atual += timedelta(days=1)
    return dias


def periodo(meses: int, referencia: date) -> tuple[date, date]:
    ano, mes = referencia.year, referencia.month - meses + 1
    while mes <= 0:
        ano, mes = ano - 1, mes + 12
    return date(ano, mes, 1), referencia


def gerar_termos(dias: list[date], rng: random.Random) -> pd.DataFrame:
    linhas = []
    for dia in dias:
        for _ in range(rng.randint(12, 28)):
            frente = rng.choice(FRENTES_PRODUCAO)
            linhas.append({
                "Data da Atividade": dia,
                "Município": rng.choice(CIDADES),
                "Recurso": rng.choice(EQUIPES),
                "Frente": frente,
                "Setor do Recurso": rng.choice(SETORES),
                "Matrícula": f"{rng.randint(100000, 999999)}",
                "Tipo de Termo": "VCG" if "VCG" in frente else "Serviços",
                "Status Termo": rng.choices(
                    ["Aplicado", "Pendente", "Cancelado"], weights=[85, 10, 5])[0],
                "Qtde": 1,
                "Valor": round(rng.uniform(120, 900), 2),
            })
    return pd.DataFrame(linhas)


def gerar_faturamento(dias: list[date], rng: random.Random) -> pd.DataFrame:
    linhas = []
    for dia in dias:
        for _ in range(rng.randint(6, 16)):
            situacao = rng.choices(SITUACOES, weights=[25, 20, 45, 10])[0]
            linhas.append({
                "Início do Mês": dia.replace(day=1),
                "Nº Termo": f"T{dia.strftime('%y%m')}{rng.randint(1000, 9999)}",
                "CIDADE": rng.choice(CIDADES),
                "Situação do Termo": situacao,
                "Qtd": 1,
                "Valor": round(rng.uniform(200, 1500), 2) if situacao == "Faturado" else None,
            })
    return pd.DataFrame(linhas)


def gerar_vendas(dias: list[date], rng: random.Random) -> pd.DataFrame:
    linhas = []
    for dia in dias:
        for _ in range(rng.randint(15, 35)):
            linhas.append({
                "Data": dia,
                "Cidade": rng.choice(CIDADES),
                "Equipe": rng.choice(EQUIPES),
                "Canal": rng.choices(FRENTES_VENDA, weights=[45, 25, 20, 10])[0],
                "Matrícula": f"{rng.randint(100000, 999999)}",
                "Quantidade": 1,
                "Valor": round(rng.uniform(80, 600), 2),
            })
    return pd.DataFrame(linhas)


def gerar_implantacao(dias: list[date], rng: random.Random) -> pd.DataFrame:
    linhas = []
    for dia in dias:
        for _ in range(rng.randint(14, 30)):
            frente = rng.choice(FRENTES_PRODUCAO)
            faturado = rng.random() < 0.72
            linhas.append({
                "Data da Implantação": dia,
                "Cidade": rng.choice(CIDADES),
                "Equipe": rng.choice(EQUIPES),
                "Frente": frente,
                "Matrícula": f"{rng.randint(100000, 999999)}",
                "Serviço": rng.choice(SERVICOS),
                "Situação Faturamento": "Faturado" if faturado else "Não Faturado",
                "Quantidade": 1,
                "Valor": round(rng.uniform(150, 1200), 2) if faturado else None,
            })
    return pd.DataFrame(linhas)


def gerar_programacao(dias: list[date], rng: random.Random) -> pd.DataFrame:
    linhas = []
    for dia in dias[-25:]:
        for equipe in rng.sample(EQUIPES, rng.randint(7, 12)):
            linhas.append({
                "Data Programação": dia,
                "Regiao": rng.choice(REGIOES),
                "Recurso": equipe,
                "Projeto Principal": rng.choice(PROJETOS),
                "Cidade": rng.choice(CIDADES),
                "Qtd OS": rng.randint(4, 22),
            })
    return pd.DataFrame(linhas)


def gerar_metas(inicio: date, fim: date, rng: random.Random) -> pd.DataFrame:
    linhas = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        uteis = dias_uteis_entre(date(ano, mes, 1), ultimo_dia_mes(date(ano, mes, 1)))
        for modulo, base_servicos, base_vcg in (
            ("TERMOS", 12, 7), ("VENDA", 16, 9), ("IMPLANTACAO", 13, 8),
        ):
            segmentos = (("SERVICOS", base_servicos), ("VCG", base_vcg)) \
                if modulo != "VENDA" else (("COMERCIAL", base_servicos), ("VCG", base_vcg))
            for segmento, base in segmentos:
                linhas.append({
                    "Ano": ano, "Mês": mes, "Indicador": modulo, "Tipo": segmento,
                    "Cidade": None, "Equipe": None,
                    "Meta": int(base * uteis * rng.uniform(0.95, 1.15)),
                })
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    return pd.DataFrame(linhas)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera planilhas de exemplo")
    parser.add_argument("--saida", default="data/exemplos")
    parser.add_argument("--meses", type=int, default=6)
    parser.add_argument("--referencia", default=None, help="AAAA-MM-DD (padrão: hoje)")
    args = parser.parse_args()

    rng = random.Random(SEMENTE)
    referencia = date.fromisoformat(args.referencia) if args.referencia else date.today()
    inicio, fim = periodo(args.meses, referencia)
    dias = dias_uteis_do_periodo(inicio, fim)

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)

    arquivos = {
        "metas.xlsx": gerar_metas(inicio, fim, rng),
        "termos_aplicados.xlsx": gerar_termos(dias, rng),
        "faturamento_termos.xlsx": gerar_faturamento(dias, rng),
        "venda.xlsx": gerar_vendas(dias, rng),
        "implantacao.xlsx": gerar_implantacao(dias, rng),
        "programacao_diaria.xlsx": gerar_programacao(dias, rng),
    }
    for nome, dados in arquivos.items():
        caminho = destino / nome
        dados.to_excel(caminho, index=False, sheet_name="Dados")
        print(f"{caminho}  ->  {len(dados):>6} linhas")

    print(f"\nPeríodo gerado: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} ({len(dias)} dias úteis)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
