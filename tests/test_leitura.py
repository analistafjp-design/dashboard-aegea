"""Trava de tamanho: recusa arquivo grande demais ANTES de ler tudo na memória."""
import pandas as pd
import pytest

from app.config import config
from app.etl.leitura import ler_planilhas
from app.utils.erros import ErroValidacaoArquivo


@pytest.fixture
def limite_baixo(monkeypatch):
    """Simula um limite baixo (sem precisar gerar dezenas de milhares de
    linhas nos testes) para exercitar a trava de forma rápida."""
    monkeypatch.setattr(config, "LIMITE_LINHAS_ARQUIVO", 5)
    return 5


def test_arquivo_dentro_do_limite_e_lido_normalmente(planilhas):
    planilhas_lidas = ler_planilhas(planilhas["vendas"])
    assert planilhas_lidas
    assert not planilhas_lidas[0].dados.empty


def test_xlsx_acima_do_limite_e_recusado_sem_carregar_tudo(planilhas, limite_baixo):
    with pytest.raises(ErroValidacaoArquivo) as excinfo:
        ler_planilhas(planilhas["vendas"])
    mensagem = str(excinfo.value)
    assert "linhas" in mensagem
    assert "5" in mensagem
    assert any("Divida o arquivo" in d for d in excinfo.value.detalhes)


def test_csv_acima_do_limite_e_recusado(tmp_path, limite_baixo):
    dados = pd.DataFrame([
        {"Data": "01/08/2026", "Cidade": "Rio Bonito", "Equipe": "Equipe 01",
         "Canal": "Comercial", "Matrícula": i, "Quantidade": 1, "Valor": 100.0}
        for i in range(20)
    ])
    caminho = tmp_path / "venda_grande.csv"
    dados.to_csv(caminho, index=False, sep=";")

    with pytest.raises(ErroValidacaoArquivo) as excinfo:
        ler_planilhas(caminho)
    assert "linhas" in str(excinfo.value)


def test_mensagem_do_limite_sugere_dividir_ou_migrar_de_plano(planilhas, limite_baixo):
    with pytest.raises(ErroValidacaoArquivo) as excinfo:
        ler_planilhas(planilhas["vendas"])
    detalhes = " ".join(excinfo.value.detalhes)
    assert "Divida o arquivo" in detalhes
    assert "plano com mais memória" in detalhes
