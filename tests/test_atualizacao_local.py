import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from scripts import atualizar_dashboard_local as atualizador
from scripts.atualizar_dashboard_local import (
    arquivo_mudou,
    carregar_manifesto,
    carregar_pastas,
    encontrar_arquivos,
    salvar_manifesto,
    selecionar_fontes_implantacao,
    tipos_pendentes,
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


def test_implantacao_usa_so_relatorios_proprios_e_snapshot_mais_novo(tmp_path):
    antigo_vcg = tmp_path / "Validação - Implantação.xlsx"
    atual_vcg = tmp_path / "Validação - Implantação(1).xlsx"
    servicos = tmp_path / "Implantação - Serviços.xlsx"
    vendas = tmp_path / "Relatório de Vendas.xlsx"
    for caminho in (antigo_vcg, atual_vcg, servicos, vendas):
        caminho.write_bytes(b"planilha")
    os.utime(antigo_vcg, ns=(1, 1))
    os.utime(atual_vcg, ns=(2, 2))

    permitidos = {"vendas", "implantacao", "termos"}
    arquivos = {
        caminho: set(permitidos)
        for caminho in (antigo_vcg, atual_vcg, servicos, vendas)
    }

    resultado = selecionar_fontes_implantacao(arquivos)

    assert "implantacao" not in resultado[antigo_vcg]
    assert "implantacao" in resultado[atual_vcg]
    assert "implantacao" in resultado[servicos]
    assert "implantacao" not in resultado[vendas]
    # A seleção da fonte de implantação não impede as outras bases.
    assert resultado[vendas] == {"vendas", "termos"}


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


def test_mudanca_de_regra_reprocessa_somente_termos_uma_vez(tmp_path):
    planilha = tmp_path / "atividades.xlsx"
    planilha.write_bytes(b"conteudo")
    info = planilha.stat()
    manifesto = {"versao": 1, "arquivos": {str(planilha.resolve()): {
        "tamanho": info.st_size,
        "modificado_ns": info.st_mtime_ns,
        "bases": ["vendas", "implantacao"],
        "bases_sem_registros": ["termos"],
        "versoes_bases": {"vendas": 2, "implantacao": 2, "termos": 1},
    }}}

    # Implantacao também está pendente porque a versão mudou de 2 para 8
    assert tipos_pendentes(
        planilha.resolve(), {"vendas", "implantacao", "termos"}, manifesto
    ) == {"implantacao", "termos"}
    # Atualizando termos de 1 para 8 e implantacao de 2 para 8
    manifesto["arquivos"][str(planilha.resolve())]["versoes_bases"]["termos"] = 8
    manifesto["arquivos"][str(planilha.resolve())]["versoes_bases"]["implantacao"] = 8
    assert tipos_pendentes(
        planilha.resolve(), {"vendas", "implantacao", "termos"}, manifesto
    ) == set()


def test_mudanca_das_medidas_reprocessa_venda_e_implantacao(tmp_path):
    planilha = tmp_path / "interior.xlsx"
    planilha.write_bytes(b"conteudo")
    info = planilha.stat()
    manifesto = {"versao": 1, "arquivos": {str(planilha.resolve()): {
        "tamanho": info.st_size,
        "modificado_ns": info.st_mtime_ns,
        "bases": ["vendas", "implantacao"],
        "versoes_bases": {"vendas": 1, "implantacao": 1},
    }}}

    assert tipos_pendentes(
        planilha.resolve(), {"vendas", "implantacao"}, manifesto
    ) == {"vendas", "implantacao"}
    manifesto["arquivos"][str(planilha.resolve())]["versoes_bases"].update({
        "vendas": 2,
        "implantacao": 2,
    })
    # Implantacao ainda está pendente porque espera versão 8 agora
    assert tipos_pendentes(
        planilha.resolve(), {"vendas", "implantacao"}, manifesto
    ) == {"implantacao"}
    # Atualizar para versão 8
    manifesto["arquivos"][str(planilha.resolve())]["versoes_bases"]["implantacao"] = 8
    assert tipos_pendentes(
        planilha.resolve(), {"vendas", "implantacao"}, manifesto
    ) == set()


def test_arquivo_sem_registro_para_uma_base_nao_e_relido_eternamente(tmp_path, monkeypatch):
    pasta = tmp_path / "Interior"
    pasta.mkdir()
    planilha = pasta / "atividades.xlsx"
    planilha.write_bytes(b"conteudo")
    configuracao = tmp_path / "pastas.txt"
    configuracao.write_text(f"{pasta} = vendas\n", encoding="utf-8")
    manifesto_path = tmp_path / "manifesto.json"

    @contextmanager
    def banco_falso():
        yield object()

    resultado = SimpleNamespace(
        ok=False, dataset="vendas", titulo_dataset="Venda", status="ERRO",
        inseridos=0, atualizados=0, mensagem="Nenhum registro aplicável.",
    )
    monkeypatch.setattr(atualizador, "sessao", banco_falso)
    monkeypatch.setattr(atualizador, "criar_banco", lambda: None)
    monkeypatch.setattr(atualizador, "detectar_tipos", lambda *_: ["vendas"])
    monkeypatch.setattr(atualizador, "processar_arquivo", lambda *_, **__: resultado)
    monkeypatch.setattr(atualizador.cache, "invalidar", lambda: None)
    monkeypatch.setattr(atualizador, "invalidar_cache_do_painel", lambda: None)

    assert atualizador.executar(configuracao, manifesto_path) == 0
    manifesto = carregar_manifesto(manifesto_path)
    registro = manifesto["arquivos"][str(planilha.resolve())]
    assert registro["status"] == "processado_com_avisos"
    assert registro["bases_sem_registros"] == ["vendas"]
    assert not arquivo_mudou(planilha.resolve(), manifesto)
