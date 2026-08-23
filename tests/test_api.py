"""Testes de ponta a ponta da API e das páginas HTML."""
import asyncio
import base64
import io
import time

import pandas as pd
from starlette.datastructures import UploadFile

from app.config import config
from app.services.upload import nome_exibicao, salvar

PAGINAS = ["/", "/termos", "/faturamento", "/vendas", "/implantacao", "/programacao",
           "/equipes", "/cidades", "/metas", "/analises", "/alertas", "/atualizacao",
           "/configuracoes", "/dicionario"]

MODULOS = ["termos", "faturamento", "vendas", "implantacao", "programacao",
           "cidades", "equipes"]


def test_todas_as_paginas_respondem(cliente, base_carregada):
    for rota in PAGINAS:
        resposta = cliente.get(rota)
        assert resposta.status_code == 200, rota
        assert "text/html" in resposta.headers["content-type"]


def test_pagina_em_modo_fragmento_nao_repete_o_layout(cliente):
    inteira = cliente.get("/vendas").text
    fragmento = cliente.get("/vendas?fragmento=1").text
    assert "<!DOCTYPE html>" in inteira
    assert "<!DOCTYPE html>" not in fragmento
    assert "conteudo-pagina" in fragmento


def test_status_reflete_a_base(cliente, base_carregada):
    dados = cliente.get("/api/status").json()
    assert dados["tem_dados"] is True
    assert dados["metas_cadastradas"] is True
    assert dados["ultima_atualizacao"]


def test_modulos_respondem_com_estrutura_esperada(cliente, base_carregada):
    """Cidades entrega ranking/tabela; os demais módulos entregam indicadores."""
    for nome in MODULOS:
        dados = cliente.get(f"/api/modulo/{nome}?ano=2026&mes=8").json()
        assert "periodo" in dados, nome
        assert dados["periodo"]["ano_mes"] == "2026-08"
        assert dados["titulo"], nome
        if nome == "cidades":
            assert dados["tabela"], nome
        else:
            assert dados["indicadores"], nome


def test_modulo_inexistente_devolve_404(cliente):
    assert cliente.get("/api/modulo/inexistente").status_code == 404


def test_filtros_invalidos_sao_recusados(cliente):
    assert cliente.get("/api/home?mes=13").status_code == 422
    assert cliente.get("/api/home?ano=1800").status_code == 422


def test_opcoes_de_filtro_vem_dos_dados(cliente, base_carregada):
    opcoes = cliente.get("/api/filtros/opcoes").json()
    assert 2026 in opcoes["anos"]
    assert "Maricá" in opcoes["cidades"]
    assert "Região A" in opcoes["regioes"]
    assert "Não Informado" not in opcoes["cidades"]


def enviar_e_aguardar(cliente, **kwargs) -> dict:
    """POST /api/upload + espera o processamento em segundo plano terminar.

    O upload é assíncrono: a rota devolve 202 com um `trabalho_id` e o
    processamento roda numa thread (para não travar o event loop). Os
    testes acompanham o mesmo caminho que a tela usa.
    """
    resposta = cliente.post("/api/upload", **kwargs)
    dados = resposta.json()
    if dados.get("concluido", True) or not dados.get("trabalho_id"):
        return dados

    for _ in range(200):  # ~20s de teto, muito acima do necessário nos testes
        estado = cliente.get(f"/api/upload/{dados['trabalho_id']}").json()
        if estado["concluido"]:
            return estado
        time.sleep(0.1)
    raise AssertionError("Processamento em segundo plano não terminou a tempo")


def test_upload_processa_planilha(cliente, planilhas):
    with planilhas["vendas"].open("rb") as arquivo:
        dados = enviar_e_aguardar(
            cliente, files={"arquivos": ("venda.xlsx", arquivo.read())})
    assert dados["ok"] is True
    assert dados["resultados"][0]["dataset"] == "vendas"
    assert dados["resultados"][0]["inseridos"] > 0
    assert not list(config.UPLOAD_DIR.iterdir()), "upload temporário não foi removido"


def test_uploads_de_mesmo_nome_nao_se_sobrescrevem():
    primeiro = UploadFile(io.BytesIO(b"primeiro"), filename="venda.xlsx")
    segundo = UploadFile(io.BytesIO(b"segundo"), filename="venda.xlsx")

    caminho_1 = asyncio.run(salvar(primeiro))
    caminho_2 = asyncio.run(salvar(segundo))
    try:
        assert caminho_1 != caminho_2
        assert caminho_1.read_bytes() == b"primeiro"
        assert caminho_2.read_bytes() == b"segundo"
        assert nome_exibicao(caminho_1.name) == "venda.xlsx"
        assert nome_exibicao(caminho_2.name) == "venda.xlsx"
    finally:
        caminho_1.unlink(missing_ok=True)
        caminho_2.unlink(missing_ok=True)


def test_upload_responde_na_hora_sem_travar_o_servidor(cliente, planilhas):
    """A rota não pode processar dentro da requisição: isso travaria o event
    loop e, com ele, o health check que o Render usa para decidir se a
    instância está viva (era a causa do upload 'travado' + 502)."""
    with planilhas["vendas"].open("rb") as arquivo:
        resposta = cliente.post("/api/upload",
                                files={"arquivos": ("venda.xlsx", arquivo.read())})
    assert resposta.status_code == 202
    corpo = resposta.json()
    assert corpo["concluido"] is False
    assert corpo["trabalho_id"]
    # O servidor continua atendendo normalmente enquanto o lote processa.
    assert cliente.get("/api/status").status_code == 200

    for _ in range(200):  # deixa o trabalho terminar antes do teardown do banco
        if cliente.get(f"/api/upload/{corpo['trabalho_id']}").json()["concluido"]:
            break
        time.sleep(0.1)


def test_progresso_de_trabalho_inexistente_da_404(cliente):
    resposta = cliente.get("/api/upload/naoexiste123")
    assert resposta.status_code == 404
    assert "Traceback" not in resposta.text


def test_upload_de_arquivo_invalido_devolve_mensagem_amigavel(cliente):
    dados = enviar_e_aguardar(
        cliente, files={"arquivos": ("virus.exe", b"MZ conteudo binario")})
    assert dados["ok"] is False
    assert "não é aceito" in dados["resultados"][0]["mensagem"]


def test_upload_com_tipo_forcado(cliente, planilhas):
    with planilhas["implantacao"].open("rb") as arquivo:
        dados = enviar_e_aguardar(
            cliente,
            files={"arquivos": ("qualquer_nome.xlsx", arquivo.read())},
            data={"tipo": "implantacao"},
        )
    assert dados["resultados"][0]["dataset"] == "implantacao"


def test_lote_cuja_soma_passa_do_limite_ainda_e_processado(cliente, planilhas, monkeypatch):
    """Vários arquivos que somados passam do limite NÃO são recusados: eles
    são processados um a um (cada um com sua sessão), e os que passam do
    limite sozinhos são lidos em blocos. O consumo de memória não depende
    da quantidade de arquivos, então não há motivo para recusar o lote."""
    # A planilha de vendas de teste tem 77 linhas — uma sozinha fica dentro
    # do limite, três juntas (231) passariam dele.
    monkeypatch.setattr(config, "LIMITE_LINHAS_ARQUIVO", 150)
    with planilhas["vendas"].open("rb") as a:
        conteudo = a.read()

    dados = enviar_e_aguardar(cliente, files=[
        ("arquivos", ("venda1.xlsx", conteudo)),
        ("arquivos", ("venda2.xlsx", conteudo)),
        ("arquivos", ("venda3.xlsx", conteudo)),
    ])

    assert dados["ok"] is True, dados["mensagem"]
    assert len(dados["resultados"]) == 3
    assert all(r["status"] in ("SUCESSO", "ATENCAO") for r in dados["resultados"])
    assert cliente.get("/api/status").json()["tem_dados"] is True


def test_historico_lista_importacoes(cliente, base_carregada):
    registros = cliente.get("/api/historico").json()["registros"]
    assert len(registros) >= 6
    assert all("data_hora" in r for r in registros)


def test_exportacao_nos_tres_formatos(cliente, base_carregada):
    for formato, assinatura in (("xlsx", b"PK"), ("csv", None), ("pdf", b"%PDF")):
        resposta = cliente.get(f"/api/exportar/home?formato={formato}")
        assert resposta.status_code == 200, formato
        assert "attachment" in resposta.headers["content-disposition"]
        if assinatura:
            assert resposta.content.startswith(assinatura)

    excel = cliente.get("/api/exportar/vendas?formato=xlsx&ano=2026&mes=8")
    abas = pd.read_excel(io.BytesIO(excel.content), sheet_name=None)
    assert "Indicadores" in abas
    assert (abas["Dados Detalhados"]["Quantidade"] > 0).all()

    excel_termos = cliente.get("/api/exportar/termos?formato=xlsx&ano=2026&mes=8")
    abas_termos = pd.read_excel(io.BytesIO(excel_termos.content), sheet_name=None)
    detalhes_termos = abas_termos["Dados Detalhados"]
    assert (detalhes_termos["Quantidade"] > 0).all()
    assert set(detalhes_termos["Código Contado"].astype(str)) == {
        "110013 ou 210013", "310013"
    }

    # Mesmo com os filtros em "Todos", a exportacao deve repetir o mes de
    # referencia usado pelo painel, e nao somar meses anteriores.
    excel_termos_todos = cliente.get("/api/exportar/termos?formato=xlsx")
    detalhes_todos = pd.read_excel(
        io.BytesIO(excel_termos_todos.content), sheet_name="Dados Detalhados"
    )
    painel_termos = cliente.get("/api/modulo/termos").json()
    assert detalhes_todos["Quantidade"].sum() == painel_termos["bloco_principal"]["realizado"]
    assert set(pd.to_datetime(detalhes_todos["Data"]).dt.to_period("M").astype(str)) == {"2026-08"}

    geral = cliente.get("/api/exportar/geral?formato=xlsx&ano=2026&mes=8")
    assert geral.status_code == 200
    abas_gerais = pd.read_excel(io.BytesIO(geral.content), sheet_name=None)
    assert {"Resumo Geral", "Venda por Cidade", "Dados Venda",
            "Dados Implantacao", "Termos Diario", "Dados Termos"}.issubset(abas_gerais)
    assert "Programacao Agenda" not in abas_gerais
    assert {"Data", "Cidade", "Equipe/Recurso", "Arquivo de Origem"}.issubset(
        abas_gerais["Dados Implantacao"].columns)
    assert {"Data", "Tipo", "Status do Termo", "Arquivo de Origem"}.issubset(
        abas_gerais["Dados Termos"].columns)
    assert (abas_gerais["Dados Termos"]["Quantidade"] > 0).all()

    pdf_geral = cliente.get("/api/exportar/geral?formato=pdf&ano=2026&mes=8")
    assert pdf_geral.status_code == 200
    assert pdf_geral.content.startswith(b"%PDF")


def test_exportacao_em_formato_invalido(cliente, base_carregada):
    assert cliente.get("/api/exportar/home?formato=docx").status_code == 400


def test_dicionario_de_dados_documenta_todas_as_bases(cliente):
    datasets = cliente.get("/api/datasets").json()["datasets"]
    assert {d["nome"] for d in datasets} == {
        "termos", "faturamento", "vendas", "implantacao", "programacao", "metas",
        "atendimento", "faturamento_implantacao"}
    for dataset in datasets:
        assert dataset["descricao"]
        assert dataset["chave_unica"]
        for campo in dataset["campos"]:
            assert campo["descricao"], f"{dataset['nome']}.{campo['nome']} sem descrição"


def test_configuracoes_salvam_e_recusam_valor_invalido(cliente):
    cliente.post("/api/configuracoes", json={"tema": "escuro", "linhas_tabela": "50"})
    atual = cliente.get("/api/configuracoes").json()["configuracoes"]
    assert atual["tema"] == "escuro"
    assert atual["linhas_tabela"] == "50"

    cliente.post("/api/configuracoes", json={"tema": "roxo_neon"})
    assert cliente.get("/api/configuracoes").json()["configuracoes"]["tema"] == "escuro"


def test_alertas_e_insights_respondem(cliente, base_carregada):
    alertas = cliente.get("/api/alertas?ano=2026&mes=8").json()
    assert alertas["resumo"]["total"] == len(alertas["alertas"])
    insights = cliente.get("/api/insights?ano=2026&mes=8").json()
    assert isinstance(insights["insights"], list)


def test_metas_expoem_acompanhamento(cliente, base_carregada):
    dados = cliente.get("/api/metas?ano=2026&mes=8").json()
    assert dados["tem_metas"] is True
    assert {linha["modulo"] for linha in dados["acompanhamento"]} == {
        "Termos", "Venda", "Implantação"}


def test_banco_vazio_nao_quebra_nenhuma_rota(cliente):
    for rota in PAGINAS:
        assert cliente.get(rota).status_code == 200, rota
    for nome in MODULOS:
        assert cliente.get(f"/api/modulo/{nome}").status_code == 200, nome
    assert cliente.get("/api/home").json()["tem_dados"] is False


# ---------------------------------------------------------- autenticação
def _cabecalho_basic(usuario: str, senha: str) -> dict[str, str]:
    valor = base64.b64encode(f"{usuario}:{senha}".encode()).decode()
    return {"Authorization": f"Basic {valor}"}


def test_sem_credenciais_configuradas_nao_pede_login(cliente):
    """Padrão de desenvolvimento local: sem AUTH_USUARIO/AUTH_SENHA, sem login."""
    assert config.AUTENTICACAO_ATIVA is False
    assert cliente.get("/").status_code == 200
    assert cliente.get("/api/status").status_code == 200


def test_com_credenciais_configuradas_exige_login(cliente, monkeypatch):
    monkeypatch.setattr(config, "AUTH_USUARIO", "admin")
    monkeypatch.setattr(config, "AUTH_SENHA", "segredo123")
    assert config.AUTENTICACAO_ATIVA is True

    sem_credencial = cliente.get("/")
    assert sem_credencial.status_code == 401
    assert "Basic" in sem_credencial.headers["www-authenticate"]

    credencial_errada = cliente.get("/", headers=_cabecalho_basic("admin", "errada"))
    assert credencial_errada.status_code == 401

    credencial_certa = cliente.get("/", headers=_cabecalho_basic("admin", "segredo123"))
    assert credencial_certa.status_code == 200


def test_status_continua_publico_mesmo_com_login_ativo(cliente, monkeypatch):
    """O healthcheck do Render precisa responder sem credenciais."""
    monkeypatch.setattr(config, "AUTH_USUARIO", "admin")
    monkeypatch.setattr(config, "AUTH_SENHA", "segredo123")

    resposta = cliente.get("/api/status")
    assert resposta.status_code == 200
    assert resposta.json()["aplicacao"]


def test_upload_exige_login_quando_ativo(cliente, monkeypatch):
    monkeypatch.setattr(config, "AUTH_USUARIO", "admin")
    monkeypatch.setattr(config, "AUTH_SENHA", "segredo123")

    assert cliente.post("/api/upload").status_code == 401
