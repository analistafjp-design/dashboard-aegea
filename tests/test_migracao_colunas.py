"""Um banco criado por versão anterior precisa ganhar as colunas novas.

`create_all` só cria tabelas ausentes; ele nunca altera uma tabela que já
existe. Sem o alinhamento, quem já tinha o banco no disco via o painel
inteiro cair com "no such column" depois de atualizar o código.
"""
from datetime import date, datetime

import pytest
import sqlalchemy as sa

from app.models.db import alinhar_colunas, engine
from app.models.tabelas import FatoImplantacao


NOVAS = ("status_atividade", "inicio_sla", "fim_sla", "conta_realizado")


def _colunas(tabela: str) -> set[str]:
    return {c["name"] for c in sa.inspect(engine).get_columns(tabela)}


@pytest.fixture
def banco_da_versao_anterior():
    """Remove as colunas de SLA e deixa implantações já carregadas."""
    agora = datetime.now()
    with engine.begin() as c:
        for coluna in NOVAS:
            c.execute(sa.text(f"DROP INDEX IF EXISTS ix_fato_implantacao_{coluna}"))
        for coluna in NOVAS:
            c.execute(sa.text(f"ALTER TABLE fato_implantacao DROP COLUMN {coluna}"))
        for i in range(3):
            c.execute(sa.text(
                "INSERT INTO fato_implantacao"
                " (chave_unica, data, ano_mes, tipo, quantidade, faturado, importado_em)"
                " VALUES (:k, :d, :am, 'SERVICOS', 1.0, 0, :ts)"
            ), {"k": f"antiga{i}", "d": date.today(),
                "am": agora.strftime("%Y-%m"), "ts": agora})
    return agora


def test_colunas_novas_sao_criadas_no_banco_existente(banco_da_versao_anterior):
    assert not (_colunas("fato_implantacao") & set(NOVAS))

    alinhar_colunas()

    assert set(NOVAS) <= _colunas("fato_implantacao")


def test_linhas_antigas_recebem_o_default_do_modelo(banco_da_versao_anterior):
    """Sem o backfill, conta_realizado nasceria NULL e zeraria o realizado."""
    alinhar_colunas()

    with engine.connect() as c:
        valores = [linha[0] for linha in
                   c.execute(sa.text("SELECT conta_realizado FROM fato_implantacao"))]
    assert valores == [1, 1, 1]


def test_consulta_de_implantacao_volta_a_responder(banco_da_versao_anterior, cliente):
    alinhar_colunas()

    resposta = cliente.get("/api/modulo/implantacao")

    assert resposta.status_code == 200
    indicadores = resposta.json()["indicadores"]
    total = next(i["valor"] for i in indicadores if i["chave"] == "total_implantacao")
    assert total == 3.0  # as três linhas antigas seguem contando


def test_alinhar_e_idempotente(banco_da_versao_anterior):
    alinhar_colunas()
    antes = _colunas("fato_implantacao")

    alinhar_colunas()

    assert _colunas("fato_implantacao") == antes


def test_indices_das_colunas_novas_sao_recriados(banco_da_versao_anterior):
    alinhar_colunas()

    indices = {i["name"] for i in sa.inspect(engine).get_indexes("fato_implantacao")}
    esperados = {indice.name for indice in FatoImplantacao.__table__.indexes}
    assert esperados <= indices
