"""Normalização, conversão e validação dos dados lidos da planilha.

Saída: um DataFrame padronizado (colunas internas) + um relatório de
validação legível pelo usuário. Nada é convertido para zero para "não dar
erro": linha inválida é descartada e contabilizada.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.etl import dominio, regras_atendimento, regras_powerbi
from app.etl.datasets import Dataset
from app.etl.deteccao import Identificacao
from app.etl.tipos import CONVERSORES, esta_vazio
from app.utils.erros import ErroValidacaoArquivo
from app.utils.log import get_logger
from app.utils.texto import titulo

logger = get_logger("etl.transformacao")

MAX_EXEMPLOS = 25

# Sugestão exibida ao usuário para cada tipo de problema (regra 23: mostrar
# arquivo, linha, coluna, valor, problema e sugestão — nunca só um erro
# técnico).
SUGESTOES_TIPO = {
    "data": "Use uma data reconhecível, como 21/08/2026 ou 2026-08-21.",
    "numero": "Use apenas números — separador de milhar com ponto e decimal com "
              "vírgula (ex.: 1.234,56), sem letras nem símbolos além de R$ e %.",
    "inteiro": "Use um número inteiro, sem texto (ex.: 12).",
    "booleano": "Use um valor como Sim/Não, Faturado/Não Faturado ou 1/0.",
}
SUGESTAO_OBRIGATORIO = "Preencha esta coluna neste registro — ela é obrigatória para a base {titulo}."


@dataclass
class RelatorioValidacao:
    dataset: str
    aba: str
    titulo: str = ""
    linhas_lidas: int = 0
    linhas_validas: int = 0
    linhas_descartadas: int = 0
    duplicadas_no_arquivo: int = 0
    problemas: dict[str, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    colunas_mapeadas: dict[str, str] = field(default_factory=dict)
    colunas_ignoradas: list[str] = field(default_factory=list)
    colunas_ausentes: list[str] = field(default_factory=list)
    exemplos: list[dict] = field(default_factory=list)
    exemplos_omitidos: int = 0

    def registrar_problema(self, descricao: str) -> None:
        self.problemas[descricao] = self.problemas.get(descricao, 0) + 1

    def registrar_exemplo(self, *, linha: int, campo: str, coluna_original: str | None,
                          valor: object, problema: str, tipo_problema: str) -> None:
        """Guarda um exemplo concreto (linha/coluna/valor) para a tela de upload.

        Limitado a `MAX_EXEMPLOS` para não estourar a resposta em arquivos com
        milhares de linhas problemáticas — o restante continua contabilizado
        em `problemas`, só não aparece como exemplo individual.
        """
        if len(self.exemplos) >= MAX_EXEMPLOS:
            self.exemplos_omitidos += 1
            return
        sugestao = SUGESTOES_TIPO.get(tipo_problema, "Corrija o valor e envie o arquivo novamente.")
        if tipo_problema == "obrigatorio":
            sugestao = SUGESTAO_OBRIGATORIO.format(titulo=self.titulo or self.dataset)
        texto_valor = "(vazio)" if valor is None or (isinstance(valor, str) and not valor.strip()) \
            else str(valor)[:120]
        self.exemplos.append({
            "linha": linha,
            "campo": campo,
            "coluna_original": coluna_original or campo,
            "valor": texto_valor,
            "problema": problema,
            "sugestao": sugestao,
        })

    @property
    def status(self) -> str:
        if self.linhas_validas == 0:
            return "ERRO"
        if self.linhas_descartadas or self.problemas:
            return "ATENCAO"
        return "SUCESSO"

    @property
    def qualidade_dados(self) -> float | None:
        """% de linhas lidas que entraram válidas — indicador da regra 24."""
        if self.linhas_lidas == 0:
            return None
        return round(self.linhas_validas / self.linhas_lidas * 100, 1)

    def mensagens(self) -> list[str]:
        saida = [f"{qtd} {descricao}" for descricao, qtd in sorted(
            self.problemas.items(), key=lambda item: item[1], reverse=True)]
        saida.extend(self.avisos)
        return saida

    def resumo(self) -> str:
        base = (f"{self.linhas_validas} de {self.linhas_lidas} registros válidos "
                f"na aba '{self.aba}'")
        mensagens = self.mensagens()
        return f"{base}. " + "; ".join(mensagens) if mensagens else base + "."

    def somar(self, outro: "RelatorioValidacao") -> None:
        """Incorpora o relatório de outro bloco do mesmo arquivo.

        Usado na leitura em blocos (arquivos grandes): cada bloco produz um
        relatório e o do arquivo é a soma de todos. Só `duplicadas_no_arquivo`
        é parcial — a checagem de duplicidade acontece dentro de cada bloco,
        não entre blocos. Isso não gera registro duplicado no banco: a carga
        é feita por chave única, então uma repetição entre blocos vira
        atualização, não inserção.
        """
        self.linhas_lidas += outro.linhas_lidas
        self.linhas_validas += outro.linhas_validas
        self.linhas_descartadas += outro.linhas_descartadas
        self.duplicadas_no_arquivo += outro.duplicadas_no_arquivo
        for descricao, quantidade in outro.problemas.items():
            self.problemas[descricao] = self.problemas.get(descricao, 0) + quantidade
        for aviso in outro.avisos:
            if aviso not in self.avisos:
                self.avisos.append(aviso)
        self.colunas_mapeadas.update(outro.colunas_mapeadas)
        for lista, novos in ((self.colunas_ignoradas, outro.colunas_ignoradas),
                             (self.colunas_ausentes, outro.colunas_ausentes)):
            for item in novos:
                if item not in lista:
                    lista.append(item)
        for exemplo in outro.exemplos:
            if len(self.exemplos) < MAX_EXEMPLOS:
                self.exemplos.append(exemplo)
            else:
                self.exemplos_omitidos += 1
        self.exemplos_omitidos += outro.exemplos_omitidos

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "aba": self.aba,
            "linhas_lidas": self.linhas_lidas,
            "linhas_validas": self.linhas_validas,
            "linhas_descartadas": self.linhas_descartadas,
            "duplicadas_no_arquivo": self.duplicadas_no_arquivo,
            "qualidade_dados": self.qualidade_dados,
            "problemas": self.problemas,
            "avisos": self.avisos,
            "colunas_mapeadas": self.colunas_mapeadas,
            "colunas_ignoradas": self.colunas_ignoradas,
            "colunas_ausentes": self.colunas_ausentes,
            "exemplos": self.exemplos,
            "exemplos_omitidos": self.exemplos_omitidos,
            "status": self.status,
            "resumo": self.resumo(),
        }


def _rotulo(campo: str) -> str:
    return campo.replace("_", " ")


def transformar(identificacao: Identificacao,
                permitir_vazio: bool = False) -> tuple[pd.DataFrame, RelatorioValidacao]:
    """Converte a planilha no DataFrame padronizado.

    `permitir_vazio` é usado na leitura em blocos: um bloco sem nenhuma
    linha aproveitável é normal (a base Atendimento, por exemplo, aprova
    poucas linhas entre centenas de milhares) e não pode abortar o arquivo
    inteiro — quem decide se o arquivo como um todo ficou vazio é o
    pipeline, depois de somar todos os blocos.
    """
    dataset = identificacao.dataset
    if dataset is None:
        raise ErroValidacaoArquivo(
            "Arquivo incompatível: não foi possível reconhecer o tipo de base pelas "
            "colunas encontradas.",
            [f"Colunas lidas: {', '.join(map(str, identificacao.planilha.dados.columns[:15]))}"],
        )
    if identificacao.faltantes:
        faltando = ", ".join(f"'{_rotulo(c)}'" for c in identificacao.faltantes)
        raise ErroValidacaoArquivo(
            f"Arquivo incompatível com a base {dataset.titulo}. "
            f"A(s) coluna(s) {faltando} não foi(ram) encontrada(s).",
            [f"Colunas do arquivo: {', '.join(map(str, identificacao.planilha.dados.columns[:20]))}"],
        )

    # As planilhas consolidadas de Venda trazem Canal/Frente; a exportação
    # bruta do PBIX traz Tipo de Atividade e permite derivar a frente. Sem
    # nenhuma das duas estruturas o arquivo não pode ser classificado.
    if (dataset.nome == "vendas"
            and "frente" not in identificacao.mapeamento
            and "tipo_atividade" not in identificacao.mapeamento):
        raise ErroValidacaoArquivo(
            "Arquivo incompatível com a base Venda. A(s) coluna(s) 'frente' ou "
            "'tipo de atividade' não foi(ram) encontrada(s).",
            ["Informe Canal/Frente ou use a exportação Field Service com Tipo de Atividade."],
        )

    origem = identificacao.planilha.dados
    relatorio = RelatorioValidacao(
        dataset=dataset.nome,
        aba=identificacao.planilha.nome,
        titulo=dataset.titulo,
        linhas_lidas=len(origem),
        colunas_mapeadas=dict(identificacao.mapeamento),
        colunas_ignoradas=identificacao.colunas_ignoradas,
        colunas_ausentes=[c.nome for c in dataset.campos if c.nome not in identificacao.mapeamento],
    )
    if relatorio.colunas_ausentes:
        relatorio.avisos.append(
            "colunas opcionais ausentes: " + ", ".join(map(_rotulo, relatorio.colunas_ausentes))
        )

    linhas: list[dict] = []
    for indice_planilha, linha_bruta in origem.iterrows():
        # O índice do pandas é 0-based e preserva a posição original da linha
        # na aba (ver leitura._limpar): +1 dá exatamente o número da linha
        # como o usuário vê no Excel.
        numero_linha = int(indice_planilha) + 1
        registro: dict = {}
        descartar = False

        for campo in dataset.campos:
            coluna = identificacao.mapeamento.get(campo.nome)
            bruto = linha_bruta[coluna] if coluna is not None else None
            if coluna is None or esta_vazio(bruto):
                if campo.obrigatorio and campo.padrao is None:
                    relatorio.registrar_problema(
                        f"registro(s) sem '{_rotulo(campo.nome)}' (descartado)")
                    relatorio.registrar_exemplo(
                        linha=numero_linha, campo=_rotulo(campo.nome), coluna_original=coluna,
                        valor=bruto, problema=f"Coluna '{_rotulo(campo.nome)}' vazia",
                        tipo_problema="obrigatorio")
                    descartar = True
                    break
                registro[campo.nome] = campo.padrao
                continue

            valor, ok = CONVERSORES[campo.tipo](bruto)
            if not ok:
                tipo_legivel = {"data": "data inválida", "numero": "número inválido",
                                "inteiro": "número inválido",
                                "booleano": "valor Sim/Não inválido"}.get(
                                    campo.tipo, "valor inválido")
                relatorio.registrar_problema(
                    f"registro(s) com {tipo_legivel} em '{_rotulo(campo.nome)}'"
                    + (" (descartado)" if campo.obrigatorio else " (campo ignorado)")
                )
                relatorio.registrar_exemplo(
                    linha=numero_linha, campo=_rotulo(campo.nome), coluna_original=coluna,
                    valor=bruto, problema=tipo_legivel.capitalize(), tipo_problema=campo.tipo)
                if campo.obrigatorio:
                    descartar = True
                    break
                registro[campo.nome] = campo.padrao
                continue

            if valor is None and campo.obrigatorio:
                relatorio.registrar_problema(
                    f"registro(s) sem '{_rotulo(campo.nome)}' (descartado)")
                relatorio.registrar_exemplo(
                    linha=numero_linha, campo=_rotulo(campo.nome), coluna_original=coluna,
                    valor=bruto, problema=f"Coluna '{_rotulo(campo.nome)}' vazia",
                    tipo_problema="obrigatorio")
                descartar = True
                break
            registro[campo.nome] = valor if valor is not None else campo.padrao

        if descartar:
            relatorio.linhas_descartadas += 1
            continue
        linhas.append(registro)

    if not linhas:
        if not permitir_vazio:
            raise ErroValidacaoArquivo(
                f"Nenhum registro válido foi encontrado na base {dataset.titulo}.",
                relatorio.mensagens(),
            )
        return pd.DataFrame(), relatorio

    dados = pd.DataFrame(linhas)
    dados = _derivar(dataset, dados)

    # Atendimento: só as linhas que a medida "Vendas Outros Canais" contaria
    # entram como venda. O que fica de fora é contabilizado com o motivo,
    # para o número não vir menor sem explicação.
    if dataset.nome == "atendimento":
        antes = len(dados)
        dados, motivos = regras_atendimento.filtrar(dados)
        for descricao, quantidade in motivos.items():
            relatorio.problemas[descricao] = \
                relatorio.problemas.get(descricao, 0) + quantidade
        if antes and not len(dados) and not permitir_vazio:
            raise ErroValidacaoArquivo(
                f"Nenhuma linha do arquivo se enquadra na regra de Vendas por "
                f"Outros Canais (das {antes} linhas lidas).",
                relatorio.mensagens(),
            )

    if not dados.empty:
        dados = _remover_duplicadas(dataset, dados, relatorio)

    relatorio.linhas_validas = len(dados)
    logger.info("Transformação %s: %s", dataset.nome, relatorio.resumo())
    return dados, relatorio


def _derivar(dataset: Dataset, dados: pd.DataFrame) -> pd.DataFrame:
    """Colunas calculadas a partir das colunas lidas."""
    if "data" in dados.columns:
        dados["ano_mes"] = dados["data"].map(lambda d: f"{d.year:04d}-{d.month:02d}")
        dados["ano"] = dados["data"].map(lambda d: d.year)
        dados["mes"] = dados["data"].map(lambda d: d.month)

    # Transcreve as condições dos PBIX quando a entrada é uma exportação
    # bruta do Field Service. Planilhas consolidadas não são alteradas.
    dados = regras_powerbi.aplicar(dataset.nome, dados)

    for coluna in ("cidade", "equipe", "regiao", "projeto", "setor", "recurso"):
        if coluna in dados.columns:
            dados[coluna] = dados[coluna].map(lambda v: titulo(v) or None)

    if "frente" in dados.columns:
        dados["frente"] = dados["frente"].map(dominio.normalizar_frente)

    if dataset.nome == "vendas":
        # A regra PBIX de Venda Comercial x VCG já grava `canal`; somente
        # planilhas consolidadas precisam derivá-lo a partir de `frente`.
        if "canal" not in dados.columns:
            dados["canal"] = dados["frente"].map(dominio.canal_venda)

    if dataset.nome == "atendimento":
        # Toda linha desta base é, por definição da medida, uma venda por
        # Outros Canais — e cada linha vale 1 (a medida usa COUNTROWS).
        dados["frente"] = dominio.OUTROS_CANAIS
        dados["canal"] = dominio.CANAL_OUTROS
        dados["quantidade"] = 1.0

    if dataset.nome in ("termos", "implantacao"):
        colunas_tipo = [c for c in ("tipo", "frente", "servico") if c in dados.columns]
        dados["tipo"] = dados.apply(
            lambda linha: dominio.classificar_tipo(*[linha[c] for c in colunas_tipo]), axis=1
        )

    if dataset.nome == "termos" and "status_termo" in dados.columns:
        dados["status_termo"] = dados["status_termo"].map(dominio.normalizar_status_termo)

    if dataset.nome == "faturamento":
        dados["situacao"] = dados["situacao"].map(dominio.normalizar_situacao_faturamento)
        dados["inicio_mes"] = dados["data"].map(lambda d: d.replace(day=1))

    if dataset.nome == "implantacao":
        # "faturado" ausente é diferente de "não faturado": mantém-se False, mas o
        # relatório avisa para que o indicador não seja lido como certeza.
        if "faturado" not in dados.columns:
            dados["faturado"] = False
        dados["faturado"] = dados["faturado"].map(lambda v: bool(v) if v is not None else False)

    if dataset.nome == "metas":
        dados["modulo"] = dados["modulo"].map(dominio.normalizar_modulo_meta)
        dados["segmento"] = dados["segmento"].map(dominio.normalizar_segmento_meta)

    if "quantidade" in dados.columns:
        dados["quantidade"] = dados["quantidade"].fillna(1.0)
    if "qtd_os" in dados.columns:
        dados["qtd_os"] = dados["qtd_os"].fillna(1.0)
    return dados


def montar_chave(dataset: Dataset, linha: pd.Series) -> str:
    partes = []
    for campo in dataset.chave_unica:
        valor = linha.get(campo)
        partes.append("" if valor is None or (isinstance(valor, float) and pd.isna(valor))
                      else str(valor).strip().lower())
    return "|".join([dataset.nome, *partes])


def _remover_duplicadas(dataset: Dataset, dados: pd.DataFrame,
                        relatorio: RelatorioValidacao) -> pd.DataFrame:
    """Aplica a chave única do dataset; a última ocorrência prevalece."""
    dados = dados.copy()
    dados["chave_unica"] = dados.apply(lambda linha: montar_chave(dataset, linha), axis=1)
    duplicadas = int(dados["chave_unica"].duplicated().sum())
    if duplicadas:
        relatorio.duplicadas_no_arquivo = duplicadas
        if dataset.nome == "termos":
            # As medidas oficiais de Termos no PBIX usam COUNTROWS. Portanto,
            # duas linhas fisicas iguais continuam valendo dois termos. Como o
            # banco precisa de uma chave unica para a carga incremental, elas
            # ficam em um unico fato com quantidade somada.
            dados["quantidade"] = pd.to_numeric(
                dados["quantidade"], errors="coerce"
            ).fillna(1.0)
            quantidades = dados.groupby("chave_unica")["quantidade"].sum()
            dados = dados.drop_duplicates(subset="chave_unica", keep="last").copy()
            dados["quantidade"] = dados["chave_unica"].map(quantidades)
            relatorio.avisos.append(
                f"{duplicadas} linha(s) repetida(s) de Termos preservada(s) "
                "na quantidade, conforme COUNTROWS do Power BI"
            )
        else:
            relatorio.avisos.append(
                f"{duplicadas} registro(s) duplicado(s) no próprio arquivo "
                f"(chave: {' + '.join(dataset.chave_unica)}) — manteve-se a última ocorrência"
            )
            dados = dados.drop_duplicates(subset="chave_unica", keep="last")
    return dados.reset_index(drop=True)
