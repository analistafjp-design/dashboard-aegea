"""Cálculos compartilhados por todos os módulos.

Documentação de cada regra:

* Realizado       = soma da coluna de medida no período filtrado.
* Meta            = valor oficial cadastrado (nunca estimado).
* Falta           = max(Meta - Realizado, 0).
* % Atingimento   = Realizado / Meta * 100.
* Média por dia   = Realizado / dias úteis decorridos.
* Meta acumulada  = Meta * (dias úteis decorridos / dias úteis totais).
* Projeção        = Realizado + Média por dia útil * dias úteis restantes.
"""
from __future__ import annotations

import pandas as pd

from app.analytics.base import (
    AZUL,
    CINZA,
    Indicador,
    calcular_atingimento,
    calcular_falta,
    status_por_atingimento,
    variacao_percentual,
)
from app.analytics.calendario import ABREV_MES, data_no_enesimo_dia_util
from app.analytics.metas import MENSAGEM_SEM_META, meta_acumulada
from app.analytics.periodo import Periodo


def total(dados: pd.DataFrame, coluna: str = "quantidade") -> float | None:
    """Soma da medida. `None` (sem dados) é diferente de 0 (houve zero)."""
    if dados is None or dados.empty or coluna not in dados.columns:
        return None
    serie = pd.to_numeric(dados[coluna], errors="coerce").dropna()
    if serie.empty:
        return None
    return float(serie.sum())


def contar(dados: pd.DataFrame) -> float | None:
    return None if dados is None or dados.empty else float(len(dados))


def distintos(dados: pd.DataFrame, coluna: str) -> float | None:
    if dados is None or dados.empty or coluna not in dados.columns:
        return None
    return float(dados[coluna].replace("Não Informado", pd.NA).dropna().nunique())


def media_diaria(realizado: float | None, dias_uteis: int) -> float | None:
    if realizado is None or dias_uteis <= 0:
        return None
    return round(realizado / dias_uteis, 2)


def projecao(realizado: float | None, periodo: Periodo) -> float | None:
    """Realizado + ritmo atual aplicado aos dias úteis restantes.

    O ritmo é usado sem arredondamento intermediário: arredondar a média
    diária antes de multiplicar distorce a projeção do mês.
    """
    if realizado is None or periodo.dias_uteis_decorridos <= 0:
        return None
    ritmo = realizado / periodo.dias_uteis_decorridos
    return round(realizado + ritmo * periodo.dias_uteis_restantes, 2)


def bloco_meta(realizado: float | None, valor_meta: float | None, periodo: Periodo,
               rotulo: str = "Total") -> dict:
    """META / REALIZADO / FALTA / ATINGIMENTO + projeção, em um só lugar."""
    atingimento = calcular_atingimento(realizado, valor_meta)
    acumulada = meta_acumulada(valor_meta, periodo.fracao_decorrida)
    projetado = projecao(realizado, periodo)
    atingimento_projetado = calcular_atingimento(projetado, valor_meta)
    ritmo = calcular_atingimento(realizado, acumulada)  # está no ritmo necessário?

    return {
        "rotulo": rotulo,
        "meta": valor_meta,
        "meta_cadastrada": valor_meta is not None,
        "meta_acumulada": acumulada,
        "realizado": realizado,
        "falta": calcular_falta(realizado, valor_meta),
        "atingimento": atingimento,
        "atingimento_ritmo": ritmo,
        "media_dia": media_diaria(realizado, periodo.dias_uteis_decorridos),
        "necessario_por_dia": (
            None if valor_meta is None or realizado is None or periodo.dias_uteis_restantes <= 0
            else round(max(valor_meta - realizado, 0) / periodo.dias_uteis_restantes, 2)
        ),
        "projecao": projetado,
        "atingimento_projetado": atingimento_projetado,
        "diferenca_projetada": (
            None if projetado is None or valor_meta is None else round(projetado - valor_meta, 2)
        ),
        "status": status_por_atingimento(ritmo if ritmo is not None else atingimento),
        "status_projecao": status_por_atingimento(atingimento_projetado),
        "dias_uteis_restantes": periodo.dias_uteis_restantes,
        "dias_uteis_decorridos": periodo.dias_uteis_decorridos,
        "mensagem_meta": None if valor_meta is not None else MENSAGEM_SEM_META,
    }


def indicador_realizado(chave: str, titulo: str, realizado: float | None,
                        valor_meta: float | None = None, anterior: float | None = None,
                        formato: str = "numero", casas: int = 0,
                        pergunta: str = "", explicacao: str = "") -> Indicador:
    atingimento = calcular_atingimento(realizado, valor_meta)
    return Indicador(
        chave=chave, titulo=titulo, valor=realizado, formato=formato, casas=casas,
        disponivel=realizado is not None,
        mensagem=None if realizado is not None else "Sem dados",
        anterior=anterior, variacao=variacao_percentual(realizado, anterior),
        meta=valor_meta,
        status=(CINZA if realizado is None else
                (status_por_atingimento(atingimento) if valor_meta is not None else AZUL)),
        pergunta=pergunta, explicacao=explicacao,
    )


def evolucao_mensal(dados: pd.DataFrame, coluna: str = "quantidade") -> pd.DataFrame:
    """Total por mês, ordenado, com rótulo curto (ago/2026)."""
    if dados is None or dados.empty:
        return pd.DataFrame(columns=["ano_mes", "rotulo", "total"])
    agrupado = (dados.groupby("ano_mes", as_index=False)[coluna].sum()
                .rename(columns={coluna: "total"}).sort_values("ano_mes"))
    agrupado["rotulo"] = agrupado["ano_mes"].map(
        lambda am: f"{ABREV_MES[int(am[5:7]) - 1]}/{am[:4]}")
    return agrupado.reset_index(drop=True)


def evolucao_diaria(dados: pd.DataFrame, coluna: str = "quantidade") -> pd.DataFrame:
    """Total por dia + acumulado no período."""
    if dados is None or dados.empty:
        return pd.DataFrame(columns=["data", "total", "acumulado"])
    agrupado = (dados.groupby("data", as_index=False)[coluna].sum()
                .rename(columns={coluna: "total"}).sort_values("data"))
    agrupado["acumulado"] = agrupado["total"].cumsum()
    return agrupado.reset_index(drop=True)


def ranking(dados: pd.DataFrame, dimensao: str, coluna: str = "quantidade",
            top: int | None = None, crescente: bool = False) -> pd.DataFrame:
    if dados is None or dados.empty or dimensao not in dados.columns:
        return pd.DataFrame(columns=[dimensao, "total", "participacao"])
    agrupado = (dados.groupby(dimensao, as_index=False)[coluna].sum()
                .rename(columns={coluna: "total"})
                .sort_values("total", ascending=crescente))
    soma = agrupado["total"].sum()
    agrupado["participacao"] = (agrupado["total"] / soma * 100).round(1) if soma else 0.0
    return (agrupado.head(top) if top else agrupado).reset_index(drop=True)


def comparar_meses(dados_completos: pd.DataFrame, periodo: Periodo,
                   coluna: str = "quantidade") -> tuple[float | None, float | None]:
    """(realizado do mês, realizado do mês anterior no MESMO estágio do mês).

    Um mês em andamento nunca é comparado com um mês fechado: o mês
    anterior é cortado no mesmo número de dias úteis decorridos, senão a
    variação apareceria sempre negativa no meio do mês.
    """
    if dados_completos is None or dados_completos.empty:
        return None, None
    anterior = periodo.anterior()
    atual_df = dados_completos[dados_completos["ano_mes"] == periodo.ano_mes]
    anterior_df = dados_completos[dados_completos["ano_mes"] == anterior.ano_mes]

    if periodo.dias_uteis_decorridos < periodo.dias_uteis_totais and not anterior_df.empty:
        corte = data_no_enesimo_dia_util(anterior.inicio, periodo.dias_uteis_decorridos)
        anterior_df = anterior_df[anterior_df["data"] <= corte]

    return total(atual_df, coluna), total(anterior_df, coluna)


def matriz_meta(linhas: list[dict]) -> list[dict]:
    """Tabela META x REALIZADO x FALTA (visual mais importante da implantação)."""
    saida = []
    for linha in linhas:
        saida.append({
            "rotulo": linha["rotulo"],
            "meta": linha.get("meta"),
            "realizado": linha.get("realizado"),
            "falta": linha.get("falta"),
            "atingimento": linha.get("atingimento"),
            "status": linha.get("status", CINZA),
            "mensagem_meta": linha.get("mensagem_meta"),
        })
    return saida
