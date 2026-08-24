"""Cobertura do acompanhamento de SLA das implantações."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from app.analytics import sla_implantacao
from app.analytics.base import Filtros


AGORA = datetime(2026, 8, 24, 12, 0, 0)
PERIODO = SimpleNamespace(ano=AGORA.year, mes=AGORA.month, ano_mes="2026-08")


def _linha(**campos):
    """Uma ordem de implantação com os campos que o painel consulta."""
    base = {
        "data": AGORA.date(),
        "ano_mes": "2026-08",
        "cidade": "Rio Bonito",
        "equipe": "EQUIPE 1",
        "frente": "Serviços",
        "matricula": "123",
        "status_atividade": "EM EXECUCAO",
        "inicio_sla": AGORA - timedelta(days=5),
        "fim_sla": AGORA + timedelta(days=5),
    }
    return base | campos


@pytest.fixture
def base(monkeypatch):
    """Injeta uma base de implantação e congela a data de referência."""
    def instalar(linhas):
        df = pd.DataFrame([_linha(**linha) for linha in linhas])
        monkeypatch.setattr(sla_implantacao.consultas, "dados", lambda *_, **__: df)
        monkeypatch.setattr(sla_implantacao, "_data_referencia", lambda _: AGORA)
        return sla_implantacao.calcular(Filtros(), periodo=PERIODO)
    return instalar


def test_base_vazia_nao_inventa_atraso(monkeypatch):
    monkeypatch.setattr(sla_implantacao.consultas, "dados",
                        lambda *_, **__: pd.DataFrame())
    resultado = sla_implantacao.calcular(Filtros(), periodo=PERIODO)
    assert resultado["vencidas"] == 0
    assert resultado["a_vencer"] == 0
    assert resultado["cidade_mais_critica"] is None


def test_prazo_no_passado_conta_como_vencida(base):
    resultado = base([{"fim_sla": AGORA - timedelta(hours=1)}])
    assert resultado["vencidas"] == 1
    assert resultado["a_vencer"] == 0


def test_prazo_dentro_da_janela_de_48h_conta_como_a_vencer(base):
    resultado = base([{
        "inicio_sla": AGORA - timedelta(days=30),
        "fim_sla": AGORA + timedelta(hours=10),
    }])
    assert resultado["vencidas"] == 0
    assert resultado["a_vencer"] == 1


def test_oitenta_por_cento_consumido_conta_como_a_vencer(base):
    # 100 dias de prazo, 85 já corridos: fora da janela de 48h, mas crítico.
    resultado = base([{
        "inicio_sla": AGORA - timedelta(days=85),
        "fim_sla": AGORA + timedelta(days=15),
    }])
    assert resultado["a_vencer"] == 1
    assert resultado["detalhes"][0]["percentual_consumido"] == pytest.approx(85, abs=1)


def test_ordem_folgada_nao_entra_no_painel(base):
    resultado = base([{
        "inicio_sla": AGORA - timedelta(days=1),
        "fim_sla": AGORA + timedelta(days=90),
    }])
    assert resultado["vencidas"] == 0
    assert resultado["a_vencer"] == 0
    assert resultado["por_cidade"] == []
    assert resultado["total"] == 1  # segue aberta, só não é crítica


def test_ordem_finalizada_sai_do_acompanhamento(base):
    resultado = base([{
        "status_atividade": "FINALIZADA",
        "fim_sla": AGORA - timedelta(days=10),
    }])
    assert resultado["vencidas"] == 0
    assert resultado["total"] == 0


def test_ordem_sem_prazo_nao_vira_atraso(base):
    resultado = base([
        {"inicio_sla": None, "fim_sla": None},
        {"inicio_sla": AGORA - timedelta(days=2), "fim_sla": None},
    ])
    assert resultado["vencidas"] == 0
    assert resultado["a_vencer"] == 0
    # Sem prazo nenhum: o painel precisa poder dizer que falta dado em vez de
    # deixar o gestor concluir que está tudo em dia.
    assert resultado["total"] == 2
    assert resultado["com_prazo"] == 0


def test_com_prazo_separa_falta_de_dado_de_tudo_em_dia(base):
    resultado = base([
        {"inicio_sla": None, "fim_sla": None},
        {"inicio_sla": AGORA - timedelta(days=1), "fim_sla": AGORA + timedelta(days=90)},
    ])
    assert resultado["vencidas"] == 0
    assert resultado["a_vencer"] == 0
    assert resultado["total"] == 2
    assert resultado["com_prazo"] == 1


def test_ranking_traz_so_cidades_com_pendencia_e_a_pior_primeiro(base):
    resultado = base([
        {"cidade": "Maricá", "fim_sla": AGORA - timedelta(days=3)},
        {"cidade": "Maricá", "fim_sla": AGORA - timedelta(days=1)},
        {"cidade": "Itaboraí", "fim_sla": AGORA + timedelta(hours=5)},
        # Cidade inteiramente dentro do prazo não deve aparecer.
        {"cidade": "Niterói", "fim_sla": AGORA + timedelta(days=90),
         "inicio_sla": AGORA - timedelta(days=1)},
    ])

    cidades = [linha["cidade"] for linha in resultado["por_cidade"]]
    assert cidades == ["Maricá", "Itaboraí"]
    assert resultado["cidade_mais_critica"] == "Maricá"
    assert resultado["por_cidade"][0]["vencidas"] == 2
    assert resultado["por_cidade"][1]["proximas"] == 1
    assert resultado["cidades"] == 2


def test_detalhes_trazem_as_vencidas_primeiro_e_a_mais_atrasada_no_topo(base):
    resultado = base([
        {"matricula": "recente", "fim_sla": AGORA - timedelta(days=1)},
        {"matricula": "antiga", "fim_sla": AGORA - timedelta(days=30)},
        {"matricula": "proxima", "fim_sla": AGORA + timedelta(hours=6)},
    ])

    situacoes = [linha["situacao"] for linha in resultado["detalhes"]]
    assert situacoes == ["VENCIDO", "VENCIDO", "PROXIMO"]
    assert resultado["detalhes"][0]["matricula"] == "antiga"
    assert resultado["detalhes"][0]["tempo_restante_horas"] < 0


def test_datas_saem_como_texto_para_o_json(base):
    resultado = base([{"fim_sla": AGORA - timedelta(days=1)}])
    detalhe = resultado["detalhes"][0]
    assert isinstance(detalhe["fim_sla"], str)
    assert detalhe["fim_sla"].startswith("2026-08-23")
