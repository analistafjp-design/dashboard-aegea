from pathlib import Path

import yaml


RAIZ = Path(__file__).resolve().parent.parent


def test_blueprint_de_producao_aponta_para_main_e_expoe_configuracoes_criticas():
    blueprint = yaml.safe_load((RAIZ / "render.yaml").read_text(encoding="utf-8"))
    servico = blueprint["services"][0]

    assert servico["branch"] == "main"
    assert servico["healthCheckPath"] == "/api/status"
    variaveis = {item["key"]: item for item in servico["envVars"]}
    assert variaveis["AUTH_USUARIO"]["sync"] is False
    assert variaveis["AUTH_SENHA"]["sync"] is False
    assert variaveis["LINHAS_POR_BLOCO"]["value"] == "20000"

