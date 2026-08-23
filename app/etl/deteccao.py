"""Identificação automática do arquivo pela estrutura das colunas (regra 53).

O nome do arquivo é apenas um desempate: o que decide é quantas colunas
conhecidas de cada dataset aparecem na planilha.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.etl.datasets import DATASETS, Dataset
from app.etl.leitura import Planilha
from app.utils.log import get_logger
from app.utils.texto import chave_comparacao, sem_acento

logger = get_logger("etl.deteccao")

PONTUACAO_MINIMA = 0.45
BONUS_EXCLUSIVO = 0.20            # campos que só existem neste dataset
PENALIDADE_EXCLUSIVO_ALHEIO = 0.12  # campos que só existem em outro dataset
BONUS_NOME_ARQUIVO = 0.08

# Algumas exportações do Field Service trazem simultaneamente a chave
# numérica "Setor" e a descrição "Setor do Recurso.Setor do Recurso".
# Para os gráficos gerenciais precisamos sempre do nome descritivo.
COLUNAS_PREFERIDAS = {
    "setor": ("setordorecursosetordorecurso",),
}


@dataclass
class Identificacao:
    dataset: Dataset | None
    planilha: Planilha
    pontuacao: float
    mapeamento: dict[str, str]      # campo interno -> coluna original
    faltantes: list[str]            # campos obrigatórios não encontrados
    colunas_ignoradas: list[str]

    @property
    def compativel(self) -> bool:
        return self.dataset is not None and not self.faltantes


def mapear_colunas(dataset: Dataset, colunas: list[str]) -> dict[str, str]:
    """Casa cada campo do dataset com a coluna correspondente da planilha."""
    disponiveis = {chave_comparacao(c): c for c in colunas}
    mapeamento: dict[str, str] = {}
    usadas: set[str] = set()

    # Prioridades explícitas são avaliadas antes do nome interno. Sem isso,
    # o campo ``setor`` casaria com a coluna numérica "Setor" e ignoraria a
    # coluna textual usada no Power BI.
    for campo in dataset.campos:
        for chave in COLUNAS_PREFERIDAS.get(campo.nome, ()):
            coluna = disponiveis.get(chave)
            if coluna is not None and coluna not in usadas:
                mapeamento[campo.nome] = coluna
                usadas.add(coluna)
                break

    # 1ª passada: correspondência exata de nome ou sinônimo.
    for campo in dataset.campos:
        if campo.nome in mapeamento:
            continue
        for chave in campo.chaves:
            coluna = disponiveis.get(chave)
            if coluna is not None and coluna not in usadas:
                mapeamento[campo.nome] = coluna
                usadas.add(coluna)
                break

    # 2ª passada: correspondência parcial ("data_da_atividade_real" ~ "data atividade").
    for campo in dataset.campos:
        if campo.nome in mapeamento:
            continue
        # "Situação" é semanticamente ampla demais para casamento parcial:
        # "Situação Faturamento" pertence à implantação, enquanto
        # "Situação do Termo" pertence ao faturamento de termos.
        if campo.nome == "situacao":
            continue
        for chave_campo in sorted(campo.chaves, key=len, reverse=True):
            if len(chave_campo) < 4:
                continue
            achou = next(
                (col for chave, col in disponiveis.items()
                 if col not in usadas and (chave_campo in chave or chave in chave_campo)),
                None,
            )
            if achou:
                mapeamento[campo.nome] = achou
                usadas.add(achou)
                break
    return mapeamento


@lru_cache(maxsize=1)
def _campos_exclusivos() -> dict[str, dict[str, set[str]]]:
    """Campos cujas chaves só existem em um dataset — são o que diferencia
    bases parecidas (ex.: 'Serviço' e 'Situação Faturamento' só existem em
    Implantação, então uma planilha com essas colunas não é Venda)."""
    # Bases somente-manual ficam de fora da contagem: elas não competem na
    # detecção, então não faz sentido que suas colunas tirem a
    # exclusividade das que realmente identificam as demais.
    automaticos = {n: d for n, d in DATASETS.items() if not d.somente_manual}

    contagem: dict[str, int] = {}
    for dataset in automaticos.values():
        for chave in {c for campo in dataset.campos for c in campo.chaves}:
            contagem[chave] = contagem.get(chave, 0) + 1

    exclusivos: dict[str, dict[str, set[str]]] = {}
    for nome, dataset in automaticos.items():
        exclusivos[nome] = {
            campo.nome: {c for c in campo.chaves if contagem.get(c) == 1}
            for campo in dataset.campos
            if any(contagem.get(c) == 1 for c in campo.chaves)
        }
    return exclusivos


def pontuar(dataset: Dataset, planilha: Planilha, nome_arquivo: str = "") -> Identificacao:
    colunas = [str(c) for c in planilha.dados.columns]
    chaves_colunas = {chave_comparacao(c) for c in colunas}
    mapeamento = mapear_colunas(dataset, colunas)

    peso_total = sum(c.peso for c in dataset.campos)
    peso_obtido = sum(c.peso for c in dataset.campos if c.nome in mapeamento)
    pontuacao = peso_obtido / peso_total if peso_total else 0.0

    # Um campo obrigatório COM valor padrão não precisa existir como coluna:
    # a transformação preenche o padrão (ex.: 'qtd os' num arquivo em que
    # cada linha já é uma O.S. — a coluna não existe, mas cada linha vale 1).
    # Sem essa ressalva, arquivos legítimos eram recusados com "a coluna
    # 'qtd os' não foi encontrada".
    faltantes = [c.nome for c in dataset.obrigatorios
                 if c.nome not in mapeamento and c.padrao is None]
    if faltantes:
        pontuacao *= 0.35  # sem coluna obrigatória o dataset dificilmente é este

    exclusivos = _campos_exclusivos()
    proprios = exclusivos.get(dataset.nome, {})
    if proprios:
        encontrados = sum(1 for campo in proprios if campo in mapeamento)
        pontuacao += BONUS_EXCLUSIVO * (encontrados / len(proprios))

    # Colunas exclusivas de OUTRO dataset presentes na planilha derrubam a nota.
    for outro, campos in exclusivos.items():
        if outro == dataset.nome:
            continue
        marcas = sum(1 for chaves in campos.values() if set(chaves) & chaves_colunas)
        if marcas:
            pontuacao -= PENALIDADE_EXCLUSIVO_ALHEIO * marcas

    nome = sem_acento(nome_arquivo).lower()
    if any(dica in nome for dica in dataset.dicas_nome_arquivo):
        pontuacao += BONUS_NOME_ARQUIVO

    ignoradas = [c for c in colunas if c not in set(mapeamento.values())]
    return Identificacao(dataset, planilha, round(min(max(pontuacao, 0.0), 1.0), 4), mapeamento,
                         faltantes, ignoradas)


def identificar(planilhas: list[Planilha], nome_arquivo: str = "",
                dataset_forcado: str | None = None) -> Identificacao:
    """Escolhe o par (dataset, planilha) com melhor aderência."""
    candidatos: list[Identificacao] = []
    datasets = (
        [DATASETS[dataset_forcado]] if dataset_forcado in DATASETS
        else [d for d in DATASETS.values() if not d.somente_manual]
    )
    for planilha in planilhas:
        for dataset in datasets:
            candidatos.append(pontuar(dataset, planilha, nome_arquivo))

    candidatos.sort(key=lambda i: (i.compativel, i.pontuacao), reverse=True)
    melhor = candidatos[0]
    logger.info(
        "Detecção de '%s': %s (aba '%s', aderência %.0f%%)",
        nome_arquivo or "arquivo", melhor.dataset.nome if melhor.dataset else "-",
        melhor.planilha.nome, melhor.pontuacao * 100,
    )
    if dataset_forcado in DATASETS:
        return melhor
    if melhor.pontuacao < PONTUACAO_MINIMA:
        return Identificacao(None, melhor.planilha, melhor.pontuacao, {},
                             melhor.faltantes, melhor.colunas_ignoradas)
    return melhor


def analisar_arquivo(caminho: Path, dataset_forcado: str | None = None) -> Identificacao:
    from app.etl.leitura import ler_planilhas

    return identificar(ler_planilhas(caminho), caminho.name, dataset_forcado)
