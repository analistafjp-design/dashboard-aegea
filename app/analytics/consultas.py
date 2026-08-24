"""Acesso aos dados: cada fato vira um DataFrame já com os nomes das
dimensões resolvidos e os filtros globais aplicados."""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.analytics import cache
from app.analytics.base import Filtros
from app.models.db import engine
from app.models.tabelas import (
    DimCidade,
    DimEquipe,
    DimFrente,
    DimProjeto,
    DimRegiao,
    DimSetor,
    FatoFaturamento,
    FatoFaturamentoImplantacao,
    FatoImplantacao,
    FatoProgramacao,
    FatoTermos,
    FatoVendas,
    HistoricoUpload,
    Meta,
)
from app.utils.log import get_logger

logger = get_logger("consultas")


def _stmt_termos():
    cidade, equipe, frente, setor = (aliased(DimCidade), aliased(DimEquipe),
                                     aliased(DimFrente), aliased(DimSetor))
    return (
        select(
            FatoTermos.data, FatoTermos.ano_mes, FatoTermos.tipo,
            FatoTermos.status_termo, FatoTermos.quantidade, FatoTermos.valor,
            FatoTermos.matricula, FatoTermos.origem_arquivo, FatoTermos.importado_em,
            cidade.nome.label("cidade"), equipe.nome.label("equipe"),
            frente.nome.label("frente"), setor.nome.label("setor"),
        )
        .join(cidade, FatoTermos.cidade_id == cidade.id, isouter=True)
        .join(equipe, FatoTermos.equipe_id == equipe.id, isouter=True)
        .join(frente, FatoTermos.frente_id == frente.id, isouter=True)
        .join(setor, FatoTermos.setor_id == setor.id, isouter=True)
    )


def _stmt_faturamento():
    cidade = aliased(DimCidade)
    return (
        select(
            FatoFaturamento.data, FatoFaturamento.ano_mes, FatoFaturamento.inicio_mes,
            FatoFaturamento.situacao, FatoFaturamento.numero_termo,
            FatoFaturamento.quantidade, FatoFaturamento.valor,
            cidade.nome.label("cidade"),
        )
        .join(cidade, FatoFaturamento.cidade_id == cidade.id, isouter=True)
    )


def _stmt_vendas():
    cidade, equipe, frente = aliased(DimCidade), aliased(DimEquipe), aliased(DimFrente)
    return (
        select(
            FatoVendas.data, FatoVendas.ano_mes, FatoVendas.canal,
            FatoVendas.conta_comercial, FatoVendas.conta_vcg,
            FatoVendas.tipo_atividade, FatoVendas.codigo_descricao,
            FatoVendas.quantidade, FatoVendas.valor, FatoVendas.matricula,
            FatoVendas.origem_arquivo, FatoVendas.importado_em,
            cidade.nome.label("cidade"), equipe.nome.label("equipe"),
            frente.nome.label("frente"),
        )
        .join(cidade, FatoVendas.cidade_id == cidade.id, isouter=True)
        .join(equipe, FatoVendas.equipe_id == equipe.id, isouter=True)
        .join(frente, FatoVendas.frente_id == frente.id, isouter=True)
    )


def _stmt_implantacao():
    cidade, equipe, frente = aliased(DimCidade), aliased(DimEquipe), aliased(DimFrente)
    return (
        select(
            FatoImplantacao.data, FatoImplantacao.ano_mes, FatoImplantacao.tipo,
            FatoImplantacao.faturado, FatoImplantacao.servico,
            FatoImplantacao.quantidade, FatoImplantacao.valor, FatoImplantacao.matricula,
            FatoImplantacao.protocolo,
            FatoImplantacao.status_atividade, FatoImplantacao.inicio_sla,
            FatoImplantacao.fim_sla, FatoImplantacao.conta_realizado,
            FatoImplantacao.origem_arquivo, FatoImplantacao.importado_em,
            cidade.nome.label("cidade"), equipe.nome.label("equipe"),
            frente.nome.label("frente"),
        )
        .join(cidade, FatoImplantacao.cidade_id == cidade.id, isouter=True)
        .join(equipe, FatoImplantacao.equipe_id == equipe.id, isouter=True)
        .join(frente, FatoImplantacao.frente_id == frente.id, isouter=True)
    )


def _stmt_faturamento_implantacao():
    return select(
        FatoFaturamentoImplantacao.data,
        FatoFaturamentoImplantacao.ano_mes,
        FatoFaturamentoImplantacao.ligacao,
        FatoFaturamentoImplantacao.tipo_solicitacao,
        FatoFaturamentoImplantacao.ocorrencia,
        FatoFaturamentoImplantacao.departamento,
        FatoFaturamentoImplantacao.frente,
        FatoFaturamentoImplantacao.valor,
        FatoFaturamentoImplantacao.faturado,
    )


def _stmt_programacao():
    cidade, equipe, regiao, projeto = (aliased(DimCidade), aliased(DimEquipe),
                                       aliased(DimRegiao), aliased(DimProjeto))
    return (
        select(
            FatoProgramacao.data, FatoProgramacao.ano_mes, FatoProgramacao.qtd_os,
            FatoProgramacao.recurso,
            cidade.nome.label("cidade"), equipe.nome.label("equipe"),
            regiao.nome.label("regiao"), projeto.nome.label("projeto"),
        )
        .join(cidade, FatoProgramacao.cidade_id == cidade.id, isouter=True)
        .join(equipe, FatoProgramacao.equipe_id == equipe.id, isouter=True)
        .join(regiao, FatoProgramacao.regiao_id == regiao.id, isouter=True)
        .join(projeto, FatoProgramacao.projeto_id == projeto.id, isouter=True)
    )


_CONSTRUTORES = {
    "termos": _stmt_termos,
    "faturamento": _stmt_faturamento,
    "vendas": _stmt_vendas,
    "implantacao": _stmt_implantacao,
    "faturamento_implantacao": _stmt_faturamento_implantacao,
    "programacao": _stmt_programacao,
}

# Quais filtros cada base entende (os demais são ignorados por não existirem lá).
COLUNAS_FILTRAVEIS = {
    "termos": ("cidade", "frente", "equipe", "setor"),
    "faturamento": ("cidade",),
    "vendas": ("cidade", "frente", "equipe"),
    "implantacao": ("cidade", "frente", "equipe"),
    "faturamento_implantacao": ("frente",),
    "programacao": ("cidade", "regiao", "projeto", "equipe"),
}


def _sem_cache(nome: str) -> pd.DataFrame:
    with engine.connect() as conexao:
        dados = pd.read_sql(_CONSTRUTORES[nome](), conexao)
    if "data" in dados.columns and not dados.empty:
        dados["data"] = pd.to_datetime(dados["data"]).dt.date
        dados["ano"] = dados["data"].map(lambda d: d.year)
        dados["mes"] = dados["data"].map(lambda d: d.month)
    for coluna in ("cidade", "equipe", "frente", "regiao", "projeto", "setor"):
        if coluna in dados.columns:
            dados[coluna] = dados[coluna].fillna("Não Informado")
    return dados


def base(nome: str) -> pd.DataFrame:
    """DataFrame completo (com cache) de uma base de fatos."""
    return cache.obter(f"base:{nome}", lambda: _sem_cache(nome)).copy()


def aplicar_filtros(nome: str, dados: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    if dados.empty:
        return dados
    saida = dados
    if filtros.ano is not None:
        saida = saida[saida["ano"] == filtros.ano]
    if filtros.mes is not None:
        saida = saida[saida["mes"] == filtros.mes]
    if filtros.data_inicio is not None:
        saida = saida[saida["data"] >= filtros.data_inicio]
    if filtros.data_fim is not None:
        saida = saida[saida["data"] <= filtros.data_fim]
    for coluna in COLUNAS_FILTRAVEIS.get(nome, ()):  # dimensões
        valor = getattr(filtros, coluna, None)
        if valor and coluna in saida.columns:
            saida = saida[saida[coluna] == valor]
    return saida


def dados(nome: str, filtros: Filtros | None = None) -> pd.DataFrame:
    """Base filtrada — ponto de entrada usado por todos os módulos."""
    bruto = base(nome)
    return bruto if filtros is None else aplicar_filtros(nome, bruto, filtros)


def periodo_disponivel() -> tuple[date | None, date | None]:
    """Menor e maior data presentes em qualquer base de fatos."""
    def calcular() -> tuple[date | None, date | None]:
        datas: list[date] = []
        for nome in _CONSTRUTORES:
            df = base(nome)
            if not df.empty:
                datas.extend([df["data"].min(), df["data"].max()])
        return (min(datas), max(datas)) if datas else (None, None)

    return cache.obter("periodo_disponivel", calcular)


def valores_dimensao(coluna: str) -> list[str]:
    """Opções de filtro presentes nos dados (sem inventar valores)."""
    def calcular() -> list[str]:
        valores: set[str] = set()
        for nome in _CONSTRUTORES:
            df = base(nome)
            if coluna in df.columns and not df.empty:
                valores.update(v for v in df[coluna].dropna().unique() if v != "Não Informado")
        return sorted(valores)

    return cache.obter(f"dim:{coluna}", calcular)


def anos_disponiveis() -> list[int]:
    def calcular() -> list[int]:
        anos: set[int] = set()
        for nome in _CONSTRUTORES:
            df = base(nome)
            if not df.empty:
                anos.update(int(a) for a in df["ano"].unique())
        return sorted(anos, reverse=True)

    return cache.obter("anos", calcular)


def metas_df() -> pd.DataFrame:
    def calcular() -> pd.DataFrame:
        cidade, equipe = aliased(DimCidade), aliased(DimEquipe)
        stmt = (
            select(
                Meta.ano, Meta.mes, Meta.modulo, Meta.segmento, Meta.valor_meta,
                cidade.nome.label("cidade"), equipe.nome.label("equipe"),
            )
            .join(cidade, Meta.cidade_id == cidade.id, isouter=True)
            .join(equipe, Meta.equipe_id == equipe.id, isouter=True)
        )
        with engine.connect() as conexao:
            return pd.read_sql(stmt, conexao)

    return cache.obter("metas", calcular).copy()


def historico_uploads(limite: int = 50) -> pd.DataFrame:
    stmt = (select(HistoricoUpload).order_by(HistoricoUpload.data_hora.desc()).limit(limite))
    with engine.connect() as conexao:
        return pd.read_sql(stmt, conexao)


def ultima_atualizacao() -> pd.Timestamp | None:
    stmt = select(func.max(HistoricoUpload.data_hora)).where(HistoricoUpload.status != "ERRO")
    with engine.connect() as conexao:
        valor = conexao.execute(stmt).scalar()
    return pd.to_datetime(valor) if valor else None


def ha_dados() -> bool:
    return any(not base(nome).empty for nome in _CONSTRUTORES)
