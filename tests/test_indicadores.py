"""Regras de negócio dos indicadores: meta, atingimento, projeção e 'sem dados'."""
from datetime import date

import pandas as pd
import pytest

from app.analytics import metas as mod_metas
from app.analytics import painel
from app.analytics.implantacao import _realizadas_unicas
from app.analytics.base import (
    AZUL,
    CINZA,
    VERDE,
    VERMELHO,
    Filtros,
    calcular_atingimento,
    calcular_falta,
    status_por_atingimento,
    variacao_percentual,
)
from app.analytics.nucleo import bloco_meta, media_diaria, projecao, total
from app.analytics.periodo import montar, resolver

FILTROS_AGOSTO = Filtros(ano=2026, mes=8)


# ------------------------------------------------------------------ unitários
def test_atingimento_e_falta():
    assert calcular_atingimento(80, 100) == 80.0
    assert calcular_falta(80, 100) == 20.0
    assert calcular_falta(120, 100) == 0.0        # nunca negativo
    assert calcular_atingimento(80, 0) is None    # sem divisão por zero
    assert calcular_atingimento(None, 100) is None


def test_status_segue_faixas_unicas():
    assert status_por_atingimento(100) == VERDE
    assert status_por_atingimento(95) == "amarelo"
    assert status_por_atingimento(50) == VERMELHO
    assert status_por_atingimento(None) == CINZA


def test_variacao_percentual():
    assert variacao_percentual(110, 100) == 10.0
    assert variacao_percentual(90, 100) == -10.0
    assert variacao_percentual(10, 0) is None
    assert variacao_percentual(10, None) is None


def test_projecao_usa_ritmo_e_dias_uteis_restantes():
    periodo = montar(2026, 8, date(2026, 8, 21))
    realizado = 100.0
    esperado = realizado + (realizado / periodo.dias_uteis_decorridos) * periodo.dias_uteis_restantes
    assert projecao(realizado, periodo) == pytest.approx(esperado, rel=1e-6)
    assert projecao(None, periodo) is None


def test_media_diaria_protege_divisao_por_zero():
    assert media_diaria(100, 0) is None
    assert media_diaria(None, 10) is None
    assert media_diaria(100, 20) == 5.0


def test_implantacao_distinta_por_matricula_no_mes():
    """140 linhas da validação devem equivaler a 138 implantações."""
    linhas = [
        {
            "ano_mes": "2026-08", "data": date(2026, 8, 1),
            "matricula": f"M-{indice:03d}", "tipo": "VCG",
            "quantidade": 1.0, "conta_realizado": True,
        }
        for indice in range(138)
    ]
    # As duas repetições reproduzem o caso real: uma matrícula reaparece
    # depois e outra pode vir de um protocolo diferente.
    linhas.extend([
        {**linhas[0], "data": date(2026, 8, 10)},
        {**linhas[1], "data": date(2026, 8, 13)},
    ])

    resultado = _realizadas_unicas(pd.DataFrame(linhas))

    assert len(linhas) == 140
    assert len(resultado) == 138
    assert total(resultado) == 138.0


def test_implantacao_distinta_preserva_meses_e_registros_sem_matricula():
    base = pd.DataFrame([
        {"ano_mes": "2026-07", "data": date(2026, 7, 10), "matricula": "100",
         "tipo": "SERVICOS", "quantidade": 1.0, "conta_realizado": True},
        {"ano_mes": "2026-08", "data": date(2026, 8, 10), "matricula": "100",
         "tipo": "SERVICOS", "quantidade": 1.0, "conta_realizado": True},
        {"ano_mes": "2026-08", "data": date(2026, 8, 10), "matricula": "100",
         "tipo": "VCG", "quantidade": 1.0, "conta_realizado": True},
        {"ano_mes": "2026-08", "data": date(2026, 8, 11), "matricula": None,
         "tipo": "SERVICOS", "quantidade": 2.0, "conta_realizado": True},
        {"ano_mes": "2026-08", "data": date(2026, 8, 12), "matricula": "200",
         "tipo": "VCG", "quantidade": 1.0, "conta_realizado": False},
    ])

    resultado = _realizadas_unicas(base)

    assert len(resultado) == 4
    assert total(resultado) == 5.0


def test_bloco_meta_sem_meta_cadastrada_nao_inventa_numero():
    periodo = montar(2026, 8, date(2026, 8, 21))
    bloco = bloco_meta(100.0, None, periodo)
    assert bloco["meta"] is None
    assert bloco["meta_cadastrada"] is False
    assert bloco["mensagem_meta"] == "Meta não cadastrada"
    assert bloco["atingimento"] is None
    assert bloco["falta"] is None
    assert bloco["realizado"] == 100.0  # o realizado continua sendo mostrado


def test_metas_padrao_sao_as_constantes_extraidas_dos_pbix():
    assert mod_metas.meta("IMPLANTACAO", 2026, 8, "SERVICOS") == 234.0
    assert mod_metas.meta("IMPLANTACAO", 2026, 8, "VCG") == 188.0
    assert mod_metas.meta_total_composta("IMPLANTACAO", 2026, 8) == 422.0
    assert mod_metas.meta("TERMOS", 2026, 8, "SERVICOS") == 250.0
    assert mod_metas.meta("TERMOS", 2026, 8, "VCG") == 180.0
    assert mod_metas.meta_total_composta("TERMOS", 2026, 8) == 430.0


# ------------------------------------------------------- distinção sem dados/0
def test_base_vazia_devolve_none_e_nao_zero():
    import pandas as pd
    assert total(pd.DataFrame()) is None
    assert total(pd.DataFrame({"quantidade": []})) is None
    assert total(pd.DataFrame({"quantidade": [0, 0]})) == 0.0  # zero real


def test_sem_dados_todos_os_cards_dizem_sem_dados():
    """Banco vazio: nada de zeros fantasmas na Home."""
    dados = painel.home(Filtros())
    assert dados["tem_dados"] is False
    realizado = next(c for c in dados["cards"] if c["chave"] == "realizado_total")
    assert realizado["valor"] is None
    assert realizado["disponivel"] is False
    assert realizado["texto"] == "Sem dados no período"
    meta = next(c for c in dados["cards"] if c["chave"] == "meta_total")
    assert meta["valor"] == 430 + 234 + 422
    assert meta["mensagem"] is None


# --------------------------------------------------------- com dados de teste
def test_termos_totais_conferem_com_a_planilha(base_carregada, dias_uteis_agosto):
    dados = painel.modulo("termos", FILTROS_AGOSTO)
    indicadores = {i["chave"]: i for i in dados["indicadores"]}
    # a fixture gera 2 termos por dia útil: 1 Serviços + 1 VCG
    assert indicadores["realizado_total"]["valor"] == dias_uteis_agosto * 2
    assert indicadores["realizado_servicos"]["valor"] == dias_uteis_agosto
    assert indicadores["realizado_vcg"]["valor"] == dias_uteis_agosto
    assert dados["evolucao_diaria_tipo"]
    datas_diarias = [linha["data"] for linha in dados["evolucao_diaria_tipo"]]
    assert datas_diarias == sorted(datas_diarias)
    assert dados["por_cidade_tipo"]
    assert dados["por_equipe_tipo"]
    assert dados["por_setor"]
    assert sum(item["total"] for item in dados["por_setor"]) == dias_uteis_agosto * 2
    assert dados["insights_executivos"]
    primeira_cidade = dados["por_cidade_tipo"][0]
    assert primeira_cidade["total"] == primeira_cidade["servicos"] + primeira_cidade["vcg"]


def test_meta_de_termos_e_a_soma_dos_segmentos(base_carregada):
    """Sem meta TOTAL cadastrada, soma-se Serviços + VCG (20 + 20)."""
    assert mod_metas.meta_total_composta("TERMOS", 2026, 8) == 40.0
    assert mod_metas.meta("TERMOS", 2026, 8, "SERVICOS") == 20.0
    # Sem planilha específica para setembro, vale a constante DAX do PBIX.
    assert mod_metas.meta("TERMOS", 2026, 9) == 430.0


def test_atingimento_de_vendas_bate_com_o_calculo_manual(base_carregada, dias_uteis_agosto):
    dados = painel.modulo("vendas", FILTROS_AGOSTO)
    bloco = dados["bloco_principal"]
    realizado = dias_uteis_agosto * 2
    assert bloco["realizado"] == realizado
    assert bloco["meta"] == 50.0
    assert bloco["atingimento"] == pytest.approx(round(realizado / 50 * 100, 1))
    assert bloco["falta"] == pytest.approx(max(50 - realizado, 0))


def test_implantacao_separa_faturado_de_nao_faturado(base_carregada, dias_uteis_agosto):
    dados = painel.modulo("implantacao", FILTROS_AGOSTO)
    faturamento = dados["faturamento"]
    assert faturamento["quantidade_faturada"] == dias_uteis_agosto
    assert faturamento["quantidade_nao_faturada"] == dias_uteis_agosto
    assert faturamento["percentual_faturado"] == 50.0
    assert "não faturada" in faturamento["alerta"]
    assert faturamento["valor_faturado"] == dias_uteis_agosto * 300.0
    por_frente = {linha["frente"]: linha for linha in faturamento["por_frente"]}
    assert por_frente["Serviços"] == {
        "frente": "Serviços", "implantacao": float(dias_uteis_agosto),
        "faturada": float(dias_uteis_agosto), "nao_faturada": 0.0,
        "valor_faturado": dias_uteis_agosto * 300.0,
    }
    assert por_frente["VCG"]["implantacao"] == float(dias_uteis_agosto)
    assert por_frente["VCG"]["faturada"] == 0.0
    assert por_frente["VCG"]["nao_faturada"] == float(dias_uteis_agosto)


def test_filtro_de_cidade_reduz_o_realizado(base_carregada):
    total_geral = painel.modulo("vendas", FILTROS_AGOSTO)["bloco_principal"]["realizado"]
    por_cidade = painel.modulo(
        "vendas", Filtros(ano=2026, mes=8, cidade="Maricá"))["bloco_principal"]["realizado"]
    assert por_cidade is not None
    assert 0 < por_cidade < total_geral


def test_filtro_sem_correspondencia_diz_sem_dados(base_carregada):
    dados = painel.modulo("vendas", Filtros(ano=2026, mes=8, cidade="Cidade Inexistente"))
    assert dados["tem_dados"] is False
    assert dados["bloco_principal"]["realizado"] is None


def test_comparacao_usa_mesmo_numero_de_dias_uteis(base_carregada):
    """Agosto parcial não pode ser comparado com julho inteiro."""
    dados = painel.modulo("vendas", FILTROS_AGOSTO)
    indicador = next(i for i in dados["indicadores"] if i["chave"] == "total_venda")
    # a fixture produz o mesmo volume por dia útil nos dois meses
    assert indicador["anterior"] == indicador["valor"]
    assert indicador["variacao"] == 0.0


def test_home_consolida_os_tres_modulos(base_carregada):
    home = painel.home(FILTROS_AGOSTO)
    modulos = {m["rotulo"]: m for m in home["modulos"]}
    soma = sum(m["realizado"] for m in modulos.values())
    consolidado = home["consolidado"]
    assert consolidado["realizado"] == soma
    assert consolidado["meta"] == 40 + 50 + 40  # termos + venda + implantação
    assert consolidado["atingimento"] == pytest.approx(round(soma / 130 * 100, 1))


def test_periodo_padrao_e_o_ultimo_mes_com_dados(base_carregada):
    periodo = resolver(Filtros())
    assert (periodo.ano, periodo.mes) == (2026, 8)
    assert periodo.dias_uteis_restantes >= 0


def test_programacao_calcula_carga_por_equipe(base_carregada):
    dados = painel.modulo("programacao", FILTROS_AGOSTO)
    indicadores = {i["chave"]: i for i in dados["indicadores"]}
    assert indicadores["os_programadas_dia"]["valor"] == 10.0   # 1 equipe x 10 O.S.
    assert indicadores["equipes_programadas"]["valor"] == 1.0
    assert dados["agenda"], "a agenda operacional não pode vir vazia"


def test_insights_e_alertas_saem_de_numeros_reais(base_carregada):
    home = painel.home(FILTROS_AGOSTO)
    assert home["insights"], "deveria haver insights com dados carregados"
    textos = " ".join(i["texto"] for i in home["insights"])
    assert "implantação" in textos.lower() or "venda" in textos.lower()
    assert home["resumo_alertas"]["total"] > 0


def test_equipes_mantem_modulos_separados(base_carregada):
    dados = painel.modulo("equipes", FILTROS_AGOSTO, base="vendas")
    assert dados["tabela"]
    linha = dados["tabela"][0]
    assert {"termos", "vendas", "implantacao"} <= set(linha)
    assert linha["realizado"] == linha["vendas"]  # base selecionada = vendas


def test_cidades_ranqueiam_sem_somar_modulos(base_carregada):
    dados = painel.modulo("cidades", FILTROS_AGOSTO)
    assert dados["tabela"]
    for linha in dados["tabela"]:
        assert {"termos", "vendas", "implantacao", "faturamento"} <= set(linha)
