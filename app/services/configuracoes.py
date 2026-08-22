"""Preferências do usuário salvas no banco (página Configurações)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.db import sessao
from app.models.tabelas import Configuracao

PADROES: dict[str, str] = {
    "tema": "claro",
    "periodo_padrao": "mes_atual",
    "linhas_tabela": "25",
    "casas_decimais": "0",
    "mostrar_insights": "sim",
    "mostrar_alertas": "sim",
    "formato_exportacao": "xlsx",
}

OPCOES = {
    "tema": ["claro", "escuro"],
    "periodo_padrao": ["mes_atual", "ultimo_mes_com_dados", "ano_atual"],
    "linhas_tabela": ["10", "25", "50", "100"],
    "casas_decimais": ["0", "1", "2"],
    "mostrar_insights": ["sim", "nao"],
    "mostrar_alertas": ["sim", "nao"],
    "formato_exportacao": ["xlsx", "csv", "pdf"],
}


def ler_todas() -> dict[str, str]:
    valores = dict(PADROES)
    with sessao() as s:
        for registro in s.execute(select(Configuracao)).scalars():
            if registro.chave in PADROES:
                valores[registro.chave] = registro.valor
    return valores


def salvar(novas: dict[str, str]) -> dict[str, str]:
    with sessao() as s:
        for chave, valor in novas.items():
            if chave not in PADROES:
                continue
            if chave in OPCOES and str(valor) not in OPCOES[chave]:
                continue
            registro = s.get(Configuracao, chave)
            if registro is None:
                s.add(Configuracao(chave=chave, valor=str(valor)))
            else:
                registro.valor = str(valor)
                registro.atualizado_em = datetime.now()
    return ler_todas()
