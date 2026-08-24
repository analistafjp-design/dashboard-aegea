"""Camada de persistência (SQLite por padrão, PostgreSQL via DATABASE_URL)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import config
from app.models.base import Base
from app.models import tabelas  # noqa: F401  (registra os modelos no metadata)
from app.utils.log import get_logger

logger = get_logger("db")

_conectar_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine: Engine = create_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_conectar_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@event.listens_for(Engine, "connect")
def _ajustes_sqlite(dbapi_connection, connection_record):  # pragma: no cover - infra
    if config.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _ddl_valor(valor: object) -> str | None:
    """Traduz um default do modelo para literal SQL, ou None se não der."""
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, str):
        return "'" + valor.replace("'", "''") + "'"
    return None


def alinhar_colunas() -> None:
    """Acrescenta ao banco já existente as colunas novas do modelo.

    `create_all` só cria tabelas que faltam — ele nunca altera uma tabela que
    já existe. Sem isto, um banco criado por uma versão anterior continua sem
    as colunas novas e toda consulta que as seleciona quebra com
    "no such column", derrubando o painel inteiro.
    """
    inspetor = inspect(engine)
    existentes = set(inspetor.get_table_names())

    for tabela in Base.metadata.sorted_tables:
        if tabela.name not in existentes:
            continue  # recém-criada por create_all, já veio completa
        no_banco = {c["name"] for c in inspetor.get_columns(tabela.name)}
        faltando = [c for c in tabela.columns if c.name not in no_banco]
        if not faltando:
            continue

        for coluna in faltando:
            tipo = coluna.type.compile(engine.dialect)
            with engine.begin() as conexao:
                conexao.execute(text(
                    f"ALTER TABLE {tabela.name} ADD COLUMN {coluna.name} {tipo}"
                ))
                # As linhas antigas ficam NULL. Quando o modelo declara um
                # default, ele é a leitura correta do passado — sem isso um
                # booleano como conta_realizado nasceria falso e zeraria os
                # totais já carregados.
                padrao = getattr(coluna.default, "arg", None)
                literal = _ddl_valor(padrao) if coluna.default is not None else None
                if literal is not None:
                    conexao.execute(text(
                        f"UPDATE {tabela.name} SET {coluna.name} = {literal} "
                        f"WHERE {coluna.name} IS NULL"
                    ))
            logger.info("Coluna %s.%s criada no banco existente",
                        tabela.name, coluna.name)

        for indice in tabela.indexes:
            indice.create(engine, checkfirst=True)


def criar_banco() -> None:
    """Cria as tabelas caso ainda não existam e alinha colunas novas."""
    Base.metadata.create_all(engine)
    alinhar_colunas()
    logger.info("Banco de dados pronto em %s", config.DATABASE_URL)


@contextmanager
def sessao() -> Iterator[Session]:
    """Sessão transacional: commit no sucesso, rollback em qualquer exceção."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_sessao() -> Iterator[Session]:
    """Dependência do FastAPI."""
    with sessao() as s:
        yield s
