from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
SCRIPTS = RAIZ / "scripts"


def _texto(nome: str) -> str:
    return (SCRIPTS / nome).read_text(encoding="utf-8")


def test_botao_chama_apenas_fluxo_manual():
    botao = _texto("ATUALIZAR_DASHBOARD.cmd")
    executor = _texto("executar_atualizacao_manual.ps1")

    assert "executar_atualizacao_manual.ps1" in botao
    assert "sincronizar_pastas.ps1" in executor
    assert "Start-Process $Url" in executor
    assert "ScheduledTask" not in botao + executor
    assert "instalar_agendamento" not in botao + executor


def test_configurador_mapeia_as_quatro_pastas_do_onedrive():
    configurador = _texto("configurar_atalho.ps1")

    assert "Atendimento') = atendimento" in configurador
    assert "Faturamento') = faturamento" in configurador
    assert "Interior') = vendas, implantacao, termos" in configurador
    assert 'Filter "OneDrive*"' in configurador
    assert 'Name -like "Programa*Di*ria"' in configurador
    assert '"$PastaProgramacao = programacao"' in configurador
    assert "CreateShortcut" in configurador
    assert "Register-ScheduledTask" not in configurador


def test_sincronizador_aceita_atendimento_e_url_configuravel():
    sincronizador = _texto("sincronizar_pastas.ps1")

    assert '"atendimento")' in sincronizador
    assert "URL\\s*=\\s*(.*)" in sincronizador
