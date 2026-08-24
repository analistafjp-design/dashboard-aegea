"""Alertas gerenciais: CRÍTICO, ATENÇÃO e NORMAL."""
from __future__ import annotations

from app.analytics.base import AMARELO, VERDE, VERMELHO
from app.utils.formato import numero, percentual

CRITICO = "CRITICO"
ATENCAO = "ATENCAO"
NORMAL = "NORMAL"

CORES = {CRITICO: VERMELHO, ATENCAO: AMARELO, NORMAL: VERDE}
ICONES = {CRITICO: "🔴", ATENCAO: "🟡", NORMAL: "🟢"}

LIMITE_CRITICO = 80.0     # atingimento do ritmo abaixo disso = crítico
LIMITE_ATENCAO = 95.0
LIMITE_EQUIPE_SEM_PRODUCAO = 0


def _classificar(ritmo: float | None) -> str | None:
    if ritmo is None:
        return None
    if ritmo < LIMITE_CRITICO:
        return CRITICO
    if ritmo < LIMITE_ATENCAO:
        return ATENCAO
    return NORMAL


def gerar(payloads: dict) -> list[dict]:
    alertas: list[dict] = []

    def add(categoria: str, titulo: str, descricao: str, origem: str,
            acao: str, prazo: str, indicador: str = "") -> None:
        alertas.append({
            "categoria": categoria, "icone": ICONES[categoria], "cor": CORES[categoria],
            "titulo": titulo, "descricao": descricao, "origem": origem,
            "acao": acao, "prazo": prazo, "indicador": indicador,
        })

    # Metas em risco (usa o ritmo: realizado vs. meta acumulada até hoje)
    for chave, rotulo in (("termos", "Termos Aplicados"), ("vendas", "Venda"),
                          ("implantacao", "Implantação")):
        bloco = (payloads.get(chave) or {}).get("bloco_principal") or {}
        categoria = _classificar(bloco.get("atingimento_ritmo"))
        if categoria is None:
            continue
        descricao = (
            f"Realizado {numero(bloco.get('realizado'))} de {numero(bloco.get('meta'))} "
            f"({percentual(bloco.get('atingimento'))}). "
            f"Ritmo necessário: {numero(bloco.get('necessario_por_dia'), 1)}/dia nos "
            f"{bloco.get('dias_uteis_restantes')} dia(s) útil(eis) restante(s)."
        )
        if categoria == CRITICO:
            add(CRITICO, f"{rotulo}: meta em risco", descricao, chave,
                "Repriorizar as equipes e acompanhar o realizado diariamente até o ritmo "
                "voltar ao necessário.", "Hoje",
                f"Necessário: {numero(bloco.get('necessario_por_dia'), 1)}/dia")
        elif categoria == ATENCAO:
            add(ATENCAO, f"{rotulo}: atenção ao ritmo", descricao, chave,
                "Revisar a distribuição da produção e corrigir os desvios antes do próximo "
                "fechamento semanal.", "Esta semana",
                f"Projeção: {numero(bloco.get('projecao'))}")
        else:
            add(NORMAL, f"{rotulo}: dentro do esperado", descricao, chave,
                "Manter o ritmo e verificar diariamente se a projeção continua acima da meta.",
                "Monitorar", f"Atingimento: {percentual(bloco.get('atingimento'))}")

    # Faturamento pendente
    faturamento_impl = (payloads.get("implantacao") or {}).get("faturamento") or {}
    pendentes = faturamento_impl.get("quantidade_nao_faturada")
    if pendentes:
        percentual_pendente = faturamento_impl.get("percentual_nao_faturado")
        categoria = CRITICO if (percentual_pendente or 0) >= 30 else ATENCAO
        add(categoria, "Faturamento pendente",
            f"{numero(pendentes)} implantação(ões) realizada(s) sem faturamento "
            f"({percentual(percentual_pendente)} do total do mês).", "implantacao",
            "Extrair a relação válida, priorizar a cidade com maior pendência e conciliar "
            "execução, ligação e valor faturado.", "Hoje" if categoria == CRITICO else "Esta semana",
            f"Pendentes: {numero(pendentes)}")

    # Queda de vendas
    venda_principal = next((i for i in (payloads.get("vendas") or {}).get("indicadores", [])
                            if i["chave"] == "total_venda"), None)
    if venda_principal and venda_principal.get("variacao") is not None:
        if venda_principal["variacao"] <= -10:
            add(CRITICO, "Queda de vendas",
                f"Venda {percentual(abs(venda_principal['variacao']))} menor que no mês anterior.",
                "vendas", "Identificar as cidades e equipes que mais perderam volume e direcionar "
                "a prospecção para os alvos com maior potencial.", "Hoje",
                f"Queda: {percentual(abs(venda_principal['variacao']))}")
        elif venda_principal["variacao"] <= -5:
            add(ATENCAO, "Vendas em queda",
                f"Venda {percentual(abs(venda_principal['variacao']))} menor que no mês anterior.",
                "vendas", "Revisar a produção por cidade e equipe e definir uma recuperação para "
                "os próximos dias úteis.", "Esta semana",
                f"Queda: {percentual(abs(venda_principal['variacao']))}")

    # Equipes sem produção
    tabela_equipes = (payloads.get("equipes") or {}).get("tabela") or []
    sem_producao = [linha["equipe"] for linha in tabela_equipes
                    if (linha.get("realizado") or 0) <= LIMITE_EQUIPE_SEM_PRODUCAO]
    if sem_producao:
        add(ATENCAO, "Equipe sem produção",
            f"{len(sem_producao)} equipe(s) sem produção na base selecionada: "
            f"{', '.join(sem_producao[:5])}" + (" ..." if len(sem_producao) > 5 else "."),
            "equipes", "Confirmar disponibilidade e redistribuir carteira ou rota para as equipes "
            "sem apontamento.", "Hoje", f"Equipes: {len(sem_producao)}")

    # Cidades abaixo da meta
    abaixo = (payloads.get("cidades") or {}).get("abaixo_da_meta") or []
    criticas = [c for c in abaixo if (c["atingimento"] or 100) < LIMITE_CRITICO]
    if criticas:
        add(CRITICO, "Cidades abaixo da meta",
            f"{len(criticas)} cidade(s) com atingimento abaixo de {int(LIMITE_CRITICO)}%: "
            + ", ".join(f"{c['cidade']} ({percentual(c['atingimento'])})" for c in criticas[:5]),
            "cidades", "Priorizar as cidades listadas na distribuição de equipes, bases e ações "
            "de campo da próxima rota.", "Hoje", f"Cidades críticas: {len(criticas)}")

    # Concentração geográfica de Termos — útil para avaliar dependência de uma cidade.
    ranking_termos = (payloads.get("termos") or {}).get("por_cidade") or []
    if ranking_termos and (ranking_termos[0].get("participacao") or 0) >= 35:
        topo = ranking_termos[0]
        add(ATENCAO, "Concentração geográfica de Termos",
            f"{topo['cidade']} concentra {percentual(topo['participacao'])} do realizado "
            f"({numero(topo['total'])} termos).", "termos",
            "Preservar o desempenho da cidade líder e definir uma ação para ampliar a produção "
            "nas cidades seguintes do ranking.", "Esta semana",
            f"Concentração: {percentual(topo['participacao'])}")

    # Dependência excessiva de uma única equipe.
    ranking_equipes = (payloads.get("equipes") or {}).get("ranking") or []
    if ranking_equipes and (ranking_equipes[0].get("participacao") or 0) >= 25:
        topo = ranking_equipes[0]
        add(ATENCAO, "Produção concentrada em uma equipe",
            f"{topo['equipe']} responde por {percentual(topo['participacao'])} da produção "
            f"selecionada ({numero(topo['total'])} registros).", "equipes",
            "Verificar capacidade, cobertura e substituição para reduzir o risco operacional "
            "de dependência de uma única equipe.", "Esta semana",
            f"Participação: {percentual(topo['participacao'])}")

    # Implantações com SLA vencido
    sla_impl = (payloads.get("implantacao") or {}).get("sla") or {}
    vencidas = sla_impl.get("vencidas", 0)
    if vencidas > 0:
        cidade_critica = sla_impl.get("cidade_mais_critica")
        msg_cidade = f" Maior concentração: {cidade_critica}." if cidade_critica else "."
        add(CRITICO, "Implantações com SLA vencido",
            f"{numero(vencidas)} implantação(ões) ultrapassaram o prazo de execução{msg_cidade}",
            "implantacao",
            "Priorizar as ordens vencidas, confirmar impedimentos com as equipes e registrar "
            "a nova previsão de execução.", "Hoje",
            f"Vencidas: {numero(vencidas)}")
    # Implantações próximas do vencimento (só mostrar se não há vencidas)
    elif vencidas == 0:
        proximas = sla_impl.get("a_vencer", 0)
        if proximas > 0:
            add(ATENCAO, "Implantações próximas do fim da SLA",
                f"{numero(proximas)} implantação(ões) estão a até 48 horas do vencimento ou "
                f"consumiram 80% do prazo.",
                "implantacao",
                "Validar a programação das equipes e antecipar as ordens com menor tempo restante.",
                "Hoje",
                f"A vencer: {numero(proximas)}")

    ordem = {CRITICO: 0, ATENCAO: 1, NORMAL: 2}
    alertas.sort(key=lambda a: ordem[a["categoria"]])
    return alertas


def resumo(alertas: list[dict]) -> dict:
    return {
        "criticos": sum(1 for a in alertas if a["categoria"] == CRITICO),
        "atencao": sum(1 for a in alertas if a["categoria"] == ATENCAO),
        "normais": sum(1 for a in alertas if a["categoria"] == NORMAL),
        "total": len(alertas),
    }
