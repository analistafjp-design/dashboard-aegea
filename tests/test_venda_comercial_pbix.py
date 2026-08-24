"""Regra `Venda Comercial` do PBIX, incluindo a exceção do RIOVCGVENIN."""
import pandas as pd

from app.etl.regras_powerbi import filtrar_vendas


def _linhas(*casos):
    return pd.DataFrame([
        {
            "tipo_atividade": "Venda Potenciais/Factíveis",
            "status_atividade": "Finalizada",
            "equipe": equipe,
            "codigo_descricao": codigo,
        }
        for equipe, codigo in casos
    ])


def _canais(df):
    return dict(zip(df["equipe"], df["canal"]))


def test_equipe_comum_e_comercial():
    resultado = filtrar_vendas(_linhas(("RIORECIN-001", "113001-VENDA")))
    assert _canais(resultado) == {"RIORECIN-001": "COMERCIAL"}


def test_equipe_vcg_e_vcg():
    resultado = filtrar_vendas(_linhas(("RIOVCGEXTIN-005", "113001-VENDA")))
    assert _canais(resultado) == {"RIOVCGEXTIN-005": "VCG"}


def test_riovcgvenin_com_113001_conta_como_comercial():
    """A exceção do DAX: equipe VCG, mas a venda é comercial."""
    resultado = filtrar_vendas(_linhas(("RIOVCGVENIN-002", "113001-VENDA POTENCIAL")))
    assert _canais(resultado) == {"RIOVCGVENIN-002": "COMERCIAL"}


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
