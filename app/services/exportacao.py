"""Exportação de dados: Excel, CSV e PDF."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils.erros import ErroDashboard

FORMATOS = ("xlsx", "csv", "pdf")

TIPOS_MIME = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "pdf": "application/pdf",
}


def _titulo_coluna(coluna: object) -> str:
    texto = str(coluna)
    return texto.replace("_", " ").title() if "_" in texto else texto


def _preparar(tabelas: dict[str, list[dict]]) -> dict[str, pd.DataFrame]:
    preparadas = {}
    for nome, registros in tabelas.items():
        if not registros:
            continue
        preparadas[nome[:31]] = pd.DataFrame(registros)
    if not preparadas:
        raise ErroDashboard("Não há dados para exportar com os filtros selecionados.")
    return preparadas


def para_excel(tabelas: dict[str, list[dict]], titulo: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        livro = writer.book
        cabecalho = livro.add_format({
            "bold": True, "bg_color": "#0B3C7D", "font_color": "white",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        for nome, dados in _preparar(tabelas).items():
            dados.to_excel(writer, sheet_name=nome, index=False, startrow=1, header=False)
            planilha = writer.sheets[nome]
            for indice, coluna in enumerate(dados.columns):
                planilha.write(0, indice, _titulo_coluna(coluna), cabecalho)
                maior = dados[coluna].astype(str).str.len().max()
                maior = 12 if pd.isna(maior) else int(maior)
                largura = max(12, min(40, maior + 2))
                planilha.set_column(indice, indice, largura)
            planilha.freeze_panes(1, 0)
            planilha.autofilter(0, 0, len(dados), max(len(dados.columns) - 1, 0))
    return buffer.getvalue()


def para_csv(tabelas: dict[str, list[dict]]) -> bytes:
    preparadas = _preparar(tabelas)
    partes = []
    for nome, dados in preparadas.items():
        if len(preparadas) > 1:
            partes.append(f"# {nome}")
        partes.append(dados.to_csv(index=False, sep=";", decimal=","))
    return "\n".join(partes).encode("utf-8-sig")


def para_pdf(tabelas: dict[str, list[dict]], titulo: str, subtitulo: str = "") -> bytes:
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), title=titulo,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = [Paragraph(f"<b>{titulo}</b>", estilos["Title"])]
    if subtitulo:
        elementos.append(Paragraph(subtitulo, estilos["Normal"]))
    elementos.append(Paragraph(
        f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", estilos["Normal"]))
    elementos.append(Spacer(1, 0.5 * cm))

    for nome, dados in _preparar(tabelas).items():
        elementos.append(Paragraph(f"<b>{nome.replace('_', ' ').title()}</b>", estilos["Heading3"]))
        recorte = dados.head(60).fillna("-")
        conteudo = [[_titulo_coluna(c) for c in recorte.columns]]
        conteudo += [[str(v) for v in linha] for linha in recorte.values.tolist()]
        tabela = Table(conteudo, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3C7D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D4E4")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5FA")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elementos.append(tabela)
        if len(dados) > 60:
            elementos.append(Paragraph(
                f"<i>Exibindo 60 de {len(dados)} linhas. Use Excel ou CSV para o conteúdo "
                f"completo.</i>", estilos["Normal"]))
        elementos.append(Spacer(1, 0.6 * cm))

    documento.build(elementos)
    return buffer.getvalue()


def exportar(tabelas: dict[str, list[dict]], formato: str, titulo: str,
             subtitulo: str = "") -> tuple[bytes, str, str]:
    """Devolve (conteúdo, nome do arquivo, mime)."""
    if formato not in FORMATOS:
        raise ErroDashboard(f"Formato '{formato}' não suportado. Use xlsx, csv ou pdf.")
    carimbo = datetime.now().strftime("%Y%m%d_%H%M")
    base = titulo.lower().replace(" ", "_").replace("ç", "c").replace("ã", "a")
    nome = f"{base}_{carimbo}.{formato}"
    if formato == "xlsx":
        return para_excel(tabelas, titulo), nome, TIPOS_MIME["xlsx"]
    if formato == "csv":
        return para_csv(tabelas), nome, TIPOS_MIME["csv"]
    return para_pdf(tabelas, titulo, subtitulo), nome, TIPOS_MIME["pdf"]
