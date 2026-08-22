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

    def add(categoria: str, titulo: str, descricao: str, origem: str) -> None:
        alertas.append({
            "categoria": categoria, "icone": ICONES[categoria], "cor": CORES[categoria],
            "titulo": titulo, "descricao": descricao, "origem": origem,
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
            add(CRITICO, f"{rotulo}: meta em risco", descricao, chave)
        elif categoria == ATENCAO:
            add(ATENCAO, f"{rotulo}: atenção ao ritmo", descricao, chave)
        else:
            add(NORMAL, f"{rotulo}: dentro do esperado", descricao, chave)

    # Faturamento pendente
    faturamento_impl = (payloads.get("implantacao") or {}).get("faturamento") or {}
    pendentes = faturamento_impl.get("quantidade_nao_faturada")
    if pendentes:
        percentual_pendente = faturamento_impl.get("percentual_nao_faturado")
        categoria = CRITICO if (percentual_pendente or 0) >= 30 else ATENCAO
        add(categoria, "Faturamento pendente",
            f"{numero(pendentes)} implantação(ões) realizada(s) sem faturamento "
            f"({percentual(percentual_pendente)} do total do mês).", "implantacao")

    # Queda de vendas
    venda_principal = next((i for i in (payloads.get("vendas") or {}).get("indicadores", [])
                            if i["chave"] == "total_venda"), None)
    if venda_principal and venda_principal.get("variacao") is not None:
        if venda_principal["variacao"] <= -10:
            add(CRITICO, "Queda de vendas",
                f"Venda {percentual(abs(venda_principal['variacao']))} menor que no mês anterior.",
                "vendas")
        elif venda_principal["variacao"] <= -5:
            add(ATENCAO, "Vendas em queda",
                f"Venda {percentual(abs(venda_principal['variacao']))} menor que no mês anterior.",
                "vendas")

    # Equipes sem produção
    tabela_equipes = (payloads.get("equipes") or {}).get("tabela") or []
    sem_producao = [linha["equipe"] for linha in tabela_equipes
                    if (linha.get("realizado") or 0) <= LIMITE_EQUIPE_SEM_PRODUCAO]
    if sem_producao:
        add(ATENCAO, "Equipe sem produção",
            f"{len(sem_producao)} equipe(s) sem produção na base selecionada: "
            f"{', '.join(sem_producao[:5])}" + (" ..." if len(sem_producao) > 5 else "."),
            "equipes")

    # Concentração de programação
    for desequilibrio in (payloads.get("programacao") or {}).get("desequilibrios", []):
        if desequilibrio["tipo"] == "sobrecarregada":
            add(ATENCAO, "Excesso de programação", desequilibrio["texto"], "programacao")

    # Cidades abaixo da meta
    abaixo = (payloads.get("cidades") or {}).get("abaixo_da_meta") or []
    criticas = [c for c in abaixo if (c["atingimento"] or 100) < LIMITE_CRITICO]
    if criticas:
        add(CRITICO, "Cidades abaixo da meta",
            f"{len(criticas)} cidade(s) com atingimento abaixo de {int(LIMITE_CRITICO)}%: "
            + ", ".join(f"{c['cidade']} ({percentual(c['atingimento'])})" for c in criticas[:5]),
            "cidades")

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
