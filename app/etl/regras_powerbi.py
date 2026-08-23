"""Regras extraídas das medidas e colunas calculadas dos três PBIX.

As regras só são acionadas quando as colunas características das exportações
Field Service estão presentes. Planilhas já consolidadas continuam seguindo
o fluxo genérico.
"""
from __future__ import annotations

import unicodedata

import pandas as pd


def _texto(valor: object) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = " ".join(str(valor).split()).strip().upper()
    return "".join(c for c in unicodedata.normalize("NFKD", texto)
                   if not unicodedata.combining(c))


def frente_interior(recurso: object) -> str:
    """Equivalente a `Interior[Frente]` no PBIX Venda e Implantação."""
    valor = _texto(recurso)
    if valor.startswith("RIOVCGEXTIN"):
        return "VCG - Rio Bonito"
    if valor.startswith(("RIOVCGPOPIN", "RIOVCGVENIN")):
        return "VCG Bairro Legal - SFI"
    if valor.startswith("VCG"):
        return "VCG - IN"
    if valor.startswith(("RIORECIN", "RIORECLG", "RIOVENIN", "RIOVENLG")):
        return "Venda"
    return "Serviços"


def _equipe_vcg(recurso: object) -> bool:
    valor = _texto(recurso)
    return any(codigo in valor for codigo in ("RIOVCGPOPIN", "RIOVCGEXTIN", "RIOVCGVENIN"))


def filtrar_vendas(dados: pd.DataFrame) -> pd.DataFrame:
    if "tipo_atividade" not in dados or not dados["tipo_atividade"].notna().any():
        return dados
    saida = dados.copy()
    atividade = saida["tipo_atividade"].map(_texto)
    status = saida["status_atividade"].map(_texto)
    codigo = saida["codigo_descricao"].map(_texto)
    vcg = saida["equipe"].map(_equipe_vcg)
    base = (atividade == "VENDA POTENCIAIS/FACTIVEIS") & (status == "FINALIZADA")
    comercial_valido = ~vcg & ~codigo.str.contains("114003|118048", regex=True)
    vcg_valido = vcg & ~codigo.str.contains("114003", regex=False)
    saida = saida[base & (comercial_valido | vcg_valido)].copy()
    if saida.empty:
        return saida
    eh_vcg = saida["equipe"].map(_equipe_vcg)
    saida["frente"] = saida["equipe"].map(frente_interior)
    saida["canal"] = eh_vcg.map({True: "VCG", False: "COMERCIAL"})
    saida["quantidade"] = 1.0
    return saida


def filtrar_implantacoes(dados: pd.DataFrame) -> pd.DataFrame:
    if "tipo_atividade" not in dados or not dados["tipo_atividade"].notna().any():
        return dados
    saida = dados.copy()
    atividade = saida["tipo_atividade"].map(_texto)
    status = saida["status_atividade"].map(_texto)
    saida = saida[(atividade == "LIGACAO DE AGUA") & (status == "FINALIZADA")].copy()
    if saida.empty:
        return saida
    saida["frente"] = saida["equipe"].map(frente_interior)
    saida["tipo"] = saida["frente"].map(
        lambda valor: "VCG" if "VCG" in _texto(valor) else "SERVICOS"
    )
    saida["quantidade"] = 1.0
    return saida


def frente_termos(recurso: object) -> str:
    valor = _texto(recurso)
    if valor.startswith("RIOREC"):
        return "CADASTRO"
    if valor.startswith("RIOVEN"):
        return "VENDA"
    if valor.startswith("RIOVCGEXT"):
        return "VCG - RIO BONITO"
    if valor.startswith("RIOVCGPOP"):
        return "VCG BAIRRO LEGAL - SFI"
    if valor.startswith("RIO"):
        return "SERVIÇOS"
    return "OUTROS"


# Tabela de dimensão ``Setor do Recurso`` extraída do modelo oficial do PBIX.
# A exportação do Field Service traz em ``Setor`` apenas um identificador
# numérico; o nome exibido no Power BI vem desta relação pelo prefixo de
# ``Recurso``. Portanto, o painel também deve derivar o setor pelo recurso.
SETORES_RECURSO = {
    "RIOPCRTIN": "Pós Corte",
    "RIOCSSIN": "Fiscalização",
    "RIOLTRIN": "Leitura",
    "RIOMLTIN": "Manutenção",
    "RIOPAVIN": "Pavimentação",
    "RIOMLTTIN": "Manutenção",
    "RIOFSCIN": "Fiscalização",
    "RIOCERIN": "Corte - Religa",
    "RIORECIN": "Recadastro",
    "RIOEGCIN": "Esgoto",
    "RIOCPAIN": "Serviços",
    "RIOOPEIN": "Operação",
    "RIOPROIN": "Serviços",
    "RIOLTRLLIN": "Leitura",
    "RIOCPATIN": "Serviços",
    "RIOEGCTIN": "Esgoto",
    "RIOMNTIN": "Manutenção",
    "RIOOVAIN": "Operação",
    "RIOPAVTIN": "Pavimentação",
    "RIOSETIN": "Setorizada",
    "RIOCSSLG": "Setorizada",
    "RIOLTRLG": "Leitura",
    "RIOMLTLG": "Manutenção",
    "RIOPAVLG": "Pavimentação",
    "RIOMLTTL": "Manutenção",
    "RIOFSCLG": "Fiscalização",
    "RIOPAVTL": "Pavimentação",
    "RIOCERLG": "Corte - Religa",
    "RIORECLG": "Recadastro",
    "RIOEGCTL": "Esgoto",
    "RIOCPATL": "Operação",
    "RIOOPELG": "Operação",
    "RIOLTRLL": "Leitura",
    "RIOEGCTLG": "Esgoto",
    "RIOLTRLLG": "Leitura",
    "RIOMLTTLG": "Manutenção",
    "RIOMNTLG": "Manutenção",
    "RIOPAVTLG": "Pavimentação",
    "RIOSETLG": "Setorizada",
    "RIOCOBIN": "Cobrança",
    "RIOLTRLIN": "Leitura",
    "RIOVENIN": "Venda",
    "RIOCERB1": "Corte - Religa B1",
    "RIOPCRNT": "Recuperação de Cortados",
    "RIOFSCB1": "Fiscalização B1",
    "RIOSETB2": "Setorizada B2",
    "RIOSETLT": "Setorizada",
    "RIOSETNT": "Setorizada",
    "RIOVCGPOPIN": "Bairro Legal SFI",
    "RIOVCGEXTIN": "VCG Rio Bonito",
    "RIOVCGVARTIN": "VCG Rio Bonito",
    "RIOCOMIN": "Serviços - Comerciais",
    "RIOPCRIN": "Pós Corte",
}


def setor_do_recurso(recurso: object) -> str | None:
    """Reproduz a relação f_Fild[Recurso] -> Setor do Recurso do PBIX."""
    valor = _texto(recurso)
    if not valor:
        return None
    # Prefixos maiores primeiro evitam que códigos semelhantes se antecipem.
    return next(
        (setor for prefixo, setor in sorted(
            SETORES_RECURSO.items(), key=lambda item: len(item[0]), reverse=True
        ) if valor.startswith(prefixo)),
        None,
    )


def filtrar_termos(dados: pd.DataFrame) -> pd.DataFrame:
    if "servico_adicional" not in dados or not dados["servico_adicional"].notna().any():
        return dados
    saida = dados.copy()
    texto = saida["servico_adicional"].map(_texto)
    recurso = saida["equipe"].map(_texto)
    status = saida["status_atividade"].map(_texto)
    status_valido = status.isin({"FINALIZADA", "ENCERRADA COM OCORRENCIA"})
    servicos = (
        (
            texto.str.contains("110013", regex=False)
            | texto.str.contains("210013", regex=False)
        )
        & ~recurso.str.contains("VCG", regex=False)
        & ~texto.str.contains("RIOVCGEXTIN", regex=False)
    )
    vcg = (texto.str.contains("310013", regex=False)
           & recurso.str.contains("RIOVCGEXTIN", regex=False))
    # O PBIX também usa 310025/310031 para sinalizar não conformidade e
    # vistoria pós-varredura. Eles entram como contexto operacional com
    # quantidade zero: ficam disponíveis para a gestão, sem alterar as
    # medidas oficiais Realizado Serviços/VCG.
    sinal_operacional = (
        texto.str.contains("310025", regex=False)
        | texto.str.contains("310031", regex=False)
    ) & recurso.str.contains("RIOVCGEXTIN", regex=False)
    oficial = servicos | vcg
    saida = saida[status_valido & (oficial | sinal_operacional)].copy()
    if saida.empty:
        return saida
    texto = saida["servico_adicional"].map(_texto)
    recurso = saida["equipe"].map(_texto)
    eh_oficial = (
        (
            texto.str.contains("110013", regex=False)
            | texto.str.contains("210013", regex=False)
        )
        & ~recurso.str.contains("VCG", regex=False)
        & ~texto.str.contains("RIOVCGEXTIN", regex=False)
    ) | (
        texto.str.contains("310013", regex=False)
        & recurso.str.contains("RIOVCGEXTIN", regex=False)
    )
    eh_vcg = recurso.str.contains("RIOVCGEXTIN", regex=False)
    saida["tipo"] = eh_vcg.map({True: "VCG", False: "SERVICOS"})
    saida["frente"] = saida["equipe"].map(frente_termos)
    # Não usa a coluna numérica ``Setor`` da exportação: no Power BI o nome
    # vem da dimensão relacionada ao código do recurso.
    saida["setor"] = saida["equipe"].map(setor_do_recurso)
    # Coluna calculada `Status Termo` do PBIX: os registros oficiais aqui
    # selecionados são os termos aplicados por cidade. O status operacional
    # da atividade é apenas um filtro e não deve substituir essa classificação.
    saida["status_termo"] = "Termo aplicado oficial"
    saida.loc[texto.str.contains("310031", regex=False), "status_termo"] = \
        "Vistoria pós-varredura"
    saida.loc[texto.str.contains("310025", regex=False), "status_termo"] = \
        "Termo de não conformidade"
    saida["quantidade"] = eh_oficial.astype(float)
    return saida


EQUIPE_GERAL = {
    "RIORECLG-002": "CAMILA-001", "RIOVENLG-001": "CAMILA-001", "RIOVENIN-001": "CAMILA-001",
    "RIORECLG-010": "ADRIANA-002", "RIOVENLG-002": "ADRIANA-002", "RIOVENIN-002": "ADRIANA-002",
    "RIORECLG-019": "ERIVELTON-003", "RIOVENLG-003": "ERIVELTON-003", "RIOVENIN-003": "ERIVELTON-003",
    "RIORECLG-026": "CRISTIAN-004", "RIOVENLG-004": "CRISTIAN-004", "RIOVENIN-004": "CRISTIAN-004",
    "RIORECLG-037": "ROBERTO-005", "RIOVENLG-005": "ROBERTO-005", "RIOVENIN-005": "ROBERTO-005",
    "RIORECLG-020": "MATEUSÃO-020", "RIORECIN-020": "MATEUSÃO-020",
    "RIORECLG-003": "HEVERSON-003", "RIORECIN-003": "HEVERSON-003",
    "RIORECLG-007": "BRUNO-007", "RIORECIN-007": "BRUNO-007",
    "RIORECLG-008": "MARIANA-008", "RIORECIN-008": "MARIANA-008",
    "RIORECLG-013": "GABRIEL-013", "RIORECIN-013": "GABRIEL-013",
    "RIORECLG-004": "FERNANDA-004", "RIORECIN-004": "FERNANDA-004",
    "RIORECLG-034": "THAFNES-034", "RIORECIN-034": "THAFNES-034",
    "RIORECLG-024": "LUCIANO-024", "RIORECIN-024": "LUCIANO-024",
    **{f"RIOIEGTIN-{n:03d}": f"OBRAS ESGOTO-{n:03d}" for n in range(1, 6)},
}

REGIOES = {
    "SERRANA": {"RIORECLG-024", "RIORECIN-024", "RIOVENLG-003", "RIOVENIN-003"},
    "NOROESTE": {"RIORECLG-029", "RIORECIN-029", "RIORECLG-013", "RIORECIN-013",
                  "RIORECLG-020", "RIORECIN-020", "RIOVENLG-004", "RIOVENIN-004",
                  *{f"RIOIEGTIN-{n:03d}" for n in range(1, 6)}},
    "METROPOLITANA": {"RIORECLG-007", "RIORECIN-007", "RIORECLG-008", "RIORECIN-008",
                      "RIOVENLG-002", "RIOVENIN-002"},
    "LITORÂNEA": {"RIORECLG-003", "RIORECIN-003", "RIORECLG-004", "RIORECIN-004",
                  "RIORECLG-023", "RIORECIN-023", "RIOVENLG-001", "RIOVENIN-001"},
    "NORTE": {"RIORECLG-034", "RIORECIN-034", "RIOVENLG-005", "RIOVENIN-005"},
}


def equipe_geral(recurso: object) -> str | None:
    return EQUIPE_GERAL.get(_texto(recurso))


def regiao_programacao(recurso: object) -> str | None:
    valor = _texto(recurso)
    return next((regiao for regiao, recursos in REGIOES.items() if valor in recursos), None)


def projeto_programacao(codigo: object, observacao: object) -> str | None:
    if _texto(codigo) == "102002-VERIFICACAO CADASTRAL (VISTORIA CAMPO)":
        return "Impacta Cliente"
    texto = str(observacao or "").strip().lower()
    posicoes = [p for separador in (":", "-") if (p := texto.find(separador)) >= 0]
    if not posicoes:
        return None
    resultado = texto[:min(posicoes)].strip()
    if not resultado or len(resultado) > 40:
        return None
    return resultado[:1].upper() + resultado[1:]


def filtrar_programacao(dados: pd.DataFrame) -> pd.DataFrame:
    if "codigo_descricao" not in dados or not dados["codigo_descricao"].notna().any():
        return dados
    saida = dados.copy()
    saida["equipe_geral"] = saida["recurso"].map(equipe_geral)
    saida = saida[saida["equipe_geral"].notna()].copy()
    saida["regiao"] = saida["recurso"].map(regiao_programacao)
    saida["projeto"] = saida.apply(
        lambda linha: projeto_programacao(linha.get("codigo_descricao"), linha.get("observacao")),
        axis=1,
    )
    # `Projeto Principal` é calculado no contexto de cada recurso: ignora
    # checklist/refeição, escolhe o projeto mais frequente e aplica os dois
    # fallbacks literais existentes na medida DAX.
    atividade = saida.get("tipo_atividade", pd.Series("", index=saida.index)).map(_texto)
    validas = saida[~atividade.isin({"CHECKLIST INICIO", "REFEICAO"})]
    for recurso, grupo in validas.groupby("recurso", dropna=False):
        projetos = grupo["projeto"].dropna()
        contagem = len(grupo)
        codigo_recurso = _texto(recurso)
        if "RIOIEGTIN" in codigo_recurso and contagem >= 3:
            principal = "Implantação de TIL - Esgoto"
        elif not projetos.empty:
            principal = projetos.value_counts().index[0]
        elif codigo_recurso in {"RIORECIN-008", "RIORECIN-034"} and contagem >= 3:
            principal = "Projeto LocalizaE"
        else:
            principal = "Aguardando..."
        saida.loc[saida["recurso"] == recurso, "projeto"] = principal
    saida["qtd_os"] = 1.0
    return saida


def preparar_faturamento_implantacao(dados: pd.DataFrame) -> pd.DataFrame:
    saida = dados.copy()
    departamento = saida["departamento"].map(_texto)
    saida["frente"] = departamento.map({
        "VEM COM A GENTE": "VCG",
        "IMPLANTACAO DE LIGACAO AGUA": "Serviços",
    }).fillna("Outros")
    saida["faturado"] = saida["valor"].fillna(0).astype(float) > 0
    saida["quantidade"] = 1.0
    return saida


def aplicar(dataset: str, dados: pd.DataFrame) -> pd.DataFrame:
    regras = {
        "vendas": filtrar_vendas,
        "implantacao": filtrar_implantacoes,
        "termos": filtrar_termos,
        "programacao": filtrar_programacao,
        "faturamento_implantacao": preparar_faturamento_implantacao,
    }
    return regras.get(dataset, lambda valor: valor)(dados)
