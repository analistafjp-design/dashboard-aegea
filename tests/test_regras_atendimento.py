"""Regra 'Vendas Outros Canais' — equivalente à medida DAX do Power BI.

Cada teste isola UM dos cinco filtros da medida, para que uma alteração
acidental em qualquer um deles apareça aqui e não como número errado no
painel executivo.
"""
import pandas as pd
import pytest

from app.etl import regras_atendimento as regras

SERVICO_VALIDO = '117002 - IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA 3/4" - ASFALTO'


def linha(**alteracoes) -> dict:
    base = {
        "ocorrencia": "0-Executado",
        "ligacao": "103489943",
        "servico": SERVICO_VALIDO,
        "cidade": "RIO BONITO",
        "usuario_emissor": "FULANO DE TAL",
    }
    base.update(alteracoes)
    return base


def test_linha_que_atende_todos_os_filtros_conta_como_venda():
    assert regras.linha_e_venda_outros_canais(linha()) is True


@pytest.mark.parametrize("campo,valor,motivo", [
    ("ocorrencia", "1-Cancelado", "ocorrência diferente de 0-Executado"),
    ("ocorrencia", "", "ocorrência vazia"),
    ("ligacao", "", "sem Nº Ligação"),
    ("ligacao", None, "Nº Ligação nulo"),
    ("ligacao", "0", "Nº Ligação zerado conta como em branco"),
    ("servico", "109001 - CORTE DE ÁGUA NO CAVALETE", "serviço fora da lista"),
    ("cidade", "NITEROI", "localidade fora da lista"),
    ("usuario_emissor", "ELBA SILVA GREGORIO", "usuário excluído da medida"),
    ("usuario_emissor", "  beatriz tavares magalhaes  ", "usuário excluído com espaço/minúscula"),
])
def test_cada_filtro_da_medida_exclui_a_linha(campo, valor, motivo):
    assert regras.linha_e_venda_outros_canais(linha(**{campo: valor})) is False, motivo


def test_comparacao_tolera_acento_espaco_e_caixa():
    """Exportações do mesmo relatório variam nesses detalhes; uma linha
    válida não pode ser descartada em silêncio por causa disso."""
    assert regras.linha_e_venda_outros_canais(linha(cidade="rio  bonito")) is True
    assert regras.linha_e_venda_outros_canais(linha(cidade="  RIO BONITO ")) is True
    assert regras.linha_e_venda_outros_canais(linha(ocorrencia="0-EXECUTADO")) is True
    assert regras.linha_e_venda_outros_canais(linha(cidade="APERIBÉ")) is True  # com acento


def test_todos_os_cinco_servicos_da_medida_sao_aceitos():
    for servico in regras.SERVICOS:
        assert regras.linha_e_venda_outros_canais(linha(servico=servico)) is True, servico


def test_todas_as_doze_localidades_da_medida_sao_aceitas():
    assert len(regras.LOCALIDADES) == 12
    for cidade in regras.LOCALIDADES:
        assert regras.linha_e_venda_outros_canais(linha(cidade=cidade)) is True, cidade


def test_filtrar_devolve_so_as_linhas_validas_e_conta_os_motivos():
    dados = pd.DataFrame([
        linha(),                                   # válida
        linha(),                                   # válida
        linha(ocorrencia="2-Pendente"),            # fora de 0-Executado
        linha(cidade="NITEROI"),                   # localidade fora
        linha(servico="OUTRO SERVIÇO"),            # serviço fora
        linha(ligacao=""),                         # sem ligação
        linha(usuario_emissor="YANDRA DA SILVA FLOR"),  # usuário excluído
    ])
    validas, motivos = regras.filtrar(dados)

    assert len(validas) == 2
    assert sum(motivos.values()) == 5
    assert any("0-Executado" in m for m in motivos)
    assert any("Nº Ligação" in m for m in motivos)
    assert any("usuário excluído" in m for m in motivos)


def test_filtrar_em_dataframe_vazio_nao_quebra():
    validas, motivos = regras.filtrar(pd.DataFrame())
    assert validas.empty and motivos == {}
