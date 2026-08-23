"""Identificação do arquivo pela estrutura das colunas e mapa de sinônimos."""
import pandas as pd
import pytest

from app.etl.datasets import DATASETS, VENDAS, get_dataset
from app.etl.deteccao import analisar_arquivo, mapear_colunas
from app.utils.erros import ErroValidacaoArquivo


def test_cada_planilha_e_identificada_corretamente(planilhas):
    for esperado, caminho in planilhas.items():
        identificacao = analisar_arquivo(caminho)
        assert identificacao.dataset is not None, f"{caminho.name} não foi identificado"
        assert identificacao.dataset.nome == esperado, (
            f"{caminho.name}: esperado {esperado}, veio {identificacao.dataset.nome}")
        assert identificacao.compativel


def test_nome_do_arquivo_nao_decide_a_deteccao(planilhas, tmp_path):
    """Renomear o arquivo não pode mudar o tipo de base identificado."""
    disfarcado = tmp_path / "planilha_qualquer_2026.xlsx"
    pd.read_excel(planilhas["implantacao"]).to_excel(disfarcado, index=False)
    assert analisar_arquivo(disfarcado).dataset.nome == "implantacao"


def test_sinonimos_de_coluna_sao_aceitos():
    """'Data da Atividade' e 'Data' caem no mesmo campo interno."""
    for cabecalho in ("Data da Atividade", "Data", "DT ATIVIDADE", "data_atividade"):
        mapa = mapear_colunas(get_dataset("termos"), [cabecalho, "Cidade", "Recurso"])
        assert mapa.get("data") == cabecalho

    mapa = mapear_colunas(VENDAS, ["Data", "Município", "Canal de Venda", "Qtde"])
    assert mapa["cidade"] == "Município"
    assert mapa["frente"] == "Canal de Venda"
    assert mapa["quantidade"] == "Qtde"


def test_setor_prioriza_descricao_do_powerbi_em_vez_do_codigo_numerico():
    mapa = mapear_colunas(get_dataset("termos"), [
        "Setor",
        "Setor do Recurso.Setor do Recurso",
        "Data da Atividade",
        "Recurso",
    ])

    assert mapa["setor"] == "Setor do Recurso.Setor do Recurso"


def test_arquivo_desconhecido_nao_e_identificado(tmp_path):
    caminho = tmp_path / "outra_coisa.xlsx"
    pd.DataFrame({"Alfa": [1, 2], "Beta": ["x", "y"]}).to_excel(caminho, index=False)
    assert analisar_arquivo(caminho).dataset is None


def test_extensao_invalida_e_recusada(tmp_path):
    caminho = tmp_path / "arquivo.txt"
    caminho.write_text("conteúdo", encoding="utf-8")
    with pytest.raises(ErroValidacaoArquivo, match="não é aceito"):
        analisar_arquivo(caminho)


def test_cabecalho_abaixo_de_linhas_de_titulo(tmp_path):
    """Planilha com título/logo antes do cabeçalho ainda é lida."""
    caminho = tmp_path / "com_titulo.xlsx"
    linhas = [
        ["RELATÓRIO DE VENDAS", None, None, None],
        [None, None, None, None],
        ["Data", "Cidade", "Canal", "Quantidade"],
        ["01/07/2026", "Maricá", "Comercial", 1],
        ["02/07/2026", "Maricá", "VCG", 1],
    ]
    pd.DataFrame(linhas).to_excel(caminho, index=False, header=False)
    identificacao = analisar_arquivo(caminho)
    assert identificacao.dataset.nome == "vendas"
    assert identificacao.planilha.linha_cabecalho == 2


def test_todos_os_datasets_tem_chave_unica_valida():
    for dataset in DATASETS.values():
        assert dataset.chave_unica, f"{dataset.nome} sem chave única"
        nomes = {c.nome for c in dataset.campos}
        assert set(dataset.chave_unica) <= nomes, dataset.nome
