"""API JSON consumida pelo frontend."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from app.analytics import alertas as mod_alertas
from app.analytics import cache, consultas, insights as mod_insights, metas as mod_metas, painel
from app.analytics.base import Filtros
from app.analytics.periodo import resolver
from app.config import config
from app.etl.datasets import DATASETS
from app.etl.leitura import estimar_linhas_arquivo
from app.etl.pipeline import ETAPAS, processar_lote
from app.models.db import sessao
from app.schemas.filtros import filtros_da_query
from app.services import configuracoes as servico_config
from app.services import exportacao as servico_exportacao
from app.services import upload as servico_upload
from app.utils.erros import ErroDashboard
from app.utils.formato import data_hora_br, numero
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


@router.post("/upload")
async def upload(arquivos: list[UploadFile] = File(...),
                 tipo: list[str] | None = Form(None)) -> JSONResponse:
    """Recebe os arquivos, processa e devolve o relatório de cada um."""
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
            erros.append({"arquivo": arquivo.filename, "status": "ERRO",
                          "mensagem": erro.mensagem, "detalhes": erro.detalhes})

    resultados: list[dict] = []
    if salvos:
        # Cada arquivo sozinho já é validado dentro de `processar_arquivo`
        # (ver app/etl/leitura.py), mas um LOTE de vários arquivos pequenos
        # processados na mesma requisição soma memória do mesmo jeito — por
        # isso o total do lote também é checado ANTES de processar
        # qualquer um, mesmo que nenhum arquivo isolado ultrapasse o limite.
        total_estimado = sum(estimar_linhas_arquivo(c) for c in salvos)
        if total_estimado > config.LIMITE_LINHAS_ARQUIVO:
            for caminho in salvos:
                caminho.unlink(missing_ok=True)
            mensagem = (
                f"Os {len(salvos)} arquivos somam aproximadamente {numero(total_estimado)} "
                f"linhas juntos — acima do limite de {numero(config.LIMITE_LINHAS_ARQUIVO)} "
                "linhas que esta instância suporta processar de uma vez, mesmo com cada "
                "arquivo sendo pequeno sozinho. Envie em lotes menores (menos arquivos por vez)."
            )
            logger.warning("Lote de upload recusado: %s arquivo(s), %s linhas estimadas",
                           len(salvos), total_estimado)
            erro_lote = [{"arquivo": c.name, "status": "ERRO", "mensagem": mensagem,
                         "detalhes": [], "dataset": None, "titulo_dataset": None, "lidos": 0,
                         "inseridos": 0, "atualizados": 0, "descartados": 0, "validacao": None,
                         "confianca_deteccao": None, "campos_detectados": [],
                         "qualidade_dados": None} for c in salvos]
            return JSONResponse(content={
                "ok": False, "mensagem": mensagem,
                "resultados": erro_lote + erros, "status": status(),
            })

        try:
            with sessao() as s:
                resultados = [r.to_dict() for r in processar_lote(s, salvos, forcados)]
        except Exception:  # noqa: BLE001 - erro de banco vira mensagem amigável
            logger.exception("Falha ao processar lote de upload")
            return JSONResponse(status_code=500, content={
                "ok": False,
                "mensagem": "Não foi possível concluir a atualização. "
                            "O erro foi registrado no log do sistema.",
            })
        cache.invalidar()

    todos_resultados = resultados + erros
    houve_sucesso = any(r["status"] in ("SUCESSO", "ATENCAO") for r in todos_resultados)
    return JSONResponse(content={
        "ok": houve_sucesso,
        "mensagem": _mensagem_lote(todos_resultados),
        "resultados": todos_resultados,
        "status": status(),
    })


def _mensagem_lote(resultados: list[dict]) -> str:
    if not resultados:
        return "Nenhum arquivo processado."
    sucessos = [r for r in resultados if r["status"] in ("SUCESSO", "ATENCAO")]
    falhas = [r for r in resultados if r["status"] == "ERRO"]
    registros = sum(r.get("inseridos", 0) + r.get("atualizados", 0) for r in sucessos)
    if sucessos and not falhas:
        return f"Dashboard atualizado: {registros} registro(s) de {len(sucessos)} arquivo(s)."
    if sucessos and falhas:
        return (f"{len(sucessos)} arquivo(s) importado(s) ({registros} registros) e "
                f"{len(falhas)} com problema.")
    return f"Nenhum arquivo pôde ser importado ({len(falhas)} com problema)."


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
    if nome == "home":
        dados = painel.home(filtros)
        return {
            "Indicadores": [
                {"Indicador": c["titulo"], "Valor": c["texto"],
                 "Comparação": c["texto_variacao"], "Status": c["rotulo_status"]}
                for c in dados["cards"]
            ],
            "Modulos": dados["modulos"],
            "Insights": [{"Tipo": i["tipo"], "Insight": i["texto"]} for i in dados["insights"]],
            "Alertas": [{"Categoria": a["categoria"], "Titulo": a["titulo"],
                         "Descricao": a["descricao"]} for a in dados["alertas"]],
        }, "Visao Executiva"

    if nome == "historico":
        return {"Historico": historico(500)["registros"]}, "Historico de Atualizacoes"

    if nome not in MODULOS_VALIDOS:
        raise ErroDashboard(f"Não é possível exportar '{nome}'.")

    dados = painel.modulo("equipes", filtros, base=base) if nome == "equipes" \
        else painel.modulo(nome, filtros)
    tabelas: dict[str, list[dict]] = {}
    if dados.get("indicadores"):
        tabelas["Indicadores"] = [
            {"Indicador": i["titulo"], "Valor": i["texto"], "Meta": i["meta"],
             "Comparação": i["texto_variacao"], "Status": i["rotulo_status"]}
            for i in dados["indicadores"]
        ]
    for chave in ("blocos_meta", "tabela", "agenda", "evolucao_mensal", "evolucao_diaria",
                  "por_cidade", "por_equipe", "por_frente", "por_setor", "por_status",
                  "por_regiao", "por_projeto", "funil", "ranking", "abaixo_da_meta"):
        valor = dados.get(chave)
        if isinstance(valor, list) and valor:
            tabelas[chave[:31]] = valor
    return tabelas, dados.get("titulo", nome.title())
