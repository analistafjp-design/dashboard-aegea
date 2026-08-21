"""Insights executivos calculados a partir dos dados reais.

Cada frase nasce de um número existente na base. Quando o dado necessário
não existe, o insight simplesmente não é gerado — nada é inventado.
"""
from __future__ import annotations

from app.utils.formato import numero, percentual

LIMITE_VARIACAO_RELEVANTE = 5.0


def _pct(valor: float | None) -> str:
    return percentual(abs(valor)) if valor is not None else ""


def gerar(payloads: dict) -> list[dict]:
    insights: list[dict] = []
    termos = payloads.get("termos") or {}
    faturamento = payloads.get("faturamento") or {}
    vendas = payloads.get("vendas") or {}
    implantacao = payloads.get("implantacao") or {}
    programacao = payloads.get("programacao") or {}
    equipes = payloads.get("equipes") or {}
    cidades = payloads.get("cidades") or {}

    def add(texto: str, tipo: str = "info", origem: str = "") -> None:
        insights.append({"texto": texto, "tipo": tipo, "origem": origem})

    # 1. Distância da meta por módulo
    for chave, rotulo, payload in (
        ("implantacao", "A implantação", implantacao),
        ("vendas", "A venda", vendas),
        ("termos", "Os termos aplicados", termos),
    ):
        bloco = payload.get("bloco_principal") or {}
        atingimento = bloco.get("atingimento")
        if atingimento is None:
            continue
        diferenca = round(atingimento - 100, 1)
        if diferenca < 0:
            add(f"{rotulo} está {_pct(diferenca)} abaixo da meta no período "
                f"({percentual(atingimento)} de atingimento).", "alerta", chave)
        else:
            add(f"{rotulo} já superou a meta em {_pct(diferenca)} "
                f"({percentual(atingimento)} de atingimento).", "positivo", chave)

    # 2. Variação contra o mês anterior, por frente/indicador principal
    for chave, payload in (("vendas", vendas), ("implantacao", implantacao),
                           ("termos", termos)):
        principal = next((i for i in payload.get("indicadores", []) if i.get("variacao")), None)
        if principal and abs(principal["variacao"]) >= LIMITE_VARIACAO_RELEVANTE:
            direcao = "crescimento" if principal["variacao"] > 0 else "queda"
            add(f"{principal['titulo']} apresenta {direcao} de "
                f"{_pct(principal['variacao'])} em relação ao mês anterior.",
                "positivo" if principal["variacao"] > 0 else "alerta", chave)

    # 3. Implantações sem faturamento
    alerta_fat = (implantacao.get("faturamento") or {}).get("alerta")
    if alerta_fat:
        add(alerta_fat, "alerta", "implantacao")
        pendentes = implantacao.get("nao_faturadas_por_cidade") or []
        if pendentes:
            topo = pendentes[0]
            add(f"A cidade {topo['cidade']} concentra a maior quantidade de implantações "
                f"pendentes de faturamento ({numero(topo['total'])}).", "alerta", "implantacao")

    # 4. Melhor equipe
    ranking_equipes = equipes.get("ranking") or []
    if ranking_equipes:
        topo = ranking_equipes[0]
        add(f"A equipe {topo['equipe']} apresenta a maior produção do período "
            f"({numero(topo['total'])} registros, {percentual(topo['participacao'])} do total).",
            "positivo", "equipes")

    # 5. Cidades abaixo da meta
    abaixo = cidades.get("abaixo_da_meta") or []
    if abaixo:
        pior = abaixo[0]
        add(f"A cidade {pior['cidade']} está com o menor atingimento do período "
            f"({percentual(pior['atingimento'])}).", "alerta", "cidades")

    # 6. Conversão de faturamento de termos
    conversao = next((i for i in faturamento.get("indicadores", [])
                      if i["chave"] == "conversao" and i["valor"] is not None), None)
    if conversao:
        add(f"A conversão de termo para faturamento está em "
            f"{percentual(conversao['valor'])} no período.",
            "positivo" if conversao["valor"] >= 70 else "info", "faturamento")

    # 7. Carga operacional
    desequilibrios = programacao.get("desequilibrios") or []
    if desequilibrios:
        sobrecarregadas = [d for d in desequilibrios if d["tipo"] == "sobrecarregada"]
        if sobrecarregadas:
            add(f"{len(sobrecarregadas)} equipe(s) com carga acima do normal na programação de "
                f"{programacao.get('data_referencia_br', 'referência')}: "
                f"{', '.join(d['equipe'] for d in sobrecarregadas[:3])}.", "alerta", "programacao")

    # 8. Projeção de fechamento
    bloco = implantacao.get("bloco_principal") or {}
    if bloco.get("projecao") is not None and bloco.get("meta") is not None:
        diferenca = bloco["diferenca_projetada"]
        if diferenca is not None and diferenca < 0:
            add(f"No ritmo atual a implantação fecha o mês em {numero(bloco['projecao'])}, "
                f"{numero(abs(diferenca))} abaixo da meta de {numero(bloco['meta'])}.",
                "alerta", "implantacao")
        elif diferenca is not None:
            add(f"No ritmo atual a implantação fecha o mês em {numero(bloco['projecao'])}, "
                f"{numero(diferenca)} acima da meta.", "positivo", "implantacao")

    return insights
