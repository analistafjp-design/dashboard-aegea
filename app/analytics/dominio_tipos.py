"""Reexporta as constantes de domínio para a camada de análise."""
from app.etl.dominio import (  # noqa: F401
    CANAL_COMERCIAL,
    CANAL_OUTROS,
    CANAL_VCG,
    FRENTES_CANONICAS,
    FUNIL_FATURAMENTO,
    SIT_AGUARDANDO,
    SIT_CANCELADO,
    SIT_FATURADO,
    SIT_NEGOCIACAO,
    TIPO_NAO_CLASSIFICADO,
    TIPO_SERVICOS,
    TIPO_VCG,
    rotulo_tipo,
)
