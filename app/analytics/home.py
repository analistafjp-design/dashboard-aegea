"""HOME EXECUTIVA — apenas o que o gestor precisa para decidir.

Regra do consolidado: "Total Realizado" é a SOMA dos realizados dos três
módulos (Termos + Venda + Implantação) e "Meta Consolidada" é a soma das
metas cadastradas desses mesmos módulos. A regra é explícita justamente
para não misturar registros sem critério — o detalhe de cada módulo
continua separado nas páginas específicas.
"""
from __future__ import annotations

from app.analytics import alertas as mod_alertas
from app.analytics import consultas, insights as mod_insights, nucleo
from app.analytics.base import (
    AZUL,
    CINZA,
    Filtros,
    Indicador,
    calcular_atingimento,
    calcular_falta,
    status_por_atingimento,
    variacao_percentual,
)
from app.analytics.dominio_tipos import SIT_FATURADO
from app.analytics.periodo import Periodo, resolver


def _soma(valores: list[float | None]) -> float | None:
    validos = [v for v in valores if v is not None]
    return float(sum(validos)) if validos else None


def montar(payloads: dict, filtros: Filtros, periodo: Periodo | None = None) -> dict:
    periodo = periodo or resolver(filtros)
    termos = payloads.get("termos") or {}
    faturamento = payloads.get("faturamento") or {}
    vendas = payloads.get("vendas") or {}
    implantacao = payloads.get("implantacao") or {}
    programacao = payloads.get("programacao") or {}
    equipes = payloads.get("equipes") or {}

    blocos = [p.get("bloco_principal") or {} for p in (termos, vendas, implantacao)]
    realizado_total = _soma([b.get("realizado") for b in blocos])
    meta_total = _soma([b.get("meta") for b in blocos])
    atingimento = calcular_atingimento(realizado_total, meta_total)
    falta = calcular_falta(realizado_total, meta_total)
    projecao_total = _soma([b.get("projecao") for b in blocos])

    anteriores = {
        "termos": _anterior(termos), "vendas": _anterior(vendas),
        "implantacao": _anterior(implantacao),
    }
    anterior_total = _soma(list(anteriores.values()))

    def valor(payload: dict, chave: str):
        item = next((i for i in payload.get("indicadores", []) if i["chave"] == chave), None)
        return (item or {}).get("valor")

    def anterior_de(payload: dict, chave: str):
        item = next((i for i in payload.get("indicadores", []) if i["chave"] == chave), None)
        return (item or {}).get("anterior")

    equipes_ativas = _equipes_ativas(filtros, periodo)

    cards = [
        Indicador(
            chave="realizado_total", titulo="Total Realizado", valor=realizado_total,
            disponivel=realizado_total is not None,
            mensagem=None if realizado_total is not None else "Sem dados no período",
            anterior=anterior_total, variacao=variacao_percentual(realizado_total, anterior_total),
            meta=meta_total, status=status_por_atingimento(atingimento) if meta_total else AZUL,
            pergunta="Como estamos?",
            explicacao="Soma de Termos + Venda + Implantação no mês de referência."),
        Indicador(
            chave="meta_total", titulo="Meta Consolidada", valor=meta_total,
            disponivel=meta_total is not None,
            mensagem=None if meta_total is not None else "Meta não cadastrada",
            status=AZUL if meta_total is not None else CINZA,
            pergunta="Qual é o compromisso do mês?",
            explicacao="Soma das metas oficiais cadastradas para os três módulos."),
        Indicador(
            chave="atingimento", titulo="% de Atingimento", valor=atingimento,
            formato="percentual", casas=1, disponivel=atingimento is not None,
            mensagem=None if atingimento is not None else "Meta não cadastrada",
            status=status_por_atingimento(atingimento),
            pergunta="Estamos atingindo a meta?",
            explicacao="Total realizado dividido pela meta consolidada."),
        Indicador(
            chave="falta", titulo="Falta para a Meta", valor=falta,
            disponivel=falta is not None,
            mensagem=None if falta is not None else "Meta não cadastrada",
            status=status_por_atingimento(atingimento),
            pergunta="Quanto falta?",
            explicacao="Meta consolidada menos o total realizado."),
        _card(vendas, "total_venda", "Venda", "Qual o resultado comercial?"),
        _card(implantacao, "total_implantacao", "Implantação", "Quanto foi implantado?"),
        _card(termos, "realizado_total", "Termos Aplicados", "Quantos termos foram aplicados?",
              chave_saida="termos_aplicados"),
        _card(faturamento, "qtd_faturado", "Termos Faturados", "Quanto virou faturamento?"),
        _card(faturamento, "valor_faturado", "Valor Faturado", "Qual o valor faturado?"),
        _card(programacao, "os_programadas_dia", "O.S. Programadas",
              "Qual a carga operacional do dia?"),
        Indicador(
            chave="equipes_ativas", titulo="Equipes Ativas", valor=equipes_ativas,
            disponivel=equipes_ativas is not None,
            mensagem=None if equipes_ativas is not None else "Sem dados",
            status=AZUL if equipes_ativas is not None else CINZA,
            pergunta="Qual a força de trabalho no mês?",
            explicacao="Equipes distintas com produção registrada em qualquer módulo."),
        Indicador(
            chave="dias_restantes", titulo="Dias Úteis Restantes",
            valor=float(periodo.dias_uteis_restantes), status=AZUL,
            pergunta="Quanto tempo resta?",
            explicacao=f"Dias úteis entre a referência e {periodo.fim.strftime('%d/%m/%Y')}."),
    ]

    lista_alertas = mod_alertas.gerar(payloads)
    return {
        "titulo": "Visão Executiva",
        "periodo": periodo.to_dict(),
        "tem_dados": consultas.ha_dados(),
        "cards": [c.to_dict() for c in cards],
        "consolidado": {
            "meta": meta_total, "realizado": realizado_total, "falta": falta,
            "atingimento": atingimento, "projecao": projecao_total,
            "diferenca_projetada": (None if projecao_total is None or meta_total is None
                                    else round(projecao_total - meta_total, 2)),
            "status": status_por_atingimento(atingimento),
            "status_projecao": status_por_atingimento(
                calcular_atingimento(projecao_total, meta_total)),
            "dias_uteis_restantes": periodo.dias_uteis_restantes,
            "mensagem_meta": None if meta_total is not None else "Meta não cadastrada",
        },
        "modulos": [
            _resumo_modulo("Termos", termos), _resumo_modulo("Venda", vendas),
            _resumo_modulo("Implantação", implantacao),
        ],
        "evolucao": {
            "termos": termos.get("evolucao_mensal", []),
            "vendas": vendas.get("evolucao_mensal", []),
            "implantacao": implantacao.get("evolucao_mensal", []),
        },
        "insights": mod_insights.gerar(payloads),
        "alertas": lista_alertas[:6],
        "resumo_alertas": mod_alertas.resumo(lista_alertas),
        "top_cidades": (payloads.get("cidades") or {}).get("maior_implantacao", [])[:5],
        "top_equipes": (equipes.get("ranking") or [])[:5],
    }


def _card(payload: dict, chave: str, titulo: str, pergunta: str,
          chave_saida: str | None = None) -> Indicador:
    origem = next((i for i in payload.get("indicadores", []) if i["chave"] == chave), None)
    if origem is None:
        return Indicador(chave=chave_saida or chave, titulo=titulo, valor=None,
                         disponivel=False, mensagem="Sem dados", status=CINZA,
                         pergunta=pergunta)
    return Indicador(
        chave=chave_saida or chave, titulo=titulo, valor=origem["valor"],
        formato=origem["formato"], casas=origem["casas"],
        disponivel=origem["disponivel"], mensagem=origem["mensagem"],
        anterior=origem["anterior"], variacao=origem["variacao"], meta=origem["meta"],
        status=origem["status"], pergunta=pergunta, explicacao=origem["explicacao"],
    )


def _anterior(payload: dict) -> float | None:
    for indicador in payload.get("indicadores", []):
        if indicador.get("anterior") is not None:
            return indicador["anterior"]
    return None


def _resumo_modulo(rotulo: str, payload: dict) -> dict:
    bloco = payload.get("bloco_principal") or {}
    return {
        "rotulo": rotulo,
        "realizado": bloco.get("realizado"),
        "meta": bloco.get("meta"),
        "falta": bloco.get("falta"),
        "atingimento": bloco.get("atingimento"),
        "projecao": bloco.get("projecao"),
        "status": bloco.get("status", CINZA),
        "mensagem_meta": bloco.get("mensagem_meta"),
        "tem_dados": payload.get("tem_dados", False),
    }


def _equipes_ativas(filtros: Filtros, periodo: Periodo) -> float | None:
    equipes: set[str] = set()
    encontrou = False
    for nome in ("termos", "vendas", "implantacao", "programacao"):
        dados = consultas.dados(nome, filtros)
        if dados.empty or "equipe" not in dados.columns:
            continue
        do_mes = dados[dados["ano_mes"] == periodo.ano_mes]
        if do_mes.empty:
            continue
        encontrou = True
        equipes.update(e for e in do_mes["equipe"].dropna().unique() if e != "Não Informado")
    return float(len(equipes)) if encontrou else None


def termos_faturados_valor(filtros: Filtros, periodo: Periodo) -> float | None:
    dados = consultas.dados("faturamento", filtros)
    if dados.empty:
        return None
    recorte = dados[(dados["ano_mes"] == periodo.ano_mes) & (dados["situacao"] == SIT_FATURADO)]
    return nucleo.total(recorte, "valor")
