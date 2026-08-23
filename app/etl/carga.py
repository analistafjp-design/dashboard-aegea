"""Carga incremental no banco.

Estratégia: chave única por dataset (definida em `datasets.py`). Registro
existente é atualizado, registro novo é inserido — reprocessar o mesmo
arquivo não duplica nada.

Performance: a carga usa INSERT/UPDATE em massa via SQLAlchemy Core
("ORM bulk INSERT/UPDATE"), não um objeto por linha com `session.add()`.
Um arquivo de ~60 mil linhas levava ~21s (a maior parte no
unit-of-work do ORM processando um INSERT por vez); em massa cai para
poucos segundos — importante porque o upload é uma requisição HTTP
síncrona e um arquivo grande travando por minutos deixava a tela de
Atualização de Dados parecendo travada, sem nenhum retorno ao usuário.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.analytics.calendario import gerar_calendario
from app.etl.datasets import Dataset
from app.models.tabelas import (
    DIMENSOES_NOMEADAS,
    FatoFaturamento,
    FatoFaturamentoImplantacao,
    FatoImplantacao,
    FatoProgramacao,
    FatoTermos,
    FatoVendas,
    Meta,
)
from app.utils.log import get_logger
from app.utils.texto import slug

logger = get_logger("etl.carga")


@dataclass
class ResultadoCarga:
    inseridos: int = 0
    atualizados: int = 0
    ignorados: int = 0

    @property
    def total(self) -> int:
        return self.inseridos + self.atualizados


class ResolvedorDimensoes:
    """Cache de dimensões: cria o rótulo se ainda não existir."""

    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao
        self._cache: dict[tuple[str, str], int] = {}

    def id_de(self, dimensao: str, valor: object) -> int | None:
        if valor is None or str(valor).strip() == "":
            return None
        modelo = DIMENSOES_NOMEADAS[dimensao]
        chave = slug(valor)
        if not chave:
            return None
        memo = (dimensao, chave)
        if memo in self._cache:
            return self._cache[memo]

        registro = self.sessao.execute(
            select(modelo).where(modelo.chave == chave)
        ).scalar_one_or_none()
        if registro is None:
            registro = modelo(nome=str(valor).strip(), chave=chave)
            self.sessao.add(registro)
            self.sessao.flush()
        self._cache[memo] = registro.id
        return registro.id


def _valor(linha: dict, campo: str, padrao=None):
    valor = linha.get(campo, padrao)
    if valor is None:
        return padrao
    if isinstance(valor, float) and pd.isna(valor):
        return padrao
    return valor


def _montar_fato(dataset: Dataset, linha: dict, dim: ResolvedorDimensoes,
                 arquivo: str) -> dict:
    """Monta os campos de UM fato como dicionário simples (não um objeto
    ORM) — usado tanto para INSERT quanto para UPDATE em massa."""
    comum = {
        "chave_unica": linha["chave_unica"],
        "data": linha["data"],
        "ano_mes": linha["ano_mes"],
        "origem_arquivo": arquivo,
        "importado_em": datetime.now(),
    }

    if dataset.nome == "termos":
        return {
            **comum,
            "cidade_id": dim.id_de("cidade", _valor(linha, "cidade")),
            "equipe_id": dim.id_de("equipe", _valor(linha, "equipe")),
            "frente_id": dim.id_de("frente", _valor(linha, "frente")),
            "setor_id": dim.id_de("setor", _valor(linha, "setor")),
            "matricula": _valor(linha, "matricula"),
            "tipo": _valor(linha, "tipo", "NAO_CLASSIFICADO"),
            "status_termo": _valor(linha, "status_termo", "Não Informado"),
            "quantidade": float(_valor(linha, "quantidade", 1.0)),
            "valor": _valor(linha, "valor"),
        }
    if dataset.nome == "faturamento":
        return {
            **comum,
            "inicio_mes": linha["inicio_mes"],
            "cidade_id": dim.id_de("cidade", _valor(linha, "cidade")),
            "situacao": _valor(linha, "situacao", "Outras"),
            "situacao_termo": _valor(linha, "situacao"),
            "numero_termo": _valor(linha, "numero_termo"),
            "quantidade": float(_valor(linha, "quantidade", 1.0)),
            "valor": _valor(linha, "valor"),
        }
    if dataset.nome == "vendas":
        return {
            **comum,
            "cidade_id": dim.id_de("cidade", _valor(linha, "cidade")),
            "equipe_id": dim.id_de("equipe", _valor(linha, "equipe")),
            "frente_id": dim.id_de("frente", _valor(linha, "frente")),
            "canal": _valor(linha, "canal", "OUTROS"),
            "matricula": _valor(linha, "matricula"),
            "quantidade": float(_valor(linha, "quantidade", 1.0)),
            "valor": _valor(linha, "valor"),
        }
    if dataset.nome == "implantacao":
        return {
            **comum,
            "cidade_id": dim.id_de("cidade", _valor(linha, "cidade")),
            "equipe_id": dim.id_de("equipe", _valor(linha, "equipe")),
            "frente_id": dim.id_de("frente", _valor(linha, "frente")),
            "tipo": _valor(linha, "tipo", "NAO_CLASSIFICADO"),
            "matricula": _valor(linha, "matricula"),
            "servico": _valor(linha, "servico"),
            "faturado": bool(_valor(linha, "faturado", False)),
            "quantidade": float(_valor(linha, "quantidade", 1.0)),
            "valor": _valor(linha, "valor"),
        }
    if dataset.nome == "atendimento":
        # Grava como venda por Outros Canais (ver regras_atendimento).
        return {
            **comum,
            "cidade_id": dim.id_de("cidade", _valor(linha, "cidade")),
            "equipe_id": dim.id_de("equipe", _valor(linha, "equipe")),
            "frente_id": dim.id_de("frente", _valor(linha, "frente")),
            "canal": _valor(linha, "canal", "OUTROS"),
            "matricula": _valor(linha, "matricula"),
            "quantidade": float(_valor(linha, "quantidade", 1.0)),
            "valor": _valor(linha, "valor"),
        }
    if dataset.nome == "faturamento_implantacao":
        return {
            **comum,
            "ligacao": _valor(linha, "ligacao"),
            "tipo_solicitacao": _valor(linha, "tipo_solicitacao", ""),
            "ocorrencia": _valor(linha, "ocorrencia", ""),
            "departamento": _valor(linha, "departamento", ""),
            "frente": _valor(linha, "frente", "Outros"),
            "valor": _valor(linha, "valor"),
            "faturado": bool(_valor(linha, "faturado", False)),
        }
    if dataset.nome == "programacao":
        recurso = _valor(linha, "recurso")
        return {
            **comum,
            "regiao_id": dim.id_de("regiao", _valor(linha, "regiao")),
            "equipe_id": dim.id_de("equipe", recurso),
            "projeto_id": dim.id_de("projeto", _valor(linha, "projeto")),
            "cidade_id": dim.id_de("cidade", _valor(linha, "cidade")),
            "recurso": recurso,
            "qtd_os": float(_valor(linha, "qtd_os", 1.0)),
        }
    raise KeyError(f"Dataset sem regra de carga: {dataset.nome}")


def _carregar_metas(sessao: Session, dados: pd.DataFrame, dim: ResolvedorDimensoes,
                    arquivo: str) -> ResultadoCarga:
    resultado = ResultadoCarga()
    for linha in dados.to_dict("records"):
        cidade_id = dim.id_de("cidade", _valor(linha, "cidade"))
        equipe_id = dim.id_de("equipe", _valor(linha, "equipe"))
        existente = sessao.execute(
            select(Meta).where(
                Meta.ano == int(linha["ano"]),
                Meta.mes == int(linha["mes"]),
                Meta.modulo == linha["modulo"],
                Meta.segmento == linha["segmento"],
                Meta.cidade_id.is_(cidade_id) if cidade_id is None else Meta.cidade_id == cidade_id,
                Meta.equipe_id.is_(equipe_id) if equipe_id is None else Meta.equipe_id == equipe_id,
            )
        ).scalar_one_or_none()

        if existente is None:
            sessao.add(Meta(
                ano=int(linha["ano"]), mes=int(linha["mes"]), modulo=linha["modulo"],
                segmento=linha["segmento"], cidade_id=cidade_id, equipe_id=equipe_id,
                valor_meta=float(linha["valor_meta"]), origem_arquivo=arquivo,
            ))
            resultado.inseridos += 1
        else:
            existente.valor_meta = float(linha["valor_meta"])
            existente.origem_arquivo = arquivo
            existente.importado_em = datetime.now()
            resultado.atualizados += 1
    sessao.flush()
    return resultado


def carregar(sessao: Session, dataset: Dataset, dados: pd.DataFrame,
             arquivo: str) -> ResultadoCarga:
    """Grava o DataFrame padronizado, atualizando registros já existentes."""
    dim = ResolvedorDimensoes(sessao)

    if dataset.nome == "metas":
        resultado = _carregar_metas(sessao, dados, dim, arquivo)
        logger.info("Carga metas: %s inseridas, %s atualizadas",
                    resultado.inseridos, resultado.atualizados)
        return resultado

    modelo = {
        "termos": FatoTermos, "faturamento": FatoFaturamento, "vendas": FatoVendas,
        "implantacao": FatoImplantacao, "programacao": FatoProgramacao,
        "faturamento_implantacao": FatoFaturamentoImplantacao,
        # Atendimento não tem tabela própria: alimenta fato_vendas.
        "atendimento": FatoVendas,
    }[dataset.nome]

    # Só id + chave (não o objeto inteiro): mais leve e evita hidratar o
    # identity map do ORM para registros que talvez nem sejam tocados.
    chaves = dados["chave_unica"].tolist()
    existentes = dict(
        sessao.execute(
            select(modelo.chave_unica, modelo.id).where(modelo.chave_unica.in_(chaves))
        ).all()
    )

    resultado = ResultadoCarga()
    inserts: list[dict] = []
    updates: list[dict] = []
    # to_dict("records") converte o DataFrame inteiro de uma vez; iterar
    # dicionários simples depois é bem mais rápido que iterrows() linha a
    # linha (que reconstrói uma Series do pandas a cada iteração).
    for linha in dados.to_dict("records"):
        campos = _montar_fato(dataset, linha, dim, arquivo)
        id_existente = existentes.get(linha["chave_unica"])
        if id_existente is None:
            inserts.append(campos)
            resultado.inseridos += 1
        else:
            campos["id"] = id_existente
            updates.append(campos)
            resultado.atualizados += 1

    # INSERT/UPDATE em massa (um executemany cada) em vez de um objeto ORM
    # por linha — é isso que faz a diferença em arquivos com dezenas de
    # milhares de linhas (segundos em vez de dezenas de segundos/minutos).
    if inserts:
        sessao.execute(insert(modelo), inserts)
    if updates:
        sessao.execute(update(modelo), updates)
    sessao.flush()

    if "data" in dados.columns and not dados.empty:
        anos = sorted({d.year for d in dados["data"]})
        gerar_calendario(sessao, min(anos), max(anos))

    logger.info("Carga %s: %s inseridos, %s atualizados",
                dataset.nome, resultado.inseridos, resultado.atualizados)
    return resultado
