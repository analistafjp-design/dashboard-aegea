"""Regra de negócio da base Atendimento (Vendas por Outros Canais).

Transcrição fiel da medida do Power BI usada hoje:

    Vendas Outros Canais =
    CALCULATE(
        COUNTROWS('Atendimento'),
        'Atendimento'[OCORRENCIA_ENCERRAMENTO] = "0-Executado",
        NOT(ISBLANK('Atendimento'[Nº LIGAÇÃO])),
        'Atendimento'[DESCRIÇÃO DO SERVIÇO] IN { ...5 serviços... },
        'Atendimento'[LOCALIDADE] IN { ...12 localidades... },
        NOT(UPPER(TRIM('Atendimento'[USUÁRIO EMITIU O.S.])) IN { ...3 usuários... })
    )

Cada linha que sobra dos cinco filtros é UMA venda por outros canais —
`COUNTROWS` conta linhas, então a quantidade de cada registro é 1.

As listas ficam aqui, em um só lugar, para poderem ser conferidas contra o
Power BI e ajustadas sem mexer no restante do ETL.
"""
from __future__ import annotations

import unicodedata

import pandas as pd

OCORRENCIA_EXECUTADO = "0-executado"

# 'Atendimento'[DESCRIÇÃO DO SERVIÇO] IN { ... }
SERVICOS = (
    '117002 - IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA 3/4" - ASFALTO',
    "117081 - IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA SOCIAL - BLOCO/PARALELO",
    "117076 - IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA SOCIAL - TERRA",
    '117045 - IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA 3/4" - BLOCO/PARALELO',
    "117006 - IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA - MEDIÇÃO INDIVIDUALIZADA",
)

# 'Atendimento'[LOCALIDADE] IN { ... }
LOCALIDADES = (
    "APERIBE", "CACHOEIRAS DE MACACU", "CAMBUCI", "CANTAGALO",
    "CASIMIRO DE ABREU", "CORDEIRO", "DUAS BARRAS", "ITAOCARA",
    "MIRACEMA", "RIO BONITO", "S.FCO.DO ITABAPOANA", "S.SEBASTIAO DO ALTO",
)

# NOT(UPPER(TRIM('Atendimento'[USUÁRIO EMITIU O.S.])) IN { ... })
USUARIOS_EXCLUIDOS = (
    "ELBA SILVA GREGORIO",
    "BEATRIZ TAVARES MAGALHAES",
    "YANDRA DA SILVA FLOR",
)


def _comparavel(valor: object) -> str:
    """UPPER(TRIM(...)) tolerante a acento e a espaços duplicados.

    O Power BI compara o texto exatamente como está na planilha. Aqui a
    comparação é um pouco mais frouxa de propósito: acento e espaço extra
    variam entre exportações do mesmo relatório e fariam uma linha válida
    ser descartada em silêncio — o que apareceria como número menor que o
    do Power BI, sem nenhum aviso.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = " ".join(str(valor).split()).strip().upper()
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


_SERVICOS = {_comparavel(s) for s in SERVICOS}
_LOCALIDADES = {_comparavel(c) for c in LOCALIDADES}
_USUARIOS_EXCLUIDOS = {_comparavel(u) for u in USUARIOS_EXCLUIDOS}
_OCORRENCIA = _comparavel(OCORRENCIA_EXECUTADO)


def _preenchido(valor: object) -> bool:
    """NOT(ISBLANK(...)) — vazio, nulo e "0" contam como em branco."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return False
    texto = str(valor).strip()
    return texto not in ("", "0", "nan", "None")


def linha_e_venda_outros_canais(linha: dict) -> bool:
    """Aplica os cinco filtros da medida a UMA linha já mapeada."""
    if _comparavel(linha.get("ocorrencia")) != _OCORRENCIA:
        return False
    if not _preenchido(linha.get("ligacao")):
        return False
    if _comparavel(linha.get("servico")) not in _SERVICOS:
        return False
    if _comparavel(linha.get("cidade")) not in _LOCALIDADES:
        return False
    if _comparavel(linha.get("usuario_emissor")) in _USUARIOS_EXCLUIDOS:
        return False
    return True


def filtrar(dados: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Devolve só as linhas que a medida contaria, mais o motivo de cada
    descarte (para a tela de resultado explicar o que foi deixado de fora
    em vez de o número simplesmente vir menor)."""
    if dados.empty:
        return dados, {}

    motivos: dict[str, int] = {}
    manter = []
    for linha in dados.to_dict("records"):
        if _comparavel(linha.get("ocorrencia")) != _OCORRENCIA:
            chave = "linha(s) fora de '0-Executado' (não contam como venda)"
        elif not _preenchido(linha.get("ligacao")):
            chave = "linha(s) sem Nº Ligação (não contam como venda)"
        elif _comparavel(linha.get("servico")) not in _SERVICOS:
            chave = "linha(s) de serviço fora da lista de implantação de ligação de água"
        elif _comparavel(linha.get("cidade")) not in _LOCALIDADES:
            chave = "linha(s) de localidade fora da região do Interior"
        elif _comparavel(linha.get("usuario_emissor")) in _USUARIOS_EXCLUIDOS:
            chave = "linha(s) emitidas por usuário excluído da medida"
        else:
            manter.append(True)
            continue
        manter.append(False)
        motivos[chave] = motivos.get(chave, 0) + 1

    return dados[pd.Series(manter, index=dados.index)], motivos
