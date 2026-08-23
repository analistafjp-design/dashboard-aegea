"""Garantias da interface operacional simplificada."""
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def test_menu_principal_tem_apenas_as_tres_telas_de_uso_diario(cliente, base_carregada):
    pagina = cliente.get("/").text

    assert "Venda e Implantação" in pagina
    assert "Termos Aplicados" in pagina
    assert "Programação Diária" in pagina
    assert 'data-chave="atualizacao"' not in pagina
    assert 'data-chave="alertas"' not in pagina
    assert 'data-chave="analises"' not in pagina


def test_home_reproduz_estrutura_enxuta_da_referencia(cliente, base_carregada):
    pagina = cliente.get("/").text

    assert "ACOMPANHAMENTO VENDA E IMPLANTAÇÃO" in pagina
    assert "simples-implantacao-kpis" in pagina
    assert "simples-vendas-kpis" in pagina
    assert "graf-simples-impl-servicos" in pagina
    assert "graf-simples-venda-cidade" in pagina
    assert "graf-simples-venda-equipe" in pagina
    assert "graf-simples-impl-cidade" in pagina
    assert "graf-simples-tendencia" not in pagina


def test_termos_e_programacao_priorizam_indicadores_operacionais(cliente, base_carregada):
    termos = cliente.get("/termos").text
    programacao = cliente.get("/programacao").text

    assert "ACOMPANHAMENTO DE TERMOS APLICADOS" in termos
    assert "graf-termos-diario" in termos
    assert "graf-termos-total-meta" in termos
    assert "graf-termos-cidade" in termos
    assert "graf-termos-equipe" in termos
    assert "termos-insights" in termos
    assert "Leitura Gerencial por Cidade" in termos
    assert "PROGRAMAÇÃO DIÁRIA" in programacao
    assert "programacao-recadastro" in programacao
    assert "programacao-vendas" in programacao


def test_graficos_exibem_quantidade_alem_do_percentual():
    javascript = (RAIZ / "frontend" / "static" / "js" / "graficos.js").read_text(
        encoding="utf-8"
    )

    assert 'textinfo: "value+percent"' in javascript
    assert 'texttemplate: "<b>%{value:,.0f}</b><br>%{percent}"' in javascript
    assert 'text: valores.slice().reverse().map(rotuloValor)' in javascript
    assert "Graficos.anelMeta" in javascript
    assert "Graficos.barraMeta" in javascript
    assert 'shape: "bullet"' in javascript
    assert 'name: "Total"' in javascript
    assert "ticklabelstandoff: 12" in javascript
    assert "annotations: rotulos.map" in javascript


def test_interface_oferece_exportacao_por_aba_e_geral(cliente, base_carregada):
    pagina = cliente.get("/").text

    assert 'data-exportar="atual" data-formato="pdf"' in pagina
    assert 'data-exportar="atual" data-formato="xlsx"' in pagina
    assert 'data-exportar="geral" data-formato="pdf"' in pagina
    assert 'data-exportar="geral" data-formato="xlsx"' in pagina


def test_interface_tem_navegacao_acessivel_e_layout_responsivo(cliente, base_carregada):
    pagina = cliente.get("/").text
    estilos = (RAIZ / "frontend" / "static" / "css" / "tema.css").read_text(
        encoding="utf-8"
    )

    assert 'class="pular-conteudo"' in pagina
    assert 'aria-label="Navegacao principal"' in pagina
    assert 'aria-current="page"' in pagina
    assert "@media (max-width: 680px)" in estilos
    assert "@media (max-width: 420px)" in estilos
    assert "prefers-reduced-motion" in estilos
    assert "overflow-x: auto" in estilos
