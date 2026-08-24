"""Análise de SLA para implantações com acompanhamento de atrasos e prazos."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.analytics import consultas
from app.analytics.base import Filtros
from app.analytics.periodo import Periodo, resolver
from app.utils.log import get_logger

logger = get_logger("sla_implantacao")

# Status que não devem ser acompanhados em SLA
STATUS_IGNORADOS = {"FINALIZADA", "ENCERRADA COM OCORRENCIA", "CANCELADA", "CANCELADO"}

# Uma ordem entra em "a vencer" quando falta esta janela para o prazo ou
# quando já consumiu esta fração do intervalo contratado.
JANELA_DIAS = 3
JANELA_HORAS = JANELA_DIAS * 24
LIMITE_CONSUMIDO = 0.8

VAZIO = {
    "vencidas": 0, "a_vencer": 0, "total": 0, "com_prazo": 0,
    "cidades": 0, "equipes": 0,
    "janela_horas": JANELA_HORAS, "janela_dias": JANELA_DIAS,
    "cidade_mais_critica": None,
    "por_cidade": [], "detalhes": [],
}


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


def _derivar(dados: pd.DataFrame, referencia: datetime) -> pd.DataFrame:
    """Colunas de SLA para a base inteira, de uma vez.

    Uma ordem só entra na análise quando tem os dois marcos de prazo. Sem
    `inicio_sla` ou sem `fim_sla` não há intervalo para medir, e chutar um
    deles inventaria atraso onde a planilha não afirma nada.
    """
    saida = pd.DataFrame(index=dados.index)
    ref = pd.Timestamp(referencia)

    inicio = pd.to_datetime(dados.get("inicio_sla"), errors="coerce")
    fim = pd.to_datetime(dados.get("fim_sla"), errors="coerce")
    tem_prazo = inicio.notna() & fim.notna()

    intervalo = (fim - inicio).dt.total_seconds()
    restante = (fim - ref).dt.total_seconds()
    consumido = ((ref - inicio).dt.total_seconds() / intervalo).where(intervalo > 0)

    vencido = tem_prazo & (fim < ref)
    proximo = tem_prazo & ~vencido & (
        (restante <= JANELA_HORAS * 3600) | (consumido >= LIMITE_CONSUMIDO)
    )

    saida["sla_status"] = None
    saida.loc[tem_prazo, "sla_status"] = "NORMAL"
    saida.loc[proximo, "sla_status"] = "PROXIMO"
    saida.loc[vencido, "sla_status"] = "VENCIDO"

    saida["inicio_sla"] = inicio
    saida["fim_sla"] = fim
    saida["horas_restantes"] = (restante / 3600).where(tem_prazo)
    saida["percentual_consumido"] = (consumido * 100).clip(0, 100).where(tem_prazo)
    return saida


def _iso(valor: object) -> str | None:
    """Data em texto ISO — NaT vira None em vez de quebrar o JSON."""
    return None if pd.isna(valor) else pd.Timestamp(valor).isoformat()


def _numero(valor: object) -> float | None:
    return None if pd.isna(valor) else float(valor)


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    """Situação de SLA das implantações ainda em aberto.

    O prazo não respeita a virada do mês: uma ordem aberta em julho continua
    vencendo em agosto. Por isso o recorte de ano/mês do painel é ignorado
    aqui — só as dimensões (cidade, frente, equipe) filtram.
    """
    periodo = periodo or resolver(filtros)
    referencia = _data_referencia(periodo)

    dados = consultas.dados("implantacao",
                            Filtros(**{**filtros.__dict__, "ano": None, "mes": None}))
    if dados.empty or "fim_sla" not in dados.columns:
        return dict(VAZIO)

    dados = dados.join(_derivar(dados, referencia), rsuffix="_sla_calc")
    abertos = (dados[dados["status_atividade"].map(_eh_aberta)]
               if "status_atividade" in dados.columns else dados)

    vencidas = abertos[abertos["sla_status"] == "VENCIDO"]
    proximas = abertos[abertos["sla_status"] == "PROXIMO"]
    # Quantas ordens abertas têm prazo preenchido. Sem isso não dá para
    # separar "está tudo no prazo" de "a planilha não trouxe as datas".
    com_prazo = int(abertos["sla_status"].notna().sum())

    criticas = pd.concat([vencidas, proximas]) if len(vencidas) or len(proximas) else vencidas
    if criticas.empty:
        return dict(VAZIO) | {"total": len(abertos), "com_prazo": com_prazo}

    # O ranking mostra só quem tem algo a tratar: uma cidade com 40 ordens
    # todas dentro do prazo não é notícia num painel de atraso.
    por_cidade = []
    if "cidade" in criticas.columns:
        ranking = (
            criticas.assign(
                _vencida=(criticas["sla_status"] == "VENCIDO").astype(int),
                _proxima=(criticas["sla_status"] == "PROXIMO").astype(int),
            )
            .groupby("cidade", as_index=False)
            .agg(vencidas=("_vencida", "sum"), proximas=("_proxima", "sum"))
        )
        ranking["total"] = ranking["vencidas"] + ranking["proximas"]
        ranking = ranking.sort_values(
            ["vencidas", "proximas", "cidade"], ascending=[False, False, True]
        ).head(10)
        por_cidade = ranking.to_dict("records")

    detalhes = []
    for grupo in (vencidas, proximas):
        if grupo.empty:
            continue
        # Mais urgente primeiro: o mais atrasado no topo das vencidas, o de
        # prazo mais curto no topo das próximas.
        ordenado = grupo.sort_values("horas_restantes", na_position="last").head(50)
        for _, linha in ordenado.iterrows():
            detalhes.append({
                "situacao": linha["sla_status"],
                "matricula": linha.get("matricula"),
                "cidade": linha.get("cidade"),
                "frente": linha.get("frente"),
                "equipe": linha.get("equipe"),
                "status_atividade": linha.get("status_atividade"),
                "inicio_sla": _iso(linha.get("inicio_sla")),
                "fim_sla": _iso(linha.get("fim_sla")),
                "tempo_restante_horas": _numero(linha.get("horas_restantes")),
                "percentual_consumido": _numero(linha.get("percentual_consumido")),
            })

    return {
        "vencidas": len(vencidas),
        "a_vencer": len(proximas),
        "total": len(abertos),
        "com_prazo": com_prazo,
        "cidades": int(criticas["cidade"].nunique()) if "cidade" in criticas.columns else 0,
        "equipes": int(criticas["equipe"].nunique()) if "equipe" in criticas.columns else 0,
        "janela_horas": JANELA_HORAS,
        "janela_dias": JANELA_DIAS,
        "cidade_mais_critica": por_cidade[0]["cidade"] if por_cidade else None,
        "por_cidade": por_cidade,
        "detalhes": detalhes,
    }
