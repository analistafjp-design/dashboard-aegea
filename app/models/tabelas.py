"""Modelo dimensional do Dashboard Executivo.

Esquema estrela simples: dimensões compartilhadas + uma tabela fato por
módulo. Os três módulos (Termos/Faturamento, Venda/Implantação e
Programação) permanecem em fatos separados — nenhum registro é misturado
entre módulos, conforme a regra de negócio do projeto.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# ---------------------------------------------------------------- dimensões


class DimCalendario(Base):
    __tablename__ = "dim_calendario"

    data: Mapped[date] = mapped_column(Date, primary_key=True)
    ano: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)
    nome_mes: Mapped[str] = mapped_column(String(20))
    ano_mes: Mapped[str] = mapped_column(String(7), index=True)  # 2026-08
    rotulo_mes: Mapped[str] = mapped_column(String(20))          # ago/2026
    dia: Mapped[int] = mapped_column(Integer)
    dia_semana: Mapped[int] = mapped_column(Integer)             # 0=segunda
    nome_dia_semana: Mapped[str] = mapped_column(String(20))
    dia_util: Mapped[bool] = mapped_column(Boolean, index=True)
    feriado: Mapped[bool] = mapped_column(Boolean, default=False)
    nome_feriado: Mapped[str | None] = mapped_column(String(60), nullable=True)
    trimestre: Mapped[int] = mapped_column(Integer)


class _DimNome(Base):
    """Dimensão genérica de rótulo único (cidade, equipe, frente...)."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    chave: Mapped[str] = mapped_column(String(120), unique=True, index=True)


class DimCidade(_DimNome):
    __tablename__ = "dim_cidade"


class DimEquipe(_DimNome):
    __tablename__ = "dim_equipe"


class DimFrente(_DimNome):
    """Comercial, VCG, Serviços, VCG Rio Bonito, VCG SFI, Outros Canais."""

    __tablename__ = "dim_frente"


class DimRegiao(_DimNome):
    __tablename__ = "dim_regiao"


class DimProjeto(_DimNome):
    __tablename__ = "dim_projeto"


class DimSetor(_DimNome):
    """Setor do Recurso (PBIX 1)."""

    __tablename__ = "dim_setor"


# -------------------------------------------------------------------- fatos


class FatoTermos(Base):
    """PBIX 1 — Termos Aplicados."""

    __tablename__ = "fato_termos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_unica: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    ano_mes: Mapped[str] = mapped_column(String(7), index=True)
    cidade_id: Mapped[int | None] = mapped_column(ForeignKey("dim_cidade.id"), index=True)
    equipe_id: Mapped[int | None] = mapped_column(ForeignKey("dim_equipe.id"), index=True)
    frente_id: Mapped[int | None] = mapped_column(ForeignKey("dim_frente.id"), index=True)
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("dim_setor.id"), index=True)
    matricula: Mapped[str | None] = mapped_column(String(60), index=True)
    tipo: Mapped[str] = mapped_column(String(20), index=True)      # SERVICOS | VCG
    status_termo: Mapped[str] = mapped_column(String(40), index=True)
    quantidade: Mapped[float] = mapped_column(Float, default=1.0)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    origem_arquivo: Mapped[str | None] = mapped_column(String(255))
    importado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class FatoFaturamento(Base):
    """PBIX 1 — Faturamento de Termos."""

    __tablename__ = "fato_faturamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_unica: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    ano_mes: Mapped[str] = mapped_column(String(7), index=True)
    inicio_mes: Mapped[date] = mapped_column(Date, index=True)
    cidade_id: Mapped[int | None] = mapped_column(ForeignKey("dim_cidade.id"), index=True)
    situacao: Mapped[str] = mapped_column(String(40), index=True)
    situacao_termo: Mapped[str | None] = mapped_column(String(40), index=True)
    numero_termo: Mapped[str | None] = mapped_column(String(60), index=True)
    quantidade: Mapped[float] = mapped_column(Float, default=1.0)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    origem_arquivo: Mapped[str | None] = mapped_column(String(255))
    importado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class FatoVendas(Base):
    """PBIX 2 — Venda."""

    __tablename__ = "fato_vendas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_unica: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    ano_mes: Mapped[str] = mapped_column(String(7), index=True)
    cidade_id: Mapped[int | None] = mapped_column(ForeignKey("dim_cidade.id"), index=True)
    equipe_id: Mapped[int | None] = mapped_column(ForeignKey("dim_equipe.id"), index=True)
    frente_id: Mapped[int | None] = mapped_column(ForeignKey("dim_frente.id"), index=True)
    canal: Mapped[str] = mapped_column(String(30), index=True)  # COMERCIAL|VCG|OUTROS
    matricula: Mapped[str | None] = mapped_column(String(60), index=True)
    quantidade: Mapped[float] = mapped_column(Float, default=1.0)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    origem_arquivo: Mapped[str | None] = mapped_column(String(255))
    importado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class FatoImplantacao(Base):
    """PBIX 2 — Implantação."""

    __tablename__ = "fato_implantacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_unica: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    ano_mes: Mapped[str] = mapped_column(String(7), index=True)
    cidade_id: Mapped[int | None] = mapped_column(ForeignKey("dim_cidade.id"), index=True)
    equipe_id: Mapped[int | None] = mapped_column(ForeignKey("dim_equipe.id"), index=True)
    frente_id: Mapped[int | None] = mapped_column(ForeignKey("dim_frente.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), index=True)  # SERVICOS | VCG
    matricula: Mapped[str | None] = mapped_column(String(60), index=True)
    servico: Mapped[str | None] = mapped_column(String(120))
    faturado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    quantidade: Mapped[float] = mapped_column(Float, default=1.0)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_atividade: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    inicio_sla: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    fim_sla: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    conta_realizado: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    origem_arquivo: Mapped[str | None] = mapped_column(String(255))
    importado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class FatoFaturamentoImplantacao(Base):
    """Base de faturamento usada pelo PBIX Venda e Implantação."""

    __tablename__ = "fato_faturamento_implantacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_unica: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    ano_mes: Mapped[str] = mapped_column(String(7), index=True)
    ligacao: Mapped[str] = mapped_column(String(80), index=True)
    tipo_solicitacao: Mapped[str] = mapped_column(String(180), index=True)
    ocorrencia: Mapped[str] = mapped_column(String(80), index=True)
    departamento: Mapped[str] = mapped_column(String(120), index=True)
    frente: Mapped[str] = mapped_column(String(40), index=True)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    faturado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    origem_arquivo: Mapped[str | None] = mapped_column(String(255))
    importado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class FatoProgramacao(Base):
    """PBIX 3 — Programação Diária."""

    __tablename__ = "fato_programacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_unica: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    ano_mes: Mapped[str] = mapped_column(String(7), index=True)
    regiao_id: Mapped[int | None] = mapped_column(ForeignKey("dim_regiao.id"), index=True)
    equipe_id: Mapped[int | None] = mapped_column(ForeignKey("dim_equipe.id"), index=True)
    projeto_id: Mapped[int | None] = mapped_column(ForeignKey("dim_projeto.id"), index=True)
    cidade_id: Mapped[int | None] = mapped_column(ForeignKey("dim_cidade.id"), index=True)
    recurso: Mapped[str | None] = mapped_column(String(120), index=True)
    qtd_os: Mapped[float] = mapped_column(Float, default=0.0)
    origem_arquivo: Mapped[str | None] = mapped_column(String(255))
    importado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Meta(Base):
    """Metas oficiais. Nunca são estimadas — só existem se vierem dos dados."""

    __tablename__ = "metas"
    __table_args__ = (
        UniqueConstraint(
            "ano", "mes", "modulo", "segmento", "cidade_id", "equipe_id",
            name="uq_meta_dimensao",
        ),
        Index("ix_meta_periodo", "ano", "mes", "modulo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ano: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    modulo: Mapped[str] = mapped_column(String(20))    # TERMOS|VENDA|IMPLANTACAO
    segmento: Mapped[str] = mapped_column(String(30), default="TOTAL")
    cidade_id: Mapped[int | None] = mapped_column(ForeignKey("dim_cidade.id"))
    equipe_id: Mapped[int | None] = mapped_column(ForeignKey("dim_equipe.id"))
    valor_meta: Mapped[float] = mapped_column(Float)
    origem_arquivo: Mapped[str | None] = mapped_column(String(255))
    importado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class HistoricoUpload(Base):
    __tablename__ = "historico_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    arquivo: Mapped[str] = mapped_column(String(255))
    dataset: Mapped[str] = mapped_column(String(40))
    registros_lidos: Mapped[int] = mapped_column(Integer, default=0)
    registros_inseridos: Mapped[int] = mapped_column(Integer, default=0)
    registros_atualizados: Mapped[int] = mapped_column(Integer, default=0)
    registros_ignorados: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20))  # SUCESSO|ATENCAO|ERRO
    mensagem: Mapped[str | None] = mapped_column(String(1000))
    usuario: Mapped[str] = mapped_column(String(80), default="local")


class Configuracao(Base):
    """Preferências salvas na página Configurações."""

    __tablename__ = "configuracoes"

    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(500))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


DIMENSOES_NOMEADAS = {
    "cidade": DimCidade,
    "equipe": DimEquipe,
    "frente": DimFrente,
    "regiao": DimRegiao,
    "projeto": DimProjeto,
    "setor": DimSetor,
}

TABELAS_FATO = {
    "termos": FatoTermos,
    "faturamento": FatoFaturamento,
    "vendas": FatoVendas,
    "implantacao": FatoImplantacao,
    "programacao": FatoProgramacao,
}
