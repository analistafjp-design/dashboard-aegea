"""Camada de persistência (SQLite por padrão, PostgreSQL via DATABASE_URL)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
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


def criar_banco() -> None:
    """Cria as tabelas caso ainda não existam."""
    Base.metadata.create_all(engine)
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
