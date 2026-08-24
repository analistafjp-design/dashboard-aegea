"""Regras `Venda Comercial` e `Venda VCG` do PBIX.

As duas medidas se sobrepõem de propósito: a mesma venda pode contar nas
duas, então cada linha carrega uma marca por medida.
"""
import pandas as pd

from app.etl.regras_powerbi import filtrar_vendas


def _linhas(*casos):
    """(equipe, código) ou (equipe, código, tipo de atividade)."""
    return pd.DataFrame([
        {
            "tipo_atividade": caso[2] if len(caso) > 2 else "Venda Potenciais/Factíveis",
            "status_atividade": "Finalizada",
            "equipe": caso[0],
            "codigo_descricao": caso[1],
        }
        for caso in casos
    ])


def _canais(df):
    return dict(zip(df["equipe"], df["canal"]))


def _marcas(df):
    return {
        linha["equipe"]: (linha["conta_comercial"], linha["conta_vcg"])
        for _, linha in df.iterrows()
    }


def test_equipe_comum_e_comercial():
    resultado = filtrar_vendas(_linhas(("RIORECIN-001", "113001-VENDA")))
    assert _canais(resultado) == {"RIORECIN-001": "COMERCIAL"}


def test_equipe_vcg_e_vcg():
    resultado = filtrar_vendas(_linhas(("RIOVCGEXTIN-005", "113001-VENDA")))
    assert _canais(resultado) == {"RIOVCGEXTIN-005": "VCG"}


def test_riovcgvenin_com_113001_conta_nas_duas_medidas():
    """A exceção torna a venda comercial sem tirá-la de VCG.

    O DAX de Comercial abre exceção para o RIOVCGVENIN com 113001; o de VCG
    só descarta o 114003, então continua contando essa mesma linha.
    """
    resultado = filtrar_vendas(_linhas(("RIOVCGVENIN-002", "113001-VENDA POTENCIAL")))
    assert _marcas(resultado) == {"RIOVCGVENIN-002": (True, True)}


def test_codigo_313001_conta_em_vcg_mesmo_com_outro_tipo_de_atividade():
    """Venda factível de água entra em VCG fora de Venda Potenciais/Factíveis."""
    resultado = filtrar_vendas(_linhas(
        ("RIOVCGEXTIN-007", "313001-VENDAS FACTÍVEL ÁGUA", "Ligação de Água"),
    ))
    assert _marcas(resultado) == {"RIOVCGEXTIN-007": (False, True)}


def test_codigo_313001_de_equipe_comum_nao_vira_vcg():
    resultado = filtrar_vendas(_linhas(
        ("RIORECIN-009", "313001-VENDAS FACTÍVEL ÁGUA", "Ligação de Água"),
    ))
    assert resultado.empty


def test_riovcgvenin_com_outro_codigo_continua_vcg():
    resultado = filtrar_vendas(_linhas(("RIOVCGVENIN-003", "115002-OUTRO")))
    assert _canais(resultado) == {"RIOVCGVENIN-003": "VCG"}


def test_codigos_114003_e_118048_saem_do_comercial():
    resultado = filtrar_vendas(_linhas(
        ("RIORECIN-001", "114003-EXCLUIDO"),
        ("RIORECIN-002", "118048-EXCLUIDO"),
        ("RIORECIN-003", "113001-VALIDO"),
    ))
    assert list(resultado["equipe"]) == ["RIORECIN-003"]


def test_excecao_nao_vale_para_as_outras_equipes_vcg():
    """Só RIOVCGVENIN tem a exceção; POPIN e EXTIN com 113001 seguem VCG."""
    resultado = filtrar_vendas(_linhas(
        ("RIOVCGPOPIN-001", "113001-VENDA"),
        ("RIOVCGEXTIN-001", "113001-VENDA"),
    ))
    assert set(resultado["canal"]) == {"VCG"}


def test_status_diferente_de_finalizada_nao_entra():
    dados = _linhas(("RIORECIN-001", "113001-VENDA"))
    dados.loc[0, "status_atividade"] = "Em execução"
    assert filtrar_vendas(dados).empty
