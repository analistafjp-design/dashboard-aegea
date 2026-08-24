"""Regras de implantação da especificação (seção 5).

- só status Finalizada;
- Ligação de Água e Ligação de Esgoto;
- a mesma matrícula não se repete dentro do mês e da frente;
- VCG são RIOVCGPOPIN, RIOVCGEXTIN e RIOVCGVENIN — as demais equipes são
  Serviços;
- Implantação Geral = Serviços + VCG;
- média diária = realizado / dias úteis decorridos.
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
                dia = linha.get("data", MES.replace(day=10))
                equipe = linha.get("equipe", "RIOMLTIN-001")
                s.add(FatoImplantacao(
                    chave_unica=f"chave-{i}",
                    data=dia,
                    ano_mes=dia.strftime("%Y-%m"),
                    cidade_id=_dim(cidades, DimCidade, linha.get("cidade", "Marica")),
                    equipe_id=_dim(equipes, DimEquipe, equipe),
                    frente_id=_dim(frentes, DimFrente, linha.get("frente", "Serviços")),
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


def test_mesma_matricula_no_mes_conta_uma_vez(base):
    """O caso real: a ordem reaparece no arquivo diário seguinte."""
    payload = base([
        {"matricula": "103139478", "data": MES.replace(day=21), "equipe": "RIOMLTIN-020"},
        {"matricula": "103139478", "data": MES.replace(day=23), "equipe": "RIOMLTIN-019"},
        {"matricula": "103139479", "data": MES.replace(day=21), "equipe": "RIOMLTIN-020"},
    ])

    assert _indicador(payload, "impl_servicos") == 2
    assert _indicador(payload, "total_implantacao") == 2


def test_vcg_e_servicos_nao_se_misturam_na_deduplicacao(base):
    """A regra é por mês E frente: a mesma matrícula conta em cada uma."""
    payload = base([
        {"matricula": "1", "equipe": "RIOMLTIN-001"},
        {"matricula": "1", "equipe": "RIOVCGEXTIN-005"},
    ])

    assert _indicador(payload, "impl_servicos") == 1
    assert _indicador(payload, "impl_vcg") == 1
    assert _indicador(payload, "total_implantacao") == 2


def test_apenas_as_tres_equipes_vcg_contam_como_vcg(base):
    payload = base([
        {"matricula": "1", "equipe": "RIOVCGPOPIN-001"},
        {"matricula": "2", "equipe": "RIOVCGEXTIN-002"},
        {"matricula": "3", "equipe": "RIOVCGVENIN-003"},
    ])

    assert _indicador(payload, "impl_vcg") == 3
    assert _indicador(payload, "impl_servicos") is None


def test_demais_equipes_entram_em_servicos(base):
    """Inclusive as de venda, que a frente gravada chama de `Venda`."""
    payload = base([
        {"matricula": "1", "equipe": "RIOMLTIN-001", "frente": "Serviços"},
        {"matricula": "2", "equipe": "RIORECIN-004", "frente": "Venda"},
        {"matricula": "3", "equipe": "RIOCOMIN-007", "frente": "Não Informado"},
    ])

    assert _indicador(payload, "impl_servicos") == 3
    assert _indicador(payload, "impl_vcg") is None


def test_geral_e_a_soma_de_servicos_e_vcg(base):
    payload = base([
        {"matricula": "1", "equipe": "RIOMLTIN-001"},
        {"matricula": "2", "equipe": "RIOMLTIN-001"},
        {"matricula": "3", "equipe": "RIOVCGEXTIN-005"},
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

    assert _indicador(payload, "impl_servicos") == 3


def test_media_diaria_divide_pelos_dias_uteis(base):
    payload = base([
        {"matricula": "1", "data": MES.replace(day=10)},
        {"matricula": "2", "data": MES.replace(day=11)},
    ])

    dias_uteis = payload["periodo"]["dias_uteis_decorridos"]
    assert _indicador(payload, "impl_servicos_dia") == pytest.approx(2 / dias_uteis)


def test_filtro_de_mes_separa_cada_mes(base):
    """Cada mês responde só pelo que é dele — o filtro não soma o histórico."""
    base([
        {"matricula": f"jul-{i}", "data": date(2026, 7, 15)} for i in range(100)
    ] + [
        {"matricula": f"ago-{i}", "data": MES.replace(day=15)} for i in range(175)
    ])

    julho = implantacao.calcular(Filtros(ano=2026, mes=7))
    agosto = implantacao.calcular(Filtros(ano=2026, mes=8))

    assert _indicador(julho, "impl_servicos") == 100
    assert _indicador(agosto, "impl_servicos") == 175


def test_mesma_matricula_em_meses_diferentes_conta_nos_dois(base):
    """A regra é por mês: julho e agosto são contextos distintos."""
    base([
        {"matricula": "1", "data": date(2026, 7, 15)},
        {"matricula": "1", "data": MES.replace(day=15)},
    ])

    assert _indicador(implantacao.calcular(Filtros(ano=2026, mes=7)), "impl_servicos") == 1
    assert _indicador(implantacao.calcular(Filtros(ano=2026, mes=8)), "impl_servicos") == 1
