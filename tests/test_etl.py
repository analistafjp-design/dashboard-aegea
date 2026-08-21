"""Importação: validação, tratamento, duplicidade e carga incremental."""
import pandas as pd
from sqlalchemy import func, select

from app.analytics import cache
from app.etl.pipeline import processar_arquivo, processar_lote
from app.models.db import sessao
from app.models.tabelas import FatoImplantacao, FatoVendas, HistoricoUpload, Meta


def total_vendas() -> int:
    with sessao() as s:
        return s.execute(select(func.count()).select_from(FatoVendas)).scalar()


def test_importacao_completa_grava_todas_as_bases(base_carregada):
    assert all(r.ok for r in base_carregada), [r.mensagem for r in base_carregada if not r.ok]
    datasets = {r.dataset for r in base_carregada}
    assert datasets == {"metas", "termos", "vendas", "implantacao",
                        "faturamento", "programacao"}


def test_reimportar_o_mesmo_arquivo_nao_duplica(planilhas, base_carregada):
    antes = total_vendas()
    with sessao() as s:
        resultado = processar_arquivo(s, planilhas["vendas"])
    cache.invalidar()
    assert resultado.inseridos == 0
    assert resultado.atualizados == antes
    assert total_vendas() == antes


def test_registros_com_data_invalida_sao_descartados_e_contados(planilhas, tmp_path):
    dados = pd.read_excel(planilhas["vendas"])
    dados["Data"] = dados["Data"].astype(object)
    dados.loc[:2, "Data"] = "data errada"
    caminho = tmp_path / "venda_com_erro.xlsx"
    dados.to_excel(caminho, index=False)

    with sessao() as s:
        resultado = processar_arquivo(s, caminho)

    assert resultado.status == "ATENCAO"
    assert resultado.descartados == 3
    assert resultado.inseridos == len(dados) - 3
    assert any("data inválida" in detalhe for detalhe in resultado.detalhes)


def test_coluna_obrigatoria_ausente_gera_mensagem_clara(planilhas, tmp_path):
    dados = pd.read_excel(planilhas["vendas"]).drop(columns=["Canal"])
    caminho = tmp_path / "venda_sem_canal.xlsx"
    dados.to_excel(caminho, index=False)

    with sessao() as s:
        resultado = processar_arquivo(s, caminho, dataset_forcado="vendas")

    assert resultado.status == "ERRO"
    assert "não foi(ram) encontrada(s)" in resultado.mensagem
    assert "frente" in resultado.mensagem


def test_duplicatas_no_arquivo_sao_removidas(planilhas, tmp_path):
    dados = pd.read_excel(planilhas["vendas"])
    duplicado = pd.concat([dados, dados.head(4)], ignore_index=True)
    caminho = tmp_path / "venda_duplicada.xlsx"
    duplicado.to_excel(caminho, index=False)

    with sessao() as s:
        resultado = processar_arquivo(s, caminho)

    assert resultado.inseridos == len(dados)
    assert resultado.validacao["duplicadas_no_arquivo"] == 4


def test_implantacao_classifica_faturado(base_carregada):
    with sessao() as s:
        faturadas = s.execute(
            select(func.count()).select_from(FatoImplantacao)
            .where(FatoImplantacao.faturado.is_(True))).scalar()
        nao_faturadas = s.execute(
            select(func.count()).select_from(FatoImplantacao)
            .where(FatoImplantacao.faturado.is_(False))).scalar()
    assert faturadas > 0 and nao_faturadas > 0
    assert faturadas == nao_faturadas  # a fixture gera 1 de cada por dia


def test_metas_sao_carregadas_como_valores_oficiais(base_carregada):
    with sessao() as s:
        metas = s.execute(select(Meta)).scalars().all()
    assert len(metas) == 6
    agosto = {(m.modulo, m.segmento): m.valor_meta for m in metas if m.mes == 8}
    assert agosto[("VENDA", "TOTAL")] == 50
    assert agosto[("IMPLANTACAO", "TOTAL")] == 40


def test_historico_registra_cada_arquivo(planilhas):
    with sessao() as s:
        processar_lote(s, list(planilhas.values()))
    with sessao() as s:
        registros = s.execute(select(HistoricoUpload)).scalars().all()
    assert len(registros) == len(planilhas)
    assert all(r.status in ("SUCESSO", "ATENCAO") for r in registros)
    assert all(r.registros_lidos > 0 for r in registros)


def test_arquivo_nao_identificado_nao_derruba_o_lote(planilhas, tmp_path):
    estranho = tmp_path / "estranho.xlsx"
    pd.DataFrame({"Alfa": [1], "Beta": [2]}).to_excel(estranho, index=False)

    with sessao() as s:
        resultados = processar_lote(s, [planilhas["vendas"], estranho])

    por_arquivo = {r.arquivo: r for r in resultados}
    assert por_arquivo["venda.xlsx"].status == "SUCESSO"
    assert por_arquivo["estranho.xlsx"].status == "ERRO"
    assert "identificar o tipo de base" in por_arquivo["estranho.xlsx"].mensagem


def test_metas_sao_carregadas_antes_dos_fatos(planilhas):
    """A ordem importa: sem metas antes, os indicadores nasceriam sem meta."""
    with sessao() as s:
        resultados = processar_lote(s, list(planilhas.values()))
    assert resultados[0].dataset == "metas"


def test_erro_de_validacao_aponta_a_linha_real_do_excel(tmp_path):
    """Regra 23: mostrar arquivo, LINHA, coluna, valor, problema e sugestão.

    A planilha tem título nas linhas 1-2, cabeçalho na linha 3, uma linha em
    branco na posição 6 e o erro proposital na linha 8 — exatamente onde um
    usuário abrindo o Excel encontraria o problema.
    """
    linhas = [
        ["RELATÓRIO DE VENDAS", None, None, None],   # Excel linha 1 (título)
        [None, None, None, None],                     # Excel linha 2 (em branco)
        ["Data", "Cidade", "Canal", "Quantidade"],     # Excel linha 3 (cabeçalho)
        ["01/07/2026", "Maricá", "Comercial", 1],      # Excel linha 4
        ["02/07/2026", "Maricá", "Comercial", 1],      # Excel linha 5
        [None, None, None, None],                      # Excel linha 6 (em branco)
        ["03/07/2026", "Maricá", "Comercial", 1],      # Excel linha 7
        ["DATA INVALIDA", "Maricá", "Comercial", 1],   # Excel linha 8 <- erro
        ["05/07/2026", "Maricá", "Comercial", 1],      # Excel linha 9
    ]
    caminho = tmp_path / "venda_com_titulo.xlsx"
    pd.DataFrame(linhas).to_excel(caminho, index=False, header=False)

    with sessao() as s:
        resultado = processar_arquivo(s, caminho)

    assert resultado.status == "ATENCAO"
    exemplos = resultado.validacao["exemplos"]
    assert len(exemplos) == 1
    exemplo = exemplos[0]
    assert exemplo["linha"] == 8
    assert exemplo["coluna_original"] == "Data"
    assert exemplo["valor"] == "DATA INVALIDA"
    assert "inválida" in exemplo["problema"].lower()
    assert exemplo["sugestao"]  # nunca vazio


def test_quantidade_de_exemplos_e_limitada_e_contabilizada(tmp_path):
    """Arquivo com muitas linhas problemáticas não pode inflar a resposta."""
    linhas = [{"Data": "invalida", "Cidade": "Maricá", "Canal": "Comercial",
              "Quantidade": 1} for _ in range(60)]
    caminho = tmp_path / "venda_toda_invalida.xlsx"
    pd.DataFrame(linhas).to_excel(caminho, index=False)

    with sessao() as s:
        resultado = processar_arquivo(s, caminho)

    assert resultado.status == "ERRO"  # nenhuma linha válida
    from app.etl.transformacao import MAX_EXEMPLOS
    assert len(resultado.detalhes) <= 5  # ErroValidacaoArquivo, não usa 'exemplos'


def test_qualidade_dados_reflete_proporcao_de_linhas_validas(planilhas, tmp_path):
    dados = pd.read_excel(planilhas["vendas"])
    dados["Data"] = dados["Data"].astype(object)
    dados.loc[:9, "Data"] = "data errada"  # 10 de N linhas inválidas
    caminho = tmp_path / "venda_parcial.xlsx"
    dados.to_excel(caminho, index=False)

    with sessao() as s:
        resultado = processar_arquivo(s, caminho)

    esperado = round(resultado.inseridos / resultado.lidos * 100, 1)
    assert resultado.qualidade_dados == esperado
    assert 0 < resultado.qualidade_dados < 100


def test_confianca_e_campos_detectados_aparecem_mesmo_com_sucesso(planilhas):
    """Regra 22: mostrar a confiança da identificação, não só quando falha."""
    with sessao() as s:
        resultado = processar_arquivo(s, planilhas["vendas"])

    assert resultado.confianca_deteccao is not None
    assert 0.0 < resultado.confianca_deteccao <= 1.0
    assert "data" in resultado.campos_detectados
    assert "frente" in resultado.campos_detectados
    assert resultado.qualidade_dados == 100.0  # planilha limpa, sem erros
