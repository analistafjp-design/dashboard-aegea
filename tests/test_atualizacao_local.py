import json
from pathlib import Path

from scripts.atualizar_dashboard_local import (
    arquivo_mudou,
    carregar_manifesto,
    carregar_pastas,
    encontrar_arquivos,
    salvar_manifesto,
)


def test_carrega_pastas_e_conta_arquivo_fisico_uma_so_vez(tmp_path):
    interior = tmp_path / "Interior"
    interior.mkdir()
    planilha = interior / "base.xlsx"
    planilha.write_bytes(b"teste")
    configuracao = tmp_path / "pastas.txt"
    configuracao.write_text(
        f"{interior} = vendas, implantacao, termos\n", encoding="utf-8"
    )

    entradas = carregar_pastas(configuracao)
    arquivos = encontrar_arquivos(entradas)

    assert len(arquivos) == 1
    assert arquivos[planilha.resolve()] == {"vendas", "implantacao", "termos"}


def test_manifesto_pula_arquivo_inalterado_e_detecta_alteracao(tmp_path):
    planilha = tmp_path / "base.csv"
    planilha.write_text("data;valor\n2026-08-22;1\n", encoding="utf-8")
    caminho_manifesto = tmp_path / "manifesto.json"
    manifesto = {"versao": 1, "arquivos": {}}

    assert arquivo_mudou(planilha.resolve(), manifesto)
    info = planilha.stat()
    manifesto["arquivos"][str(planilha.resolve())] = {
        "tamanho": info.st_size,
        "modificado_ns": info.st_mtime_ns,
        "bases": ["vendas"],
        "status": "processado",
    }
    salvar_manifesto(caminho_manifesto, manifesto)
    recarregado = carregar_manifesto(caminho_manifesto)
    assert not arquivo_mudou(planilha.resolve(), recarregado)

    planilha.write_text("data;valor\n2026-08-22;12\n", encoding="utf-8")
    assert arquivo_mudou(planilha.resolve(), recarregado)


def test_manifesto_e_json_legivel(tmp_path):
    caminho = tmp_path / "manifesto.json"
    salvar_manifesto(caminho, {"versao": 1, "arquivos": {}})
    assert json.loads(caminho.read_text(encoding="utf-8"))["versao"] == 1
