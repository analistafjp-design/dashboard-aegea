"""Processamento de upload em segundo plano.

Por que isso existe: processar planilha é trabalho pesado e SÍNCRONO
(pandas, openpyxl, SQLAlchemy). Fazer isso dentro da rota `async def`
bloqueia o event loop do servidor inteiro — enquanto um upload processa,
NENHUMA outra requisição é respondida, nem o health check que o Render usa
para saber se a instância está viva. Numa máquina rápida isso é um soluço
de alguns segundos; nos 0.1 de CPU do plano gratuito vira minutos, o Render
declara a instância morta, reinicia o container no meio do upload e o
navegador recebe "Falha de comunicação com o servidor" (ou 502 em qualquer
outra página aberta na mesma hora).

A solução é a rota devolver na hora um identificador de trabalho e o
processamento acontecer numa thread separada, com a tela perguntando o
progresso de tempos em tempos. Assim o event loop nunca trava, o health
check continua respondendo e a tela mostra progresso REAL (arquivo X de Y)
em vez de uma animação cronometrada que só parecia estar avançando.

Uma thread só (`max_workers=1`): dois lotes processando juntos dobrariam o
uso de memória, que é justamente o recurso escasso aqui.
"""
from __future__ import annotations

import gc
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from app.analytics import cache
from app.etl.pipeline import ordenar_para_carga, processar_arquivo
from app.models.db import sessao
from app.services.upload import nome_exibicao
from app.utils.log import get_logger

logger = get_logger("processamento")

PROCESSANDO = "PROCESSANDO"
CONCLUIDO = "CONCLUIDO"
ERRO = "ERRO"

# Trabalhos terminados somem da memória depois disso (a tela já leu o
# resultado bem antes; guardar para sempre seria vazamento).
VALIDADE_TRABALHO = timedelta(hours=1)
MAX_TRABALHOS = 50


@dataclass
class Trabalho:
    id: str
    total: int
    status: str = PROCESSANDO
    concluidos: int = 0
    arquivo_atual: str | None = None
    resultados: list[dict] = field(default_factory=list)
    mensagem: str = ""
    criado_em: datetime = field(default_factory=datetime.now)
    terminado_em: datetime | None = None

    @property
    def percentual(self) -> int:
        if self.total <= 0:
            return 100
        return min(100, round(self.concluidos / self.total * 100))

    def to_dict(self) -> dict:
        return {
            "trabalho_id": self.id,
            "status": self.status,
            "total": self.total,
            "concluidos": self.concluidos,
            "percentual": self.percentual,
            "arquivo_atual": self.arquivo_atual,
            "resultados": self.resultados,
            "mensagem": self.mensagem,
        }


_trabalhos: dict[str, Trabalho] = {}
_trava = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="upload")


def _limpar_antigos() -> None:
    """Chamado com `_trava` já adquirida."""
    limite = datetime.now() - VALIDADE_TRABALHO
    vencidos = [
        chave for chave, t in _trabalhos.items()
        if t.terminado_em is not None and t.terminado_em < limite
    ]
    for chave in vencidos:
        _trabalhos.pop(chave, None)

    if len(_trabalhos) > MAX_TRABALHOS:
        por_idade = sorted(_trabalhos.values(), key=lambda t: t.criado_em)
        for antigo in por_idade[: len(_trabalhos) - MAX_TRABALHOS]:
            if antigo.status != PROCESSANDO:
                _trabalhos.pop(antigo.id, None)


def obter(trabalho_id: str) -> Trabalho | None:
    with _trava:
        return _trabalhos.get(trabalho_id)


def agendar(caminhos: list[Path], forcados: dict[str, str],
            erros_iniciais: list[dict] | None = None, usuario: str = "local") -> Trabalho:
    """Registra o trabalho e devolve na hora — o processamento roda depois,
    fora da thread que atende a requisição HTTP."""
    trabalho = Trabalho(id=uuid.uuid4().hex, total=len(caminhos))
    trabalho.resultados = list(erros_iniciais or [])
    with _trava:
        _limpar_antigos()
        _trabalhos[trabalho.id] = trabalho
    _executor.submit(_executar, trabalho.id, caminhos, forcados, usuario)
    logger.info("Trabalho %s agendado: %s arquivo(s)", trabalho.id, len(caminhos))
    return trabalho


def _executar(trabalho_id: str, caminhos: list[Path], forcados: dict[str, str],
              usuario: str) -> None:
    trabalho = obter(trabalho_id)
    if trabalho is None:  # pragma: no cover - só se expirar antes de rodar
        return
    try:
        # Uma sessão POR ARQUIVO (em vez de uma só para o lote inteiro): o
        # identity map do SQLAlchemy é descartado a cada arquivo, então a
        # memória não cresce acumulando o lote todo, e cada arquivo já fica
        # gravado — se o processo morrer no arquivo 15, os 14 anteriores
        # não se perdem.
        for caminho in ordenar_para_carga(caminhos, forcados):
            with _trava:
                trabalho.arquivo_atual = nome_exibicao(caminho.name)
            try:
                with sessao() as s:
                    resultado = processar_arquivo(
                        s, caminho, forcados.get(caminho.name), usuario)
            finally:
                # O arquivo aceito já foi copiado para data/processed quando
                # a carga deu certo. A cópia temporária de data/uploads não
                # pode ficar acumulando indefinidamente e enchendo o disco.
                try:
                    caminho.unlink(missing_ok=True)
                except OSError as erro:  # pragma: no cover - depende do disco/SO
                    logger.warning("Não foi possível remover upload temporário %s: %s",
                                   caminho, erro)
            with _trava:
                trabalho.resultados.append(resultado.to_dict())
                trabalho.concluidos += 1
            del resultado
            gc.collect()

        cache.invalidar()
        with _trava:
            trabalho.status = CONCLUIDO
            trabalho.arquivo_atual = None
            trabalho.mensagem = resumo_do_lote(trabalho.resultados)
            trabalho.terminado_em = datetime.now()
        logger.info("Trabalho %s concluído: %s", trabalho_id, trabalho.mensagem)

    except Exception:  # noqa: BLE001 - nunca deixa o trabalho pendurado
        logger.exception("Falha inesperada no trabalho %s", trabalho_id)
        cache.invalidar()
        with _trava:
            trabalho.status = ERRO
            trabalho.arquivo_atual = None
            trabalho.terminado_em = datetime.now()
            trabalho.mensagem = (
                "A atualização foi interrompida por um erro inesperado. "
                "O que já havia sido importado antes do erro foi mantido; "
                "o erro está registrado no log do sistema."
            )


def resumo_do_lote(resultados: list[dict]) -> str:
    if not resultados:
        return "Nenhum arquivo processado."
    sucessos = [r for r in resultados if r.get("status") in ("SUCESSO", "ATENCAO")]
    falhas = [r for r in resultados if r.get("status") == "ERRO"]
    registros = sum(r.get("inseridos", 0) + r.get("atualizados", 0) for r in sucessos)
    if sucessos and not falhas:
        return f"Dashboard atualizado: {registros} registro(s) de {len(sucessos)} arquivo(s)."
    if sucessos and falhas:
        return (f"{len(sucessos)} arquivo(s) importado(s) ({registros} registros) e "
                f"{len(falhas)} com problema.")
    return f"Nenhum arquivo pôde ser importado ({len(falhas)} com problema)."
