"""Configuração dos testes: banco temporário e dados sintéticos controlados.

O banco de teste é criado em um diretório temporário ANTES de qualquer
import de `app`, para que a aplicação nunca toque no banco real.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_TEMPORARIO = tempfile.mkdtemp(prefix="dashboard_testes_")
os.environ["DATA_DIR"] = _TEMPORARIO
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TEMPORARIO) / 'teste.db'}"
os.environ["CACHE_TTL"] = "0"

import pandas as pd  # noqa: E402

from app.analytics import cache  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.db import criar_banco, engine, sessao  # noqa: E402

REFERENCIA = date(2026, 8, 21)
CIDADES = ["Rio Bonito", "Itaboraí", "Maricá"]
EQUIPES = ["Equipe 01", "Equipe 02", "Equipe 03"]


def dias_uteis(inicio: date, fim: date) -> list[date]:
    dias, atual = [], inicio
    while atual <= fim:
        if atual.weekday() < 5:
            dias.append(atual)
        atual += timedelta(days=1)
    return dias


@pytest.fixture(scope="session")
def diretorio_temporario() -> Path:
    return Path(_TEMPORARIO)


@pytest.fixture(autouse=True)
def banco_limpo():
    """Cada teste começa com o banco zerado e o cache invalidado."""
    Base.metadata.drop_all(engine)
    criar_banco()
    cache.invalidar()
    yield
    cache.invalidar()


@pytest.fixture
def planilhas(diretorio_temporario) -> dict[str, Path]:
    """Planilhas pequenas e determinísticas, com totais conhecidos.

    Julho/2026 e agosto/2026, 2 registros por dia útil em cada base.
    """
    destino = diretorio_temporario / "planilhas"
    destino.mkdir(parents=True, exist_ok=True)
    dias = dias_uteis(date(2026, 7, 1), REFERENCIA)

    termos, vendas, implantacao, faturamento, programacao = [], [], [], [], []
    for indice, dia in enumerate(dias):
        cidade = CIDADES[indice % len(CIDADES)]
        equipe = EQUIPES[indice % len(EQUIPES)]
        for sufixo, frente in ((0, "Serviços"), (1, "VCG Rio Bonito")):
            termos.append({
                "Data da Atividade": dia, "Município": cidade, "Recurso": equipe,
                "Frente": frente, "Setor do Recurso": "Operação",
                "Matrícula": f"{indice}{sufixo}", "Tipo de Termo": frente,
                "Status Termo": "Aplicado", "Qtde": 1, "Valor": 100.0,
            })
            vendas.append({
                "Data": dia, "Cidade": cidade, "Equipe": equipe,
                "Canal": "Comercial" if sufixo == 0 else "VCG Rio Bonito",
                "Matrícula": f"{indice}{sufixo}", "Quantidade": 1, "Valor": 200.0,
            })
            implantacao.append({
                "Data da Implantação": dia, "Cidade": cidade, "Equipe": equipe,
                "Frente": frente, "Matrícula": f"{indice}{sufixo}",
                "Serviço": "Ligação Nova",
                "Situação Faturamento": "Faturado" if sufixo == 0 else "Não Faturado",
                "Quantidade": 1, "Valor": 300.0 if sufixo == 0 else None,
            })
        faturamento.append({
            "Início do Mês": dia.replace(day=1), "Nº Termo": f"T{indice}",
            "CIDADE": cidade, "Situação do Termo": "Faturado", "Qtd": 1, "Valor": 500.0,
        })
        programacao.append({
            "Data Programação": dia, "Regiao": "Região A", "Recurso": equipe,
            "Projeto Principal": "Projeto Interior", "Cidade": cidade, "Qtd OS": 10,
        })

    metas = [
        {"Ano": 2026, "Mês": 7, "Indicador": "TERMOS", "Tipo": "SERVICOS", "Meta": 20},
        {"Ano": 2026, "Mês": 7, "Indicador": "TERMOS", "Tipo": "VCG", "Meta": 20},
        {"Ano": 2026, "Mês": 8, "Indicador": "TERMOS", "Tipo": "SERVICOS", "Meta": 20},
        {"Ano": 2026, "Mês": 8, "Indicador": "TERMOS", "Tipo": "VCG", "Meta": 20},
        {"Ano": 2026, "Mês": 8, "Indicador": "VENDA", "Tipo": "TOTAL", "Meta": 50},
        {"Ano": 2026, "Mês": 8, "Indicador": "IMPLANTACAO", "Tipo": "TOTAL", "Meta": 40},
    ]

    arquivos = {
        "metas": ("metas.xlsx", metas),
        "termos": ("termos.xlsx", termos),
        "vendas": ("venda.xlsx", vendas),
        "implantacao": ("implantacao.xlsx", implantacao),
        "faturamento": ("faturamento.xlsx", faturamento),
        "programacao": ("programacao.xlsx", programacao),
    }
    caminhos = {}
    for chave, (nome, registros) in arquivos.items():
        caminho = destino / nome
        pd.DataFrame(registros).to_excel(caminho, index=False, sheet_name="Dados")
        caminhos[chave] = caminho
    return caminhos


@pytest.fixture
def base_carregada(planilhas):
    """Banco populado com todas as planilhas de teste."""
    from app.etl.pipeline import processar_lote

    with sessao() as s:
        resultados = processar_lote(s, list(planilhas.values()))
    cache.invalidar()
    return resultados


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def dias_uteis_agosto() -> int:
    """Dias úteis de 01/08/2026 até a referência (21/08/2026)."""
    return len(dias_uteis(date(2026, 8, 1), REFERENCIA))
