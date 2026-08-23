"""MÓDULO 2 — Implantação (PBIX 2).

Equivalências: Medidas.Total Implantação, Implantação Geral,
Implantação por Mês - Serviços, Média Implantação Dia - Serviços,
Implantação Mês - VCG, Implantação Dia VCG, Implantação Faturada,
Implantação Não Faturada, Valor Total Faturado, Falta Total.
"""
from __future__ import annotations

from app.analytics import consultas, metas, nucleo
from app.analytics.base import AZUL, CINZA, VERMELHO, Filtros, Indicador
from app.analytics.dominio_tipos import TIPO_SERVICOS, TIPO_VCG
from app.analytics.periodo import Periodo, resolver


DEPARTAMENTOS_FATURAMENTO = {
    "IMPLANTAÇÃO DE LIGAÇÃO ÁGUA",
    "VEM COM A GENTE",
}


def _tipo(dados, tipo: str):
    return dados[dados["tipo"] == tipo] if "tipo" in dados.columns else dados.iloc[0:0]


def _linha_faturamento(rotulo: str, implantacoes, faturadas, nao_faturadas,
                       valor: float | None) -> dict:
    """Resume uma frente usando as mesmas contagens das medidas do PBIX."""
    implantacao = nucleo.total(implantacoes)
    faturada = (nucleo.total(faturadas) if "ligacao" not in faturadas.columns
                else float(faturadas["ligacao"].nunique()))
    nao_faturada = (nucleo.total(nao_faturadas)
                    if "ligacao" not in nao_faturadas.columns
                    else float(nao_faturadas["ligacao"].nunique()))
    return {
        "frente": rotulo,
        "implantacao": implantacao,
        "faturada": 0.0 if faturada is None and implantacao is not None else faturada,
        "nao_faturada": 0.0 if nao_faturada is None and implantacao is not None else nao_faturada,
        "valor_faturado": valor,
    }


def calcular(filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    todos = consultas.dados("implantacao",
                            Filtros(**{**filtros.__dict__, "ano": None, "mes": None}))
    dados = consultas.dados("implantacao", filtros)
    do_mes = dados[dados["ano_mes"] == periodo.ano_mes] if not dados.empty else dados
    faturamento_base = consultas.dados("faturamento_implantacao", filtros)
    faturamento_mes = (
        faturamento_base[faturamento_base["ano_mes"] == periodo.ano_mes]
        if not faturamento_base.empty else faturamento_base
    )

    total_impl = nucleo.total(do_mes)
    servicos = nucleo.total(_tipo(do_mes, TIPO_SERVICOS))
    vcg = nucleo.total(_tipo(do_mes, TIPO_VCG))

    meta_total = metas.meta_total_composta("IMPLANTACAO", periodo.ano, periodo.mes, filtros)
    meta_servicos = metas.meta("IMPLANTACAO", periodo.ano, periodo.mes, "SERVICOS", filtros)
    meta_vcg = metas.meta("IMPLANTACAO", periodo.ano, periodo.mes, "VCG", filtros)

    if not faturamento_mes.empty:
        ocorrencia = faturamento_mes["ocorrencia"].str.strip().str.upper() == "0-EXECUTADO"
        departamento = faturamento_mes["departamento"].str.strip().str.upper().isin(
            DEPARTAMENTOS_FATURAMENTO
        )
        ligacao = faturamento_mes["tipo_solicitacao"].str.upper().str.contains(
            "IMPLANTAÇÃO DE LIGAÇÃO", regex=False, na=False
        )
        elegiveis = faturamento_mes[ocorrencia & departamento & ligacao]
        faturadas_df = elegiveis[elegiveis["valor"].fillna(0) > 0]
        nao_faturadas_df = elegiveis[elegiveis["valor"].fillna(0) == 0]
        # As medidas DAX usam DISTINCTCOUNT de Nº Ligação.
        qtd_faturada = float(faturadas_df["ligacao"].nunique())
        qtd_nao_faturada = float(nao_faturadas_df["ligacao"].nunique())
        valor_faturado = nucleo.total(
            faturamento_mes[ocorrencia & departamento], "valor"
        )
        faturamento_por_frente = []
        for rotulo, tipo in (("Serviços", TIPO_SERVICOS), ("VCG", TIPO_VCG)):
            mascara_frente = faturamento_mes["frente"].str.strip().str.upper() == rotulo.upper()
            faturadas_frente = faturadas_df[
                faturadas_df["frente"].str.strip().str.upper() == rotulo.upper()
            ]
            nao_faturadas_frente = nao_faturadas_df[
                nao_faturadas_df["frente"].str.strip().str.upper() == rotulo.upper()
            ]
            valor_frente = nucleo.total(
                faturamento_mes[ocorrencia & departamento & mascara_frente], "valor"
            )
            faturamento_por_frente.append(_linha_faturamento(
                rotulo, _tipo(do_mes, tipo), faturadas_frente,
                nao_faturadas_frente, valor_frente,
            ))
    else:
        # Compatibilidade com planilhas consolidadas antigas.
        faturadas_df = do_mes[do_mes["faturado"] == True] if not do_mes.empty else do_mes  # noqa: E712
        nao_faturadas_df = do_mes[do_mes["faturado"] == False] if not do_mes.empty else do_mes  # noqa: E712
        qtd_faturada = nucleo.total(faturadas_df)
        qtd_nao_faturada = nucleo.total(nao_faturadas_df)
        valor_faturado = nucleo.total(faturadas_df, "valor")
        faturamento_por_frente = []
        for rotulo, tipo in (("Serviços", TIPO_SERVICOS), ("VCG", TIPO_VCG)):
            implantacoes_frente = _tipo(do_mes, tipo)
            faturamento_por_frente.append(_linha_faturamento(
                rotulo,
                implantacoes_frente,
                implantacoes_frente[implantacoes_frente["faturado"] == True],  # noqa: E712
                implantacoes_frente[implantacoes_frente["faturado"] == False],  # noqa: E712
                nucleo.total(
                    implantacoes_frente[implantacoes_frente["faturado"] == True], "valor"  # noqa: E712
                ),
            ))

    pct_faturado = (round(qtd_faturada / total_impl * 100, 1)
                    if qtd_faturada is not None and total_impl else None)
    pct_nao_faturado = None if pct_faturado is None else round(100 - pct_faturado, 1)

    _, anterior = nucleo.comparar_meses(todos, periodo)

    bloco_total = nucleo.bloco_meta(total_impl, meta_total, periodo, "Total")
    blocos = [
        nucleo.bloco_meta(servicos, meta_servicos, periodo, "Serviços"),
        nucleo.bloco_meta(vcg, meta_vcg, periodo, "VCG"),
        bloco_total,
    ]

    alerta_faturamento = None
    if qtd_nao_faturada:
        alerta_faturamento = (
            f"Existem {int(qtd_nao_faturada)} implantação(ões) realizada(s) ainda não "
            f"faturada(s) em {periodo.rotulo}."
        )

    indicadores = [
        nucleo.indicador_realizado(
            "total_implantacao", "Implantação Total", total_impl, meta_total, anterior,
            pergunta="Como está a implantação no mês?",
            explicacao="Soma das implantações do mês de referência."),
        nucleo.indicador_realizado(
            "impl_servicos", "Implantação Serviços", servicos, meta_servicos,
            pergunta="Como está Serviços?", explicacao="Implantações classificadas como Serviços."),
        nucleo.indicador_realizado(
            "impl_vcg", "Implantação VCG", vcg, meta_vcg,
            pergunta="Como está VCG?", explicacao="Implantações classificadas como VCG."),
        nucleo.indicador_realizado(
            "impl_faturada", "Implantação Faturada", qtd_faturada,
            pergunta="Quanto já foi faturado?",
            explicacao="Implantações marcadas como faturadas na base."),
        Indicador(
            chave="impl_nao_faturada", titulo="Implantação Não Faturada",
            valor=qtd_nao_faturada, disponivel=qtd_nao_faturada is not None,
            mensagem=None if qtd_nao_faturada is not None else "Sem dados",
            status=(CINZA if qtd_nao_faturada is None else
                    (VERMELHO if qtd_nao_faturada > 0 else AZUL)),
            pergunta="Qual receita está represada?",
            explicacao="Implantações realizadas que ainda não têm faturamento."),
        Indicador(
            chave="valor_faturado", titulo="Valor Total Faturado", valor=valor_faturado,
            formato="moeda", disponivel=valor_faturado is not None,
            mensagem=None if valor_faturado is not None else "Valor não informado na base",
            status=AZUL if valor_faturado is not None else CINZA,
            pergunta="Quanto entrou de receita?",
            explicacao="Soma do valor das implantações faturadas."),
        nucleo.indicador_realizado(
            "media_dia", "Média Implantação/Dia", bloco_total["media_dia"], casas=1,
            pergunta="Qual o ritmo diário?",
            explicacao="Implantação total dividida pelos dias úteis decorridos."),
        nucleo.indicador_realizado(
            "falta_total", "Falta Total", bloco_total["falta"],
            pergunta="Quanto falta para a meta?",
            explicacao="Meta menos realizado."),
    ]

    return {
        "modulo": "IMPLANTACAO",
        "titulo": "Implantação",
        "periodo": periodo.to_dict(),
        "tem_dados": not do_mes.empty,
        "indicadores": [i.to_dict() for i in indicadores],
        "blocos_meta": nucleo.matriz_meta(blocos),
        "bloco_principal": bloco_total,
        "faturamento": {
            "quantidade_faturada": qtd_faturada,
            "quantidade_nao_faturada": qtd_nao_faturada,
            "valor_faturado": valor_faturado,
            "percentual_faturado": pct_faturado,
            "percentual_nao_faturado": pct_nao_faturado,
            "alerta": alerta_faturamento,
            "por_frente": faturamento_por_frente,
        },
        "evolucao_mensal": nucleo.evolucao_mensal(dados).to_dict("records"),
        "evolucao_servicos": nucleo.evolucao_mensal(_tipo(dados, TIPO_SERVICOS)).to_dict("records"),
        "evolucao_vcg": nucleo.evolucao_mensal(_tipo(dados, TIPO_VCG)).to_dict("records"),
        "evolucao_diaria": nucleo.evolucao_diaria(do_mes).to_dict("records"),
        "por_cidade": nucleo.ranking(do_mes, "cidade", top=15).to_dict("records"),
        "por_frente": nucleo.ranking(do_mes, "frente").to_dict("records"),
        "por_equipe": nucleo.ranking(do_mes, "equipe", top=15).to_dict("records"),
        "nao_faturadas_por_cidade": (
            nucleo.ranking(nao_faturadas_df, "cidade", top=10).to_dict("records")
            if "cidade" in nao_faturadas_df.columns else []
        ),
    }
