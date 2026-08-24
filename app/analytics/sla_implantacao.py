"""Alertas de SLA para Implantações — vencidas e próximo vencimento.

Monitora o cumprimento do prazo de execução das implantações usando as
colunas Início da SLA e Fim da SLA. Classifica em: CRITICO (vencida),
ATENCAO (dentro de 24h), NORMAL (dentro do prazo).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from app.analytics import consultas
from app.analytics.base import Filtros
from app.analytics.periodo import Periodo, resolver
from app.utils.formato import numero


def _status_sla(data_fim_sla: object) -> str | None:
    """Classifica o status da SLA comparando com hoje.

    Retorna: VENCIDO, PROXIMO_VENCIMENTO ou None (se sem data).
    """
    if data_fim_sla is None:
        return None
    try:
        # Converter para data se for string
        if isinstance(data_fim_sla, str):
            data_fim = datetime.fromisoformat(data_fim_sla).date()
        else:
            data_fim = data_fim_sla

        hoje = datetime.now().date()
        dias_restantes = (data_fim - hoje).days

        if dias_restantes < 0:
            return "VENCIDO"
        elif dias_restantes <= 1:  # próximo vencimento é até amanhã
            return "PROXIMO_VENCIMENTO"
        else:
            return None
    except (ValueError, TypeError, AttributeError):
        return None


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    """Calcula alertas de SLA para implantações do período selecionado."""
    periodo = periodo or resolver(filtros)
    dados = consultas.dados("implantacao", filtros)
    do_mes = dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados

    # Filtrar registros com SLA definida
    com_sla = do_mes[do_mes["data_fim_sla"].notna()] if not do_mes.empty else do_mes

    # Classificar por status de SLA
    vencidas = []
    proximo_vencimento = []

    if not com_sla.empty:
        for _, linha in com_sla.iterrows():
            status = _status_sla(linha.get("data_fim_sla"))
            registro = {
                "matricula": linha.get("matricula"),
                "cidade": linha.get("cidade"),
                "equipe": linha.get("equipe"),
                "frente": linha.get("frente"),
                "servico": linha.get("servico"),
                "data_inicio_sla": linha.get("data_inicio_sla"),
                "data_fim_sla": linha.get("data_fim_sla"),
                "faturado": linha.get("faturado", False),
            }

            if status == "VENCIDO":
                vencidas.append(registro)
            elif status == "PROXIMO_VENCIMENTO":
                proximo_vencimento.append(registro)

    # Ranking por cidade para SLA vencidas
    ranking_vencidas_por_cidade = _ranking_sla_por_cidade(vencidas)

    # Ranking por cidade para próximo vencimento
    ranking_proximo_por_cidade = _ranking_sla_por_cidade(proximo_vencimento)

    return {
        "modulo": "SLA_IMPLANTACAO",
        "titulo": "SLA de Implantação",
        "periodo": periodo.to_dict(),
        "tem_dados": not com_sla.empty,
        "resumo": {
            "total_com_sla": len(com_sla) if not com_sla.empty else 0,
            "total_vencidas": len(vencidas),
            "total_proximo_vencimento": len(proximo_vencimento),
        },
        "vencidas": vencidas[:20],  # Top 20
        "proximo_vencimento": proximo_vencimento[:20],  # Top 20
        "ranking_vencidas_por_cidade": ranking_vencidas_por_cidade,
        "ranking_proximo_por_cidade": ranking_proximo_por_cidade,
    }


def _ranking_sla_por_cidade(registros: list[dict]) -> list[dict]:
    """Consolida registros de SLA por cidade para ranking.

    Retorna lista de dicts com: cidade, total, faturadas, nao_faturadas
    """
    por_cidade: dict[str, dict] = {}

    for reg in registros:
        cidade = reg.get("cidade", "Não Informado")
        if cidade not in por_cidade:
            por_cidade[cidade] = {
                "cidade": cidade,
                "total": 0,
                "faturadas": 0,
                "nao_faturadas": 0,
            }
        por_cidade[cidade]["total"] += 1
        if reg.get("faturado"):
            por_cidade[cidade]["faturadas"] += 1
        else:
            por_cidade[cidade]["nao_faturadas"] += 1

    # Ordenar por total decrescente
    ranking = sorted(por_cidade.values(), key=lambda x: x["total"], reverse=True)
    return ranking[:10]  # Top 10 cidades
