"""A implantação conta matrículas distintas, não linhas.

A mesma ligação reaparece na planilha quando a ordem é lançada em outra data
ou por outra equipe. Como a chave do fato inclui data, serviço e equipe, cada
lançamento virava uma linha e a ligação era contada duas vezes.
"""
from datetime import date

import pytest

from app.analytics import cache, implantacao
from app.analytics.base import Filtros
from app.models.db import sessao
from app.models.tabelas import DimCidade, DimEquipe, DimFrente, FatoImplantacao


MES = date(2026, 8, 1)


@pytest.fixture
def base():
    """Carrega implantações finalizadas e devolve o payload do módulo."""
    def montar(linhas):
        with sessao() as s:
            cidades, equipes, frentes = {}, {}, {}

            def _dim(cache_local, modelo, nome):
                if nome not in cache_local:
                    obj = modelo(nome=nome, chave=nome.upper().replace(" ", "_"))
                    s.add(obj)
                    s.flush()
                    cache_local[nome] = obj.id
                return cache_local[nome]

            for i, linha in enumerate(linhas):
                s.add(FatoImplantacao(
                    chave_unica=f"chave-{i}",
                    data=linha.get("data", MES.replace(day=10)),
                    ano_mes="2026-08",
                    cidade_id=_dim(cidades, DimCidade, linha.get("cidade", "Marica")),
                    equipe_id=_dim(equipes, DimEquipe, linha.get("equipe", "EQ-1")),
                    frente_id=_dim(frentes, DimFrente, linha.get("frente", "Servicos")),
                    tipo=linha.get("tipo", "SERVICOS"),
                    matricula=linha.get("matricula"),
                    servico=linha.get("servico", "117007-LIGACAO"),
                    protocolo=linha.get("protocolo"),
                    status_atividade="FINALIZADA",
                    conta_realizado=linha.get("conta_realizado", True),
                    quantidade=1.0,
                ))
            s.commit()
        cache.invalidar()
        return implantacao.calcular(Filtros(ano=2026, mes=8))
    return montar


def _indicador(payload, chave):
    return next(i["valor"] for i in payload["indicadores"] if i["chave"] == chave)


def test_mesma_matricula_em_datas_diferentes_conta_uma_vez(base):
    """O caso real: mesma ligação, mesmo serviço, duas datas e duas equipes."""
    payload = base([
        {"matricula": "103139478", "data": MES.replace(day=21), "equipe": "Riomltin-020"},
        {"matricula": "103139478", "data": MES.replace(day=23), "equipe": "Riomltin-019"},
        {"matricula": "103139479", "data": MES.replace(day=21), "equipe": "Riomltin-020"},
    ])

    assert _indicador(payload, "impl_servicos") == 2
    assert _indicador(payload, "total_implantacao") == 2


def test_geral_e_a_soma_de_servicos_e_vcg(base):
    payload = base([
        {"matricula": "1", "tipo": "SERVICOS"},
        {"matricula": "2", "tipo": "SERVICOS"},
        {"matricula": "3", "tipo": "VCG", "frente": "VCG Rio Bonito"},
    ])

    assert _indicador(payload, "impl_servicos") == 2
    assert _indicador(payload, "impl_vcg") == 1
    assert _indicador(payload, "total_implantacao") == 3


def test_ordem_em_aberto_nao_entra_no_realizado(base):
    payload = base([
        {"matricula": "1"},
        {"matricula": "2", "conta_realizado": False},
    ])

    assert _indicador(payload, "total_implantacao") == 1


def test_ranking_por_cidade_tambem_conta_distinto(base):
    payload = base([
        {"matricula": "1", "cidade": "Marica", "data": MES.replace(day=5)},
        {"matricula": "1", "cidade": "Marica", "data": MES.replace(day=9)},
        {"matricula": "2", "cidade": "Marica"},
        {"matricula": "3", "cidade": "Itaborai"},
    ])

    por_cidade = {linha["cidade"]: linha["total"] for linha in payload["por_cidade"]}
    assert por_cidade["Marica"] == 2
    assert por_cidade["Itaborai"] == 1


def test_linha_sem_matricula_continua_valendo(base):
    """Sem identificador não dá para agrupar; descartar esconderia produção."""
    payload = base([
        {"matricula": None},
        {"matricula": None},
        {"matricula": "1"},
    ])

    assert _indicador(payload, "total_implantacao") == 3


def test_media_por_dia_usa_o_total_distinto(base):
    # Duas ligações distintas em duas datas: 2 / 2 = 1,0 por dia.
    payload = base([
        {"matricula": "1", "data": MES.replace(day=10)},
        {"matricula": "1", "data": MES.replace(day=11)},
        {"matricula": "2", "data": MES.replace(day=11)},
    ])

    assert _indicador(payload, "impl_servicos") == 2
    assert _indicador(payload, "impl_servicos_dia") == pytest.approx(1.0)


def test_protocolo_tem_prioridade_sobre_matricula(base):
    """A medida do PBIX conta Cód. Protocolo Origem, não matrícula."""
    payload = base([
        {"matricula": "1", "protocolo": "P-100"},
        {"matricula": "2", "protocolo": "P-100"},  # mesmo protocolo
        {"matricula": "3", "protocolo": "P-200"},
    ])

    assert _indicador(payload, "total_implantacao") == 2


def test_sem_protocolo_a_matricula_segue_valendo(base):
    payload = base([
        {"matricula": "1", "protocolo": None},
        {"matricula": "1", "protocolo": None, "data": MES.replace(day=12)},
        {"matricula": "2", "protocolo": None},
    ])

    assert _indicador(payload, "total_implantacao") == 2
