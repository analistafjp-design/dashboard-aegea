"""Tipos base dos indicadores.

`Indicador` existe para cumprir a regra 60: um indicador pode valer 0,
pode não ter dados e pode não ter meta cadastrada — três situações
diferentes, nunca colapsadas em zero.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from app.utils.formato import moeda, numero, percentual

# Status visual (regra 6)
VERDE = "verde"
AMARELO = "amarelo"
VERMELHO = "vermelho"
AZUL = "azul"
CINZA = "cinza"

ROTULO_STATUS = {
    VERDE: "Meta atingida",
    AMARELO: "Atenção",
    VERMELHO: "Abaixo da meta",
    AZUL: "Acompanhamento",
    CINZA: "Sem dados",
}


@dataclass
class Filtros:
    """Filtros globais aplicáveis a qualquer módulo."""

    ano: int | None = None
    mes: int | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    cidade: str | None = None
    frente: str | None = None
    equipe: str | None = None
    regiao: str | None = None
    projeto: str | None = None
    setor: str | None = None

    def chave_cache(self) -> str:
        return "|".join(f"{k}={v}" for k, v in sorted(asdict(self).items()) if v is not None)

    def descricao(self) -> list[str]:
        rotulos = {
            "ano": "Ano", "mes": "Mês", "cidade": "Cidade", "frente": "Frente",
            "equipe": "Equipe", "regiao": "Região", "projeto": "Projeto", "setor": "Setor",
            "data_inicio": "De", "data_fim": "Até",
        }
        return [f"{rotulos[k]}: {v}" for k, v in asdict(self).items()
                if v is not None and k in rotulos]

    @property
    def ativo(self) -> bool:
        return any(v is not None for v in asdict(self).values())


@dataclass
class Indicador:
    """Um número com contexto: meta, comparação, status e explicação."""

    chave: str
    titulo: str
    valor: float | None = None
    formato: str = "numero"          # numero | moeda | percentual
    casas: int = 0
    disponivel: bool = True
    mensagem: str | None = None      # exibida quando não há valor
    anterior: float | None = None
    variacao: float | None = None    # % em relação ao período anterior
    meta: float | None = None
    status: str = AZUL
    explicacao: str = ""
    pergunta: str = ""               # pergunta gerencial (regra 56)
    detalhe: str = ""

    @property
    def texto(self) -> str:
        if not self.disponivel or self.valor is None:
            return self.mensagem or "Sem dados"
        if self.formato == "moeda":
            return moeda(self.valor)
        if self.formato == "percentual":
            return percentual(self.valor, self.casas or 1)
        return numero(self.valor, self.casas)

    rotulo_comparacao: str = "vs. mesmo período do mês anterior"

    @property
    def texto_variacao(self) -> str:
        if self.variacao is None:
            return "Sem base de comparação"
        seta = "▲" if self.variacao > 0 else ("▼" if self.variacao < 0 else "▬")
        return f"{seta} {percentual(abs(self.variacao))}"

    @property
    def direcao(self) -> str:
        if self.variacao is None:
            return "neutro"
        return "alta" if self.variacao > 0 else ("baixa" if self.variacao < 0 else "estavel")

    def to_dict(self) -> dict:
        dados = asdict(self)
        dados.update({
            "texto": self.texto,
            "texto_variacao": self.texto_variacao,
            "direcao": self.direcao,
            "rotulo_status": ROTULO_STATUS.get(self.status, ""),
        })
        return dados


@dataclass
class Serie:
    """Série pronta para o Plotly."""

    nome: str
    x: list = field(default_factory=list)
    y: list = field(default_factory=list)
    tipo: str = "bar"
    cor: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def sem_dados(chave: str, titulo: str, motivo: str = "Sem dados", **extra) -> Indicador:
    return Indicador(chave=chave, titulo=titulo, valor=None, disponivel=False,
                     mensagem=motivo, status=CINZA, **extra)


def variacao_percentual(atual: float | None, anterior: float | None) -> float | None:
    """None quando não há base de comparação; evita divisão por zero."""
    if atual is None or anterior is None or anterior == 0:
        return None
    return round((atual - anterior) / abs(anterior) * 100, 1)


def status_por_atingimento(atingimento: float | None,
                           limite_verde: float = 100.0,
                           limite_amarelo: float = 90.0) -> str:
    """Regra única de cor usada em todo o dashboard."""
    if atingimento is None:
        return CINZA
    if atingimento >= limite_verde:
        return VERDE
    if atingimento >= limite_amarelo:
        return AMARELO
    return VERMELHO


def calcular_atingimento(realizado: float | None, meta: float | None) -> float | None:
    if realizado is None or meta is None or meta == 0:
        return None
    return round(realizado / meta * 100, 1)


def calcular_falta(realizado: float | None, meta: float | None) -> float | None:
    if realizado is None or meta is None:
        return None
    return max(meta - realizado, 0.0)
