"""Padronização dos domínios de negócio (frentes, tipos, situações).

As frentes NÃO são agrupadas: Comercial, VCG, Serviços, VCG Rio Bonito e
VCG Bairro Legal/SFI permanecem identificáveis (regra 18). O que este
módulo faz é apenas uniformizar a grafia vinda das planilhas.
"""
from __future__ import annotations

import pandas as pd

from app.utils.texto import sem_acento

# Frentes canônicas
COMERCIAL = "Comercial"
VCG = "VCG"
SERVICOS = "Serviços"
VCG_RIO_BONITO = "VCG Rio Bonito"
VCG_SFI = "VCG Bairro Legal/SFI"
OUTROS_CANAIS = "Outros Canais"
NAO_INFORMADO = "Não Informado"

FRENTES_CANONICAS = (COMERCIAL, VCG, SERVICOS, VCG_RIO_BONITO, VCG_SFI, OUTROS_CANAIS)

# Canais de venda (agrupamento das medidas Venda Comercial / VCG / Outros)
CANAL_COMERCIAL = "COMERCIAL"
CANAL_VCG = "VCG"
CANAL_OUTROS = "OUTROS"

# Tipos de produção
TIPO_SERVICOS = "SERVICOS"
TIPO_VCG = "VCG"
TIPO_NAO_CLASSIFICADO = "NAO_CLASSIFICADO"

# Situações do funil de faturamento de termos
SIT_NEGOCIACAO = "Negociação"
SIT_AGUARDANDO = "Aguardando"
SIT_FATURADO = "Faturado"
SIT_CANCELADO = "Cancelado"
SIT_OUTRA = "Outras"

FUNIL_FATURAMENTO = (SIT_NEGOCIACAO, SIT_AGUARDANDO, SIT_FATURADO)


def _k(valor: object) -> str:
    # `pd.NA` não pode ser avaliado como verdadeiro/falso. Exportações reais
    # do Field Service usam esse marcador em várias colunas opcionais.
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return sem_acento(str(valor)).strip().lower()


def normalizar_frente(valor: object) -> str:
    """Texto livre da planilha -> frente canônica."""
    texto = _k(valor)
    if not texto:
        return NAO_INFORMADO
    if "rio bonito" in texto:
        return VCG_RIO_BONITO
    if "sfi" in texto or "bairro legal" in texto:
        return VCG_SFI
    if "vcg" in texto:
        return VCG
    if "comercial" in texto:
        return COMERCIAL
    if "servico" in texto or "serviço" in texto:
        return SERVICOS
    if "outro" in texto or "canal" in texto or "parceiro" in texto or "digital" in texto:
        return OUTROS_CANAIS
    return str(valor).strip()


def canal_venda(frente: object) -> str:
    """Frente -> canal usado nas medidas de venda."""
    frente_canonica = normalizar_frente(frente)
    if frente_canonica == COMERCIAL:
        return CANAL_COMERCIAL
    if frente_canonica in (VCG, VCG_RIO_BONITO, VCG_SFI):
        return CANAL_VCG
    return CANAL_OUTROS


def classificar_tipo(*valores: object) -> str:
    """Deriva SERVICOS x VCG a partir de tipo/frente/serviço."""
    for valor in valores:
        texto = _k(valor)
        if not texto:
            continue
        if "vcg" in texto:
            return TIPO_VCG
        if "servico" in texto or "serviço" in texto:
            return TIPO_SERVICOS
    return TIPO_NAO_CLASSIFICADO


def rotulo_tipo(tipo: str) -> str:
    return {TIPO_SERVICOS: "Serviços", TIPO_VCG: "VCG"}.get(tipo, "Não Classificado")


def normalizar_situacao_faturamento(valor: object) -> str:
    texto = _k(valor)
    if not texto:
        return SIT_OUTRA
    if "cancel" in texto:
        return SIT_CANCELADO
    if "fatur" in texto and "nao" not in texto and "não" not in texto:
        return SIT_FATURADO
    if "aguard" in texto or "pendente" in texto or "analise" in texto:
        return SIT_AGUARDANDO
    if "negocia" in texto or "andamento" in texto or "tratativa" in texto:
        return SIT_NEGOCIACAO
    if "concluid" in texto or "pago" in texto:
        return SIT_FATURADO
    return str(valor).strip().title()


def normalizar_status_termo(valor: object) -> str:
    texto = _k(valor)
    if not texto:
        return "Não Informado"
    if "aplicad" in texto or "ativo" in texto:
        return "Aplicado"
    if "cancel" in texto:
        return "Cancelado"
    if "pendente" in texto or "aguard" in texto:
        return "Pendente"
    return str(valor).strip().title()


def normalizar_modulo_meta(valor: object) -> str:
    texto = _k(valor)
    if "termo" in texto:
        return "TERMOS"
    if "venda" in texto or "comercial" in texto:
        return "VENDA"
    if "implanta" in texto:
        return "IMPLANTACAO"
    return str(valor or "").strip().upper() or "TOTAL"


def normalizar_segmento_meta(valor: object) -> str:
    texto = _k(valor)
    if not texto or "total" in texto or "geral" in texto:
        return "TOTAL"
    if "vcg" in texto:
        return "VCG"
    if "servico" in texto:
        return "SERVICOS"
    if "comercial" in texto:
        return "COMERCIAL"
    if "outro" in texto:
        return "OUTROS"
    return texto.upper()
