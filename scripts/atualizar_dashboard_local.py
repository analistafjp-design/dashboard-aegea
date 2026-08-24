#!/usr/bin/env python3
"""Atualiza o banco local somente com planilhas novas ou alteradas.

Este e o fluxo usado pelo botao do Windows. As planilhas permanecem no
OneDrive, o banco SQLite permanece no computador e nenhum arquivo e enviado
para o Render ou para outro servidor.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROJETO))

from app.analytics import cache  # noqa: E402
from app.config import config  # noqa: E402
from app.etl.datasets import DATASETS, ORDEM_CARGA  # noqa: E402
from app.etl.deteccao import PONTUACAO_MINIMA, identificar  # noqa: E402
from app.etl.leitura import ler_planilhas  # noqa: E402
from app.etl.pipeline import processar_arquivo  # noqa: E402
from app.models.db import criar_banco, sessao  # noqa: E402
from app.models.tabelas import FatoImplantacao, FatoTermos, FatoVendas  # noqa: E402

EXTENSOES = {".xlsx", ".xlsm", ".xls", ".csv"}
TIPOS_VALIDOS = set(DATASETS)
# Versões das medidas oficiais do Power BI. A alteração de uma versão força
# somente uma releitura daquela base, removendo antes a contribuição antiga
# do mesmo arquivo. Depois da correção, o fluxo volta a ser incremental.
VERSOES_REGRAS = {tipo: 1 for tipo in TIPOS_VALIDOS} | {
    "termos": 8,
    "vendas": 2,
    "implantacao": 5,
}

FATOS_SUBSTITUIDOS_POR_ARQUIVO = {
    "termos": FatoTermos,
    "vendas": FatoVendas,
    "implantacao": FatoImplantacao,
}


@dataclass(frozen=True)
class PastaMonitorada:
    caminho: Path
    tipos: tuple[str, ...]


def carregar_pastas(caminho: Path) -> list[PastaMonitorada]:
    """Le o mesmo arquivo de configuracao criado por CONFIGURAR_ATALHO."""
    entradas: list[PastaMonitorada] = []
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        texto = linha.strip()
        if not texto or texto.startswith("#"):
            continue
        partes = texto.rsplit("=", 1)
        pasta = Path(partes[0].strip().strip('"'))
        tipos: tuple[str, ...] = ()
        if len(partes) == 2:
            tipos = tuple(
                tipo.strip().lower()
                for tipo in partes[1].split(",")
                if tipo.strip().lower() in TIPOS_VALIDOS
            )
        # Migra automaticamente a configuração antiga: a pasta Faturamento
        # pode conter tanto a base de Termos quanto a de Venda/Implantação.
        if pasta.name.casefold() == "faturamento" and tipos == ("faturamento",):
            tipos = ("faturamento", "faturamento_implantacao")
        entradas.append(PastaMonitorada(pasta, tipos))
    return entradas


def encontrar_arquivos(entradas: list[PastaMonitorada]) -> dict[Path, set[str]]:
    """Retorna cada arquivo fisico uma unica vez e seus tipos permitidos."""
    encontrados: dict[Path, set[str]] = {}
    for entrada in entradas:
        if not entrada.caminho.exists():
            print(f"AVISO  Pasta nao encontrada: {entrada.caminho}")
            continue
        candidatos = (
            entrada.caminho.rglob("*")
            if entrada.caminho.is_dir()
            else [entrada.caminho]
        )
        for arquivo in candidatos:
            if (
                not arquivo.is_file()
                or arquivo.name.startswith("~$")
                or arquivo.suffix.lower() not in EXTENSOES
            ):
                continue
            resolvido = arquivo.resolve()
            encontrados.setdefault(resolvido, set()).update(entrada.tipos)
    return encontrados


def assinatura(caminho: Path) -> dict[str, int]:
    info = caminho.stat()
    return {"tamanho": info.st_size, "modificado_ns": info.st_mtime_ns}


def carregar_manifesto(caminho: Path) -> dict:
    if not caminho.exists():
        return {"versao": 1, "arquivos": {}}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if isinstance(dados.get("arquivos"), dict):
            return dados
    except (OSError, ValueError, TypeError):
        pass
    print("AVISO  O catalogo local estava ilegivel e sera recriado.")
    return {"versao": 1, "arquivos": {}}


def salvar_manifesto(caminho: Path, manifesto: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporario.replace(caminho)


def arquivo_mudou(caminho: Path, manifesto: dict) -> bool:
    anterior = manifesto["arquivos"].get(str(caminho))
    return anterior is None or any(
        anterior.get(chave) != valor for chave, valor in assinatura(caminho).items()
    )


def tipos_pendentes(caminho: Path, permitidos: set[str], manifesto: dict,
                    completo: bool = False) -> set[str] | None:
    """Bases que realmente precisam ser verificadas para este arquivo.

    Arquivo novo/alterado: verifica os tipos configurados normalmente.
    Arquivo inalterado: verifica apenas a base cuja regra mudou de versão.
    """
    if completo or arquivo_mudou(caminho, manifesto):
        # None preserva a detecção automática das configurações sem tipo.
        return set(permitidos) or None
    anterior = manifesto["arquivos"].get(str(caminho), {})
    versoes = anterior.get("versoes_bases", {})
    return {
        tipo for tipo in permitidos
        if int(versoes.get(tipo, 1)) < VERSOES_REGRAS.get(tipo, 1)
    }


def detectar_tipos(caminho: Path, permitidos: set[str]) -> list[str | None]:
    """Evita processar um arquivo de Interior tres vezes sem necessidade.

    Uma pasta com um unico tipo e confiavel e nao precisa de deteccao. Quando
    ha varios tipos permitidos, cada aba e avaliada e somente as bases realmente
    compativeis sao processadas.
    """
    if len(permitidos) == 1:
        return [next(iter(permitidos))]
    if not permitidos:
        return [None]

    planilhas = ler_planilhas(caminho)
    detectados: list[str] = []
    for tipo in sorted(permitidos, key=lambda item: ORDEM_CARGA.index(item)):
        resultado = identificar(planilhas, caminho.name, tipo)
        if resultado.compativel and resultado.pontuacao >= PONTUACAO_MINIMA:
            detectados.append(tipo)
    return detectados


def invalidar_cache_do_painel() -> None:
    """Avisa um painel local que ja esteja aberto; falhar aqui nao e erro."""
    requisicao = urllib.request.Request(
        "http://127.0.0.1:8000/api/local/invalidar-cache", method="POST"
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=2):  # noqa: S310 - loopback fixo
            pass
    except Exception:  # noqa: BLE001 - o servidor pode ainda nao estar iniciado
        return


def executar(pastas_arquivo: Path, manifesto_arquivo: Path, completo: bool = False) -> int:
    entradas = carregar_pastas(pastas_arquivo)
    if not entradas:
        print("ERRO   Nenhuma pasta foi configurada.")
        return 1

    arquivos = encontrar_arquivos(entradas)
    if not arquivos:
        print("ERRO   Nenhuma planilha foi encontrada nas pastas configuradas.")
        return 1

    manifesto = carregar_manifesto(manifesto_arquivo)
    pendentes = {
        caminho: tipos_pendentes(caminho, permitidos, manifesto, completo)
        for caminho, permitidos in arquivos.items()
    }
    pendentes = {
        caminho: tipos for caminho, tipos in pendentes.items()
        if tipos is None or tipos
    }
    pulados = len(arquivos) - len(pendentes)

    print(f"Encontradas {len(arquivos)} planilha(s) fisica(s).")
    if pulados:
        print(f"Ignoradas {pulados} sem alteracao desde o ultimo clique.")
    if not pendentes:
        print("Dashboard ja esta atualizado. Nenhum arquivo precisou ser relido.")
        invalidar_cache_do_painel()
        return 0

    revisoes_termos = sum(
        1 for tipos in pendentes.values()
        if tipos == {"termos"}
    )
    if revisoes_termos:
        print(
            f"Aplicando a correcao de Termos em {revisoes_termos} planilha(s), "
            "sem recarregar Venda, Implantacao ou Programacao."
        )
    print(f"Processando {len(pendentes)} planilha(s) que realmente precisam de atualizacao.")
    criar_banco()
    falhas = 0
    concluidos = 0
    com_avisos = 0

    for indice, caminho in enumerate(sorted(pendentes), start=1):
        print(f"[{indice}/{len(pendentes)}] {caminho.name}")
        try:
            tipos = detectar_tipos(caminho, pendentes[caminho] or set())
        except Exception as erro:  # noqa: BLE001 - mostra falha e segue as demais
            print(f"  ERRO ao analisar: {erro}")
            falhas += 1
            continue

        if not tipos:
            print("  Ignorada: nenhuma aba compativel com as bases desta pasta.")
            anterior = manifesto["arquivos"].get(str(caminho), {})
            manifesto["arquivos"][str(caminho)] = {
                **anterior, **assinatura(caminho), "status": "ignorado",
                "versoes_bases": {
                    **anterior.get("versoes_bases", {}),
                    **{
                        tipo: VERSOES_REGRAS[tipo]
                        for tipo in (pendentes[caminho] or set())
                    },
                },
            }
            salvar_manifesto(manifesto_arquivo, manifesto)
            continue

        resultados = []
        for tipo in tipos:
            with sessao() as banco:
                ja_processado = str(caminho) in manifesto["arquivos"]
                if ja_processado and tipo in FATOS_SUBSTITUIDOS_POR_ARQUIVO:
                    # Substitui somente a contribuição desta base e arquivo.
                    # Assim, linhas que deixaram de atender às medidas saem do
                    # banco. Uma falha provoca rollback e preserva o anterior.
                    fato = FATOS_SUBSTITUIDOS_POR_ARQUIVO[tipo]
                    banco.execute(
                        delete(fato).where(fato.origem_arquivo == caminho.name)
                    )
                resultado = processar_arquivo(
                    banco, caminho, dataset_forcado=tipo,
                    usuario="atalho-local", arquivar=False,
                )
            resultados.append(resultado)
            rotulo = resultado.titulo_dataset or tipo or "nao identificada"
            print(
                f"  {rotulo}: {resultado.status} - "
                f"{resultado.inseridos} novo(s), {resultado.atualizados} atualizado(s)"
            )
            if not resultado.ok:
                print(f"    {resultado.mensagem}")

        if resultados:
            anterior = manifesto["arquivos"].get(str(caminho), {})
            bases_ok = [resultado.dataset for resultado in resultados if resultado.ok]
            bases_ignoradas = [
                resultado.dataset or tipo
                for resultado, tipo in zip(resultados, tipos)
                if not resultado.ok
            ]
            # Um arquivo bruto do Interior pode ter a estrutura das três
            # bases, mas não possuir linhas que atendam a todas as medidas.
            # Ele foi verificado e não deve ser relido até realmente mudar.
            status = "processado" if not bases_ignoradas else "processado_com_avisos"
            manifesto["arquivos"][str(caminho)] = {
                **assinatura(caminho),
                "bases": sorted(set(anterior.get("bases", [])) | set(bases_ok)),
                "bases_sem_registros": sorted(
                    (set(anterior.get("bases_sem_registros", [])) - set(bases_ok))
                    | set(bases_ignoradas)
                ),
                "status": status,
                "versoes_bases": {
                    **anterior.get("versoes_bases", {}),
                    **{
                        (resultado.dataset or tipo): VERSOES_REGRAS.get(
                            resultado.dataset or tipo, 1
                        )
                        for resultado, tipo in zip(resultados, tipos)
                    },
                },
            }
            salvar_manifesto(manifesto_arquivo, manifesto)
            concluidos += 1
            if bases_ignoradas:
                com_avisos += 1

    cache.invalidar()
    invalidar_cache_do_painel()
    print()
    print(
        f"Concluido: {concluidos} arquivo(s); "
        f"com avisos: {com_avisos}; falhas de leitura: {falhas}."
    )
    return 2 if falhas else 0


def main() -> int:
    padrao_manifesto = config.DATA_DIR / "local" / "manifesto_atualizacao.json"
    parser = argparse.ArgumentParser(description="Atualiza o Dashboard AEGEA local")
    parser.add_argument(
        "--pastas", type=Path,
        default=Path(__file__).resolve().parent / "pastas-monitoradas.txt",
    )
    parser.add_argument("--manifesto", type=Path, default=padrao_manifesto)
    parser.add_argument("--completo", action="store_true")
    argumentos = parser.parse_args()
    if not argumentos.pastas.exists():
        print(f"ERRO   Configuracao nao encontrada: {argumentos.pastas}")
        return 1
    return executar(argumentos.pastas, argumentos.manifesto, argumentos.completo)


if __name__ == "__main__":
    raise SystemExit(main())
