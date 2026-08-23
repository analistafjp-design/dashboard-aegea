import pandas as pd

from app.etl import regras_powerbi as regras


def test_venda_comercial_e_vcg_reproduzem_filtros_dax():
    base = pd.DataFrame([
        {"tipo_atividade": "Venda Potenciais/Factíveis", "status_atividade": "Finalizada",
         "codigo_descricao": "VENDA NORMAL", "equipe": "RIOVENIN-001"},
        {"tipo_atividade": "Venda Potenciais/Factíveis", "status_atividade": "Finalizada",
         "codigo_descricao": "VENDA NORMAL", "equipe": "RIOVCGEXTIN-001"},
        {"tipo_atividade": "Venda Potenciais/Factíveis", "status_atividade": "Finalizada",
         "codigo_descricao": "114003 - NAO CONTA", "equipe": "RIOVCGEXTIN-001"},
        {"tipo_atividade": "Venda Potenciais/Factíveis", "status_atividade": "Finalizada",
         "codigo_descricao": "118048 - NAO CONTA COMERCIAL", "equipe": "RIOVENIN-001"},
        {"tipo_atividade": "Venda Potenciais/Factíveis", "status_atividade": "Iniciada",
         "codigo_descricao": "VENDA NORMAL", "equipe": "RIOVENIN-001"},
    ])
    resultado = regras.filtrar_vendas(base)
    assert list(resultado["canal"]) == ["COMERCIAL", "VCG"]
    assert list(resultado["quantidade"]) == [1.0, 1.0]


def test_implantacao_exige_ligacao_de_agua_finalizada_e_classifica_frente():
    base = pd.DataFrame([
        {"tipo_atividade": "Ligação de Água", "status_atividade": "Finalizada",
         "equipe": "RIOMLTIN-001"},
        {"tipo_atividade": "Ligação de Água", "status_atividade": "Finalizada",
         "equipe": "RIOVCGPOPIN-001"},
        {"tipo_atividade": "Ligação de Água", "status_atividade": "Iniciada",
         "equipe": "RIOMLTIN-002"},
    ])
    resultado = regras.filtrar_implantacoes(base)
    assert list(resultado["tipo"]) == ["SERVICOS", "VCG"]
    assert list(resultado["frente"]) == ["Serviços", "VCG Bairro Legal - SFI"]


def test_termos_reproduzem_codigos_status_e_equipe_das_medidas():
    base = pd.DataFrame([
        {"servico_adicional": "110013 - irregularidade", "status_atividade": "Finalizada",
         "equipe": "RIORECIN-001"},
        {"servico_adicional": "310013 - irregularidade", "status_atividade": "Encerrada com Ocorrência",
         "equipe": "RIOVCGEXTIN-001"},
        {"servico_adicional": "310013 - irregularidade", "status_atividade": "Finalizada",
         "equipe": "RIORECIN-002"},
    ])
    resultado = regras.filtrar_termos(base)
    assert list(resultado["tipo"]) == ["SERVICOS", "VCG"]


def test_programacao_usa_mapas_de_equipe_regiao_e_projeto_do_pbix():
    base = pd.DataFrame([
        {"recurso": "RIORECIN-024", "codigo_descricao": "102002-VERIFICAÇÃO CADASTRAL (VISTORIA CAMPO)",
         "observacao": "qualquer"},
        {"recurso": "RIOIEGTIN-001", "codigo_descricao": "OUTRO",
         "observacao": "projeto esgoto: atividade"},
        {"recurso": "EQUIPE-FORA-DO-MAPA", "codigo_descricao": "OUTRO", "observacao": "x:y"},
    ])
    resultado = regras.filtrar_programacao(base)
    assert list(resultado["equipe_geral"]) == ["LUCIANO-024", "OBRAS ESGOTO-001"]
    assert list(resultado["regiao"]) == ["SERRANA", "NOROESTE"]
    assert list(resultado["projeto"]) == ["Impacta Cliente", "Projeto esgoto"]


def test_faturamento_implantacao_classifica_frente_e_valor_como_no_pbix():
    base = pd.DataFrame([
        {"departamento": "VEM COM A GENTE", "valor": 100.0},
        {"departamento": "IMPLANTAÇÃO DE LIGAÇÃO ÁGUA", "valor": 0.0},
        {"departamento": "OUTRO", "valor": None},
    ])
    resultado = regras.preparar_faturamento_implantacao(base)
    assert list(resultado["frente"]) == ["VCG", "Serviços", "Outros"]
    assert list(resultado["faturado"]) == [True, False, False]
