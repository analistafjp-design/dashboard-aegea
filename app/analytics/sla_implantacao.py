"""Análise de SLA para implantações com acompanhamento de atrasos e prazos."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from app.analytics import consultas, nucleo
from app.analytics.base import Filtros
from app.analytics.periodo import Periodo, resolver
from app.utils.log import get_logger

logger = get_logger("sla_implantacao")

# Status que não devem ser acompanhados em SLA
STATUS_IGNORADOS = {"FINALIZADA", "ENCERRADA COM OCORRENCIA", "CANCELADA", "CANCELADO"}


def _eh_aberta(status: str) -> bool:
    """Verifica se a implantação está aberta (não finalizada/cancelada)."""
    if pd.isna(status):
        return True  # Se não tem status, considera aberta
    return str(status).strip().upper() not in STATUS_IGNORADOS


def _data_referencia(periodo: Periodo) -> datetime:
    """Retorna a data de referência para análise de SLA.

    Para o período atual (hoje), usa a data/hora real.
    Para períodos históricos, usa o final do mês de referência (23:59:59).
    """
    agora = datetime.now()
    hoje = agora.date()

    if periodo.mes == hoje.month and periodo.ano == hoje.year:
        return agora  # Data real agora

    # Para períodos históricos, usa o final do mês
    if periodo.mes == 12:
        proximo = pd.Timestamp(periodo.ano + 1, 1, 1)
    else:
        proximo = pd.Timestamp(periodo.ano, periodo.mes + 1, 1)
    ultimo_dia = (proximo - pd.Timedelta(days=1)).to_pydatetime()
    return ultimo_dia.replace(hour=23, minute=59, second=59)


def _classificar_sla(inicio: datetime | None, fim: datetime | None,
                     referencia: datetime) -> str | None:
    """Classifica o status do SLA: VENCIDO, PROXIMO ou NORMAL."""
    if pd.isna(inicio) or pd.isna(fim):
        return None

    if not isinstance(inicio, datetime):
        return None
    if not isinstance(fim, datetime):
        return None

    # Vencida: fim < referencia
    if fim < referencia:
        return "VENCIDO"

    # A vencer: dentro de 48h OU consumiu 80% do intervalo
    tempo_restante = fim - referencia
    intervalo_total = fim - inicio

    # Condição 1: faltam no máximo 48 horas
    if tempo_restante <= timedelta(hours=48):
        return "PROXIMO"

    # Condição 2: pelo menos 80% consumido
    if intervalo_total.total_seconds() > 0:
        consumido = (referencia - inicio).total_seconds() / intervalo_total.total_seconds()
        if consumido >= 0.8:
            return "PROXIMO"

    return "NORMAL"


def _calcular_percentual_consumido(inicio: datetime | None, fim: datetime | None,
                                    referencia: datetime) -> float | None:
    """Calcula o percentual do intervalo SLA já consumido."""
    if pd.isna(inicio) or pd.isna(fim):
        return None

    if not isinstance(inicio, datetime) or not isinstance(fim, datetime):
        return None

    intervalo_total = (fim - inicio).total_seconds()
    if intervalo_total <= 0:
        return None

    consumido = (referencia - inicio).total_seconds()
    percentual = (consumido / intervalo_total) * 100
    return max(0, min(100, percentual))  # Clamp entre 0 e 100


def _calcular_tempo_restante(inicio: datetime | None, fim: datetime | None,
                               referencia: datetime) -> timedelta | None:
    """Retorna o tempo restante (negativo se vencido)."""
    if pd.isna(inicio) or pd.isna(fim):
        return None

    if not isinstance(fim, datetime):
        return None

    return fim - referencia


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    """Calcula SLA para implantações abertas."""
    periodo = periodo or resolver(filtros)
    referencia = _data_referencia(periodo)

    # Buscar todas as implantações (incluindo as não finalizadas)
    todos_dados = consultas.dados("implantacao",
                                   Filtros(**{**filtros.__dict__, "ano": None, "mes": None}))

    # Filtrar apenas as abertas (de qualquer período, não apenas o selecionado)
    if todos_dados.empty:
        return {
            "vencidas": 0, "a_vencer": 0, "total": 0,
            "cidades": 0, "equipes": 0, "janela_horas": 48,
            "cidade_mais_critica": None,
            "por_cidade": [], "detalhes": [],
        }

    # Adicionar colunas de SLA
    todos_dados["eh_aberta"] = todos_dados["status_atividade"].apply(_eh_aberta)
    todos_dados["sla_status"] = todos_dados.apply(
        lambda r: _classificar_sla(r.get("inicio_sla"), r.get("fim_sla"), referencia),
        axis=1
    )
    todos_dados["percentual_consumido"] = todos_dados.apply(
        lambda r: _calcular_percentual_consumido(r.get("inicio_sla"), r.get("fim_sla"), referencia),
        axis=1
    )
    todos_dados["tempo_restante"] = todos_dados.apply(
        lambda r: _calcular_tempo_restante(r.get("inicio_sla"), r.get("fim_sla"), referencia),
        axis=1
    )

    # Apenas as abertas
    abertos = todos_dados[todos_dados["eh_aberta"]].copy()

    if abertos.empty:
        return {
            "vencidas": 0, "a_vencer": 0, "total": 0,
            "cidades": 0, "equipes": 0, "janela_horas": 48,
            "cidade_mais_critica": None,
            "por_cidade": [], "detalhes": [],
        }

    # Separar por status
    vencidas = abertos[abertos["sla_status"] == "VENCIDO"]
    proximas = abertos[abertos["sla_status"] == "PROXIMO"]

    qtd_vencidas = len(vencidas)
    qtd_proximas = len(proximas)
    qtd_total = len(abertos)
    cidades_afetadas = set()
    equipes_afetadas = set()

    for status_grupo in [vencidas, proximas]:
        for _, row in status_grupo.iterrows():
            if pd.notna(row.get("cidade")):
                cidades_afetadas.add(row["cidade"])
            if pd.notna(row.get("equipe")):
                equipes_afetadas.add(row["equipe"])

    # Ranking por cidade
    por_cidade = []
    if not abertos.empty and "cidade" in abertos.columns:
        ranking = abertos.groupby("cidade").agg({
            "sla_status": lambda x: (
                (x == "VENCIDO").sum(),
                (x == "PROXIMO").sum(),
                len(x)
            )
        }).reset_index()
        ranking.columns = ["cidade", "stats"]
        ranking[["vencidas", "proximas", "total"]] = pd.DataFrame(
            ranking["stats"].tolist(), index=ranking.index
        )
        ranking = ranking[["cidade", "vencidas", "proximas", "total"]].copy()
        ranking = ranking.sort_values("vencidas", ascending=False).head(10)
        por_cidade = ranking.to_dict("records")

    # Determinar cidade mais crítica
    cidade_mais_critica = None
    if por_cidade:
        cidade_mais_critica = por_cidade[0]["cidade"]

    # Detalhes: ordenar vencidas primeiro, depois próximas
    detalhes = []
    for df_grupo in [vencidas, proximas]:
        if df_grupo.empty:
            continue

        df_sorted = df_grupo.sort_values(
            "tempo_restante",
            ascending=True,  # Menores primeiros (mais urgentes)
            na_position="last"
        ).head(50)  # Máximo 50 por grupo

        for _, row in df_sorted.iterrows():
            detalhes.append({
                "situacao": row.get("sla_status", "NORMAL"),
                "matricula": row.get("matricula"),
                "cidade": row.get("cidade"),
                "frente": row.get("frente"),
                "equipe": row.get("equipe"),
                "status_atividade": row.get("status_atividade"),
                "inicio_sla": row.get("inicio_sla"),
                "fim_sla": row.get("fim_sla"),
                "tempo_restante_horas": (
                    row.get("tempo_restante").total_seconds() / 3600
                    if pd.notna(row.get("tempo_restante")) else None
                ),
                "percentual_consumido": row.get("percentual_consumido"),
            })

    return {
        "vencidas": qtd_vencidas,
        "a_vencer": qtd_proximas,
        "total": qtd_total,
        "cidades": len(cidades_afetadas),
        "equipes": len(equipes_afetadas),
        "janela_horas": 48,
        "cidade_mais_critica": cidade_mais_critica,
        "por_cidade": por_cidade,
        "detalhes": detalhes,
    }
