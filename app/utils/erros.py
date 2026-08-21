"""Exceções de negócio com mensagem pronta para o usuário final."""
from __future__ import annotations


class ErroDashboard(Exception):
    """Base: sempre carrega uma mensagem em português, sem jargão técnico."""

    def __init__(self, mensagem: str, detalhes: list[str] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes or []

    def to_dict(self) -> dict:
        return {"ok": False, "mensagem": self.mensagem, "detalhes": self.detalhes}


class ErroValidacaoArquivo(ErroDashboard):
    """Arquivo enviado não passou na validação (extensão, tamanho, colunas...)."""


class ErroImportacao(ErroDashboard):
    """Falha durante a leitura/gravação dos dados."""


class ErroSemDados(ErroDashboard):
    """Consulta executada, porém a base não possui registros para o filtro."""
