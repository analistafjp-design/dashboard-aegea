"""API JSON consumida pelo frontend."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from app.analytics import alertas as mod_alertas
from app.analytics import cache, consultas, insights as mod_insights, metas as mod_metas, painel
from app.analytics.base import Filtros
from app.analytics.periodo import resolver
from app.config import config
from app.etl.datasets import DATASETS
from app.etl.pipeline import ETAPAS
from app.schemas.filtros import filtros_da_query
from app.services import configuracoes as servico_config
from app.services import exportacao as servico_exportacao
from app.services import processamento as servico_processamento
from app.services import upload as servico_upload
from app.utils.erros import ErroDashboard
from app.utils.formato import data_hora_br
from app.utils.log import get_logger

logger = get_logger("api")
router = APIRouter(prefix="/api", tags=["api"])

MODULOS_VALIDOS = ("termos", "faturamento", "vendas", "implantacao",
                   "programacao", "cidades", "equipes")


@router.get("/status")
def status() -> dict:
    ultima = consultas.ultima_atualizacao()
    return {
        "aplicacao": config.APP_NOME,
        "versao": config.APP_VERSAO,
        "tem_dados": consultas.ha_dados(),
        "ultima_atualizacao": data_hora_br(ultima) if ultima is not None else None,
        "cache": cache.estatisticas(),
        "metas_cadastradas": mod_metas.tem_metas(),
    }


@router.post("/local/invalidar-cache")
def invalidar_cache_local(request: Request) -> dict:
    """Atualiza um painel ja aberto depois da carga feita no mesmo computador."""
    cliente = request.client.host if request.client else ""
    if cliente not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="Disponivel somente no computador local.")
    cache.invalidar()
    return {"ok": True}


@router.get("/filtros/opcoes")
def opcoes_filtros() -> dict:
    return painel.opcoes_filtros()


@router.get("/home")
def home(filtros: Filtros = Depends(filtros_da_query)) -> dict:
    return painel.home(filtros)


@router.get("/modulo/{nome}")
def modulo(nome: str, filtros: Filtros = Depends(filtros_da_query),
           base: str = Query("implantacao")) -> dict:
    if nome not in MODULOS_VALIDOS:
        raise HTTPException(status_code=404, detail=f"Módulo '{nome}' não existe.")
    if nome == "equipes":
        return painel.modulo("equipes", filtros, base=base)
    return painel.modulo(nome, filtros)


@router.get("/insights")
def insights(filtros: Filtros = Depends(filtros_da_query)) -> dict:
    payloads = painel.todos(filtros)
    return {"insights": mod_insights.gerar(payloads),
            "periodo": resolver(filtros).to_dict()}


@router.get("/alertas")
def alertas(filtros: Filtros = Depends(filtros_da_query)) -> dict:
    lista = mod_alertas.gerar(painel.todos(filtros))
    return {"alertas": lista, "resumo": mod_alertas.resumo(lista),
            "periodo": resolver(filtros).to_dict()}


@router.get("/metas")
def metas(filtros: Filtros = Depends(filtros_da_query)) -> dict:
    periodo = resolver(filtros)
    payloads = painel.todos(filtros, periodo)
    tabela = mod_metas.metas_do_periodo(periodo.ano).to_dict("records")
    return {
        "periodo": periodo.to_dict(),
        "tem_metas": mod_metas.tem_metas(),
        "cadastradas": tabela,
        "acompanhamento": [
            {**payloads[chave]["bloco_principal"], "modulo": rotulo}
            for chave, rotulo in (("termos", "Termos"), ("vendas", "Venda"),
                                  ("implantacao", "Implantação"))
        ],
    }


@router.get("/historico")
def historico(limite: int = Query(50, ge=1, le=500)) -> dict:
    df = consultas.historico_uploads(limite)
    if df.empty:
        return {"registros": []}
    df = df.copy()
    df["data_hora"] = df["data_hora"].map(lambda v: data_hora_br(v))
    return {"registros": df.to_dict("records")}


@router.get("/datasets")
def datasets() -> dict:
    """Dicionário de dados: bases, colunas aceitas e regras."""
    return {
        "datasets": [
            {
                "nome": d.nome, "titulo": d.titulo, "modulo": d.modulo,
                "tabela": d.tabela, "descricao": d.descricao,
                "chave_unica": list(d.chave_unica),
                "campos": [
                    {"nome": c.nome, "tipo": c.tipo, "descricao": c.descricao,
                     "obrigatorio": c.obrigatorio, "aliases": list(c.aliases)}
                    for c in d.campos
                ],
            }
            for d in DATASETS.values()
        ]
    }


@router.get("/configuracoes")
def ler_configuracoes() -> dict:
    return {"configuracoes": servico_config.ler_todas(), "opcoes": servico_config.OPCOES}


@router.post("/configuracoes")
def salvar_configuracoes(dados: dict) -> dict:
    return {"ok": True, "configuracoes": servico_config.salvar(dados or {})}


@router.get("/etapas")
def etapas() -> dict:
    return {"etapas": list(ETAPAS)}


def _resultado_erro(arquivo: str, mensagem: str, detalhes: list[str] | None = None) -> dict:
    """Resultado no mesmo formato de `ResultadoArquivo.to_dict()`, para a tela
    conseguir exibir erro e sucesso pela mesma estrutura."""
    return {
        "arquivo": arquivo, "status": "ERRO", "mensagem": mensagem,
        "detalhes": detalhes or [], "dataset": None, "titulo_dataset": None,
        "lidos": 0, "inseridos": 0, "atualizados": 0, "descartados": 0,
        "validacao": None, "confianca_deteccao": None, "campos_detectados": [],
        "qualidade_dados": None,
    }


@router.post("/upload")
async def upload(arquivos: list[UploadFile] = File(...),
                 tipo: list[str] | None = Form(None)) -> JSONResponse:
    """Recebe os arquivos e AGENDA o processamento, devolvendo na hora.

    O processamento em si é síncrono e pesado (pandas/openpyxl/SQLAlchemy):
    fazê-lo aqui dentro travaria o event loop e, com ele, todas as outras
    requisições — inclusive o health check do Render, que então reinicia a
    instância no meio do upload. Por isso a rota só grava os arquivos em
    disco (rápido, em streaming) e devolve um `trabalho_id`; a tela
    acompanha o andamento em `GET /api/upload/{trabalho_id}`.
    """
    if not arquivos:
        return JSONResponse(status_code=400,
                            content={"ok": False, "mensagem": "Nenhum arquivo enviado."})

    salvos: list[Path] = []
    forcados: dict[str, str] = {}
    erros: list[dict] = []

    for indice, arquivo in enumerate(arquivos):
        try:
            caminho = await servico_upload.salvar(arquivo)
            salvos.append(caminho)
            escolhido = tipo[indice] if tipo and indice < len(tipo) else None
            if escolhido and escolhido in DATASETS:
                forcados[caminho.name] = escolhido
        except ErroDashboard as erro:
            erros.append(_resultado_erro(arquivo.filename or "arquivo",
                                         erro.mensagem, erro.detalhes))

    if not salvos:
        return JSONResponse(content={
            "ok": False, "concluido": True,
            "mensagem": servico_processamento.resumo_do_lote(erros),
            "resultados": erros, "status": status(),
        })

    # Não há mais trava por total de linhas do lote: os arquivos são
    # processados um a um, cada um com a própria sessão de banco, e um
    # arquivo grande demais para caber na memória é lido em blocos (ver
    # app/etl/pipeline._processar_em_blocos). O consumo de memória, portanto,
    # não depende nem da quantidade de arquivos nem do tamanho deles.
    trabalho = servico_processamento.agendar(salvos, forcados, erros_iniciais=erros)
    return JSONResponse(status_code=202, content={
        "ok": True, "concluido": False,
        "mensagem": f"Processando {len(salvos)} arquivo(s)...",
        **trabalho.to_dict(),
    })


@router.get("/upload/{trabalho_id}")
def progresso_upload(trabalho_id: str) -> JSONResponse:
    """Andamento de um upload agendado — consultado pela tela em intervalos."""
    trabalho = servico_processamento.obter(trabalho_id)
    if trabalho is None:
        raise HTTPException(
            status_code=404,
            detail="Esta atualização não está mais disponível para consulta. "
                   "Recarregue a página e confira o histórico abaixo.",
        )
    concluido = trabalho.status != servico_processamento.PROCESSANDO
    corpo = {
        **trabalho.to_dict(),
        "concluido": concluido,
        "ok": concluido and any(
            r.get("status") in ("SUCESSO", "ATENCAO") for r in trabalho.resultados),
    }
    if concluido:
        corpo["status_app"] = status()
    return JSONResponse(content=corpo)


@router.get("/exportar/{nome}")
def exportar(nome: str, formato: str = Query("xlsx"),
             filtros: Filtros = Depends(filtros_da_query),
             base: str = Query("implantacao")) -> Response:
    periodo = resolver(filtros)
    try:
        tabelas, titulo = _tabelas_para_exportar(nome, filtros, base)
        subtitulo = f"Período: {periodo.rotulo}" + (
            " | " + " | ".join(filtros.descricao()) if filtros.ativo else "")
        conteudo, arquivo, mime = servico_exportacao.exportar(
            tabelas, formato, titulo, subtitulo)
    except ErroDashboard as erro:
        raise HTTPException(status_code=400, detail=erro.mensagem) from erro

    return Response(content=conteudo, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{arquivo}"'
    })


def _tabelas_para_exportar(nome: str, filtros: Filtros, base: str) -> tuple[dict, str]:
    if nome in {"home", "geral"}:
        home = painel.home(filtros)
        vendas = painel.modulo("vendas", filtros)
        implantacao = painel.modulo("implantacao", filtros)
        tabelas = {
            "Resumo Geral": _linhas_indicadores(home.get("cards", [])),
            "Venda Indicadores": _linhas_indicadores(vendas.get("indicadores", [])),
            "Venda por Cidade": vendas.get("top_cidades", []),
            "Venda por Equipe": vendas.get("top_equipes", []),
            "Dados Venda": _dados_detalhados("vendas", filtros),
            "Implantacao Indicadores": _linhas_indicadores(
                implantacao.get("indicadores", [])),
            "Implantacao por Cidade": implantacao.get("por_cidade", []),
            "Dados Implantacao": _dados_detalhados("implantacao", filtros),
        }
        if nome == "home":
            return tabelas, "Venda e Implantacao"

        termos = painel.modulo("termos", filtros)
        tabelas.update({
            "Termos Indicadores": _linhas_indicadores(termos.get("indicadores", [])),
            "Termos Diario": termos.get("evolucao_diaria_tipo", []),
            "Termos por Cidade": termos.get("por_cidade_tipo", []),
            "Termos por Equipe": termos.get("por_equipe_tipo", []),
            "Dados Termos": _dados_detalhados("termos", filtros),
        })
        return tabelas, "Dashboard Executivo Geral"

    if nome == "historico":
        return {"Historico": historico(500)["registros"]}, "Historico de Atualizacoes"

    if nome not in MODULOS_VALIDOS:
        raise ErroDashboard(f"Não é possível exportar '{nome}'.")

    dados = painel.modulo("equipes", filtros, base=base) if nome == "equipes" \
        else painel.modulo(nome, filtros)
    tabelas: dict[str, list[dict]] = {}
    if dados.get("indicadores"):
        tabelas["Indicadores"] = _linhas_indicadores(dados["indicadores"])
    if nome in {"vendas", "implantacao", "termos"}:
        tabelas["Dados Detalhados"] = _dados_detalhados(nome, filtros)
    for chave in ("blocos_meta", "tabela", "agenda", "evolucao_mensal", "evolucao_diaria",
                  "evolucao_diaria_tipo", "por_cidade", "por_cidade_tipo",
                  "por_equipe", "por_equipe_tipo", "por_frente", "por_setor", "por_status",
                  "por_regiao", "por_projeto", "funil", "ranking", "abaixo_da_meta"):
        valor = dados.get(chave)
        if isinstance(valor, list) and valor:
            tabelas[chave[:31]] = valor
    return tabelas, dados.get("titulo", nome.title())


def _linhas_indicadores(indicadores: list[dict]) -> list[dict]:
    """Padroniza os cartões do painel para os relatórios PDF e Excel."""
    return [
        {
            "Indicador": item.get("titulo", ""),
            "Valor": item.get("texto", item.get("valor")),
            "Meta": item.get("meta"),
            "Comparação": item.get("texto_variacao", ""),
            "Status": item.get("rotulo_status", item.get("status", "")),
        }
        for item in indicadores
    ]


COLUNAS_DETALHADAS = {
    "data": "Data",
    "ano_mes": "Ano/Mês",
    "cidade": "Cidade",
    "equipe": "Equipe/Recurso",
    "frente": "Frente",
    "setor": "Setor do Recurso",
    "canal": "Canal",
    "tipo": "Tipo",
    "codigo_contado": "Código Contado",
    "status_termo": "Status do Termo",
    "matricula": "Matrícula",
    "servico": "Serviço",
    "faturado": "Faturado",
    "quantidade": "Quantidade",
    "valor": "Valor",
    "origem_arquivo": "Arquivo de Origem",
    "importado_em": "Importado em",
}


def _dados_detalhados(nome: str, filtros: Filtros) -> list[dict]:
    """Linhas contabilizadas pelas medidas, em estrutura próxima da origem.

    Os painéis somam ``quantidade``. Portanto, uma ocorrência com quantidade
    zero é apenas contexto operacional e não pode aparecer no Excel como se
    fizesse parte do realizado. Aplicar a mesma regra aqui evita divergência
    entre cartões, gráficos e arquivo baixado.
    """
    dados = consultas.dados(nome, filtros)
    if dados.empty:
        return []
    # Os cartoes e graficos sempre trabalham com um unico mes de referencia:
    # o mes filtrado ou, quando a tela esta em "Todos", o mes mais recente da
    # base. O Excel deve usar exatamente o mesmo recorte para que o total das
    # linhas detalhadas seja igual ao realizado exibido no painel.
    if nome in {"termos", "vendas", "implantacao"} and "ano_mes" in dados.columns:
        periodo = resolver(filtros)
        dados = dados[dados["ano_mes"] == periodo.ano_mes].copy()
    if nome in {"termos", "vendas", "implantacao"} and "quantidade" in dados.columns:
        quantidade = pd.to_numeric(dados["quantidade"], errors="coerce").fillna(0)
        dados = dados[quantidade > 0].copy()
    if dados.empty:
        return []
    if nome == "termos" and "tipo" in dados.columns:
        dados["codigo_contado"] = dados["tipo"].map({
            "SERVICOS": "110013 ou 210013",
            "VCG": "310013",
        })
    colunas = [coluna for coluna in COLUNAS_DETALHADAS if coluna in dados.columns]
    detalhes = dados[colunas].rename(columns=COLUNAS_DETALHADAS)
    if "Data" in detalhes.columns:
        detalhes = detalhes.sort_values("Data", ascending=False)
    return detalhes.to_dict("records")
