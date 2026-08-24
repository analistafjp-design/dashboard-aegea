"""Agregação de cada medida de implantação do PBIX.

`Implantação Mês - Serviços` soma [Total Implantação] (COUNTROWS) e
`Implantação Mês - VCG` usa DISTINCTCOUNT(Interior[Matrícula]) — agregações
diferentes de propósito. As duas recortam por CONTAINSSTRING(Frente, ...).
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
                    ano_mes=linha.get("data", MES.replace(day=10)).strftime("%Y-%m"),
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


def test_servicos_conta_linhas_e_nao_matriculas_distintas(base):
    """Serviços usa COUNTROWS: duas execuções da mesma ligação valem duas."""
    payload = base([
        {"matricula": "103139478", "data": MES.replace(day=21), "equipe": "Riomltin-020"},
        {"matricula": "103139478", "data": MES.replace(day=23), "equipe": "Riomltin-019"},
        {"matricula": "103139479", "data": MES.replace(day=21), "equipe": "Riomltin-020"},
    ])

    assert _indicador(payload, "impl_servicos") == 3
    assert _indicador(payload, "total_implantacao") == 3


def test_vcg_conta_matriculas_distintas(base):
    """VCG usa DISTINCTCOUNT(Matrícula): a mesma ligação vale uma."""
    payload = base([
        {"matricula": "1", "frente": "VCG Rio Bonito", "data": MES.replace(day=21)},
        {"matricula": "1", "frente": "VCG Rio Bonito", "data": MES.replace(day=23)},
        {"matricula": "2", "frente": "VCG Rio Bonito", "data": MES.replace(day=21)},
    ])

    assert _indicador(payload, "impl_vcg") == 2


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
        {"matricula": None, "frente": "VCG"},
        {"matricula": None, "frente": "VCG"},
        {"matricula": "1", "frente": "VCG"},
    ])

    assert _indicador(payload, "impl_vcg") == 3


def test_media_por_dia_divide_pelas_datas_distintas(base):
    # 3 linhas em 2 datas distintas: 3 / 2 = 1,5 por dia.
    payload = base([
        {"matricula": "1", "data": MES.replace(day=10)},
        {"matricula": "1", "data": MES.replace(day=11)},
        {"matricula": "2", "data": MES.replace(day=11)},
    ])

    assert _indicador(payload, "impl_servicos") == 3
    assert _indicador(payload, "impl_servicos_dia") == pytest.approx(1.5)


def test_vcg_agrupa_por_matricula_e_nao_por_protocolo(base):
    """A medida de VCG conta DISTINCTCOUNT(Interior[Matrícula])."""
    payload = base([
        {"matricula": "1", "protocolo": "P-100", "frente": "VCG"},
        {"matricula": "2", "protocolo": "P-100", "frente": "VCG"},  # mesmo protocolo
        {"matricula": "3", "protocolo": "P-200", "frente": "VCG"},
    ])

    assert _indicador(payload, "impl_vcg") == 3


def test_frente_fora_de_servicos_e_vcg_nao_entra_em_nenhuma_medida(base):
    """As medidas recortam por CONTAINSSTRING(Frente, ...).

    A frente `Venda` não contém "Serviços" nem "VCG", então essas linhas
    ficam fora das duas — e, por consequência, fora do Geral.
    """
    payload = base([
        {"matricula": "1", "frente": "Serviços"},
        {"matricula": "2", "frente": "VCG Rio Bonito"},
        {"matricula": "3", "frente": "Venda"},
        {"matricula": "4", "frente": "Não Informado"},
    ])

    assert _indicador(payload, "impl_servicos") == 1
    assert _indicador(payload, "impl_vcg") == 1
    assert _indicador(payload, "total_implantacao") == 2


def test_todas_as_frentes_com_vcg_no_nome_somam_em_vcg(base):
    payload = base([
        {"matricula": "1", "frente": "VCG"},
        {"matricula": "2", "frente": "VCG Rio Bonito"},
        {"matricula": "3", "frente": "VCG Bairro Legal/SFI"},
    ])

    assert _indicador(payload, "impl_vcg") == 3
    assert _indicador(payload, "impl_servicos") is None


def test_filtro_de_mes_separa_cada_mes(base):
    """Cada mês responde só pelo que é dele — o filtro não soma o histórico."""
    from app.analytics import implantacao as modulo

    payload = base([
        {"matricula": f"jul-{i}", "data": date(2026, 7, 15)} for i in range(100)
    ] + [
        {"matricula": f"ago-{i}", "data": MES.replace(day=15)} for i in range(175)
    ])
    del payload  # o interesse está nas duas consultas abaixo

    julho = modulo.calcular(Filtros(ano=2026, mes=7))
    agosto = modulo.calcular(Filtros(ano=2026, mes=8))

    assert _indicador(julho, "impl_servicos") == 100
    assert _indicador(agosto, "impl_servicos") == 175
