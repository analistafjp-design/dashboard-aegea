"""Configuração central da aplicação.

Todos os caminhos são resolvidos a partir da raiz do projeto, para que o
sistema funcione igual em Windows, Linux ou macOS e em qualquer diretório.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# O README orienta o uso de um arquivo .env na raiz. Carregá-lo aqui torna
# essa configuração efetiva tanto nos scripts de inicialização quanto ao
# executar o Uvicorn diretamente. Variáveis já definidas pelo ambiente (por
# exemplo, os segredos do Render) sempre têm prioridade.
load_dotenv(BASE_DIR / ".env", override=False)


def _env(nome: str, padrao: str) -> str:
    valor = os.getenv(nome)
    return valor if valor not in (None, "") else padrao


class Config:
    """Parâmetros de execução (podem ser sobrescritos por variáveis de ambiente)."""

    APP_NOME = _env("APP_NOME", "Dashboard Executivo")
    # O atualizador do Windows compara esta versao com o servidor que ja esta
    # aberto. Quando o codigo do painel muda, uma versao diferente garante que
    # o processo antigo seja encerrado e reiniciado antes de abrir o navegador.
    APP_VERSAO = "1.17.3"
    DEBUG = _env("DEBUG", "false").lower() in ("1", "true", "yes")

    BASE_DIR = BASE_DIR
    DATA_DIR = Path(_env("DATA_DIR", str(BASE_DIR / "data")))
    UPLOAD_DIR = DATA_DIR / "uploads"
    PROCESSED_DIR = DATA_DIR / "processed"
    DATABASE_DIR = DATA_DIR / "database"

    TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
    STATIC_DIR = BASE_DIR / "frontend" / "static"
    LOG_DIR = DATA_DIR / "logs"

    DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{DATABASE_DIR / 'dashboard.db'}")

    # Autenticação HTTP Basic — opcional. Quando AUTH_USUARIO e AUTH_SENHA
    # estão definidas (ex.: em produção, via variável de ambiente do
    # Render), o sistema exige login em toda a aplicação, inclusive na API
    # de upload. Sem as duas definidas, roda sem login — é o padrão em
    # desenvolvimento local, para não travar quem só quer testar.
    AUTH_USUARIO = _env("AUTH_USUARIO", "")
    AUTH_SENHA = _env("AUTH_SENHA", "")

    @property
    def AUTENTICACAO_ATIVA(self) -> bool:
        return bool(self.AUTH_USUARIO and self.AUTH_SENHA)

    # Segurança do upload
    EXTENSOES_PERMITIDAS = {".xlsx", ".xlsm", ".xls", ".csv"}
    TAMANHO_MAXIMO_MB = int(_env("TAMANHO_MAXIMO_MB", "50"))

    # Limite de linhas por arquivo — proteção contra estourar a memória da
    # instância (medido: ~115 MB só de a aplicação subir + ~140 MB a cada 60
    # mil linhas processadas; 100.000 linhas fica com folga confortável
    # dentro dos 512 MB do plano gratuito do Render). Ajustável via
    # variável de ambiente para quem migrar para um plano com mais RAM.
    LIMITE_LINHAS_ARQUIVO = int(_env("LIMITE_LINHAS_ARQUIVO", "100000"))

    # Acima de LIMITE_LINHAS_ARQUIVO o arquivo não é recusado: passa a ser
    # lido em blocos deste tamanho (ver app/etl/leitura.ler_em_blocos), o
    # que mantém a memória constante independentemente do tamanho do
    # arquivo. Bloco menor = menos memória e mais lento; maior = o inverso.
    LINHAS_POR_BLOCO = int(_env("LINHAS_POR_BLOCO", "20000"))

    # Cache de indicadores (segundos). O cache é invalidado a cada carga de dados.
    CACHE_TTL = int(_env("CACHE_TTL", "300"))

    # Feriados nacionais fixos usados pela dimensão calendário (dd-mm).
    FERIADOS_FIXOS = {
        (1, 1): "Confraternização Universal",
        (4, 21): "Tiradentes",
        (5, 1): "Dia do Trabalho",
        (9, 7): "Independência",
        (10, 12): "Nossa Senhora Aparecida",
        (11, 2): "Finados",
        (11, 15): "Proclamação da República",
        (12, 25): "Natal",
    }

    def criar_diretorios(self) -> None:
        for caminho in (
            self.DATA_DIR,
            self.UPLOAD_DIR,
            self.PROCESSED_DIR,
            self.DATABASE_DIR,
            self.LOG_DIR,
        ):
            caminho.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_config() -> Config:
    config = Config()
    config.criar_diretorios()
    return config


config = get_config()
