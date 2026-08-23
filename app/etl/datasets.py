"""Dicionário de dados e mapa de colunas.

Cada dataset descreve as colunas que o sistema entende, com os sinônimos
aceitos. É isso que permite:

* identificar o arquivo pela ESTRUTURA e não pelo nome (regra 53);
* aceitar variações de cabeçalho — "Data da Atividade", "Data" ou
  "Dt. Atividade" caem todas em `data` (regra 54);
* gerar automaticamente a documentação do dicionário de dados (regra 55).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.utils.texto import chave_comparacao


@dataclass(frozen=True)
class Campo:
    nome: str                      # nome interno (snake_case)
    tipo: str                      # data | texto | numero | inteiro | booleano
    descricao: str
    aliases: tuple[str, ...] = ()  # cabeçalhos aceitos no Excel
    obrigatorio: bool = False
    peso: int = 1                  # peso na identificação automática do arquivo
    padrao: object = None          # valor quando a coluna não existe no arquivo

    @property
    def chaves(self) -> tuple[str, ...]:
        """Nome e apelidos na ORDEM de declaração, sem repetição.

        A ordem importa: quando a planilha tem mais de uma coluna que casa
        com o campo, vence a primeira declarada. Isso era um `set`, cuja
        ordem de iteração é indefinida — o campo `data` do Atendimento, por
        exemplo, podia casar tanto com "Data do Pedido" quanto com "Data de
        Encerramento" (vazia enquanto a O.S. está aberta), e qual delas
        vencia mudava sem motivo aparente.
        """
        vistos: dict[str, None] = {}
        for apelido in (self.nome, *self.aliases):
            vistos.setdefault(chave_comparacao(apelido), None)
        return tuple(vistos)


@dataclass(frozen=True)
class Dataset:
    nome: str
    titulo: str
    modulo: str
    tabela: str
    descricao: str
    campos: tuple[Campo, ...]
    chave_unica: tuple[str, ...]
    dicas_nome_arquivo: tuple[str, ...] = ()
    campos_derivados: tuple[str, ...] = field(default=())
    # Base que NÃO participa da identificação automática: só é usada quando
    # escolhida de propósito (aba da tela ou "= base" na pasta monitorada).
    # É o caso do Atendimento, cujas colunas se parecem com as de várias
    # outras bases — mandar um arquivo para lá é decisão de negócio, não
    # algo que dê para deduzir pela estrutura. Sem isso, ela concorreria na
    # detecção e ainda tiraria a "exclusividade" de colunas que hoje
    # identificam Implantação (ex.: Serviço).
    somente_manual: bool = False

    @property
    def obrigatorios(self) -> list[Campo]:
        return [c for c in self.campos if c.obrigatorio]

    def campo(self, nome: str) -> Campo | None:
        return next((c for c in self.campos if c.nome == nome), None)


# --------------------------------------------------------------------------
# Campos reaproveitados entre datasets
# --------------------------------------------------------------------------
CAMPO_DATA = Campo(
    "data", "data", "Data do registro (base para mês, dia útil e acumulados)",
    aliases=("data da atividade", "dt atividade", "data atividade", "data execucao",
             "data da execucao", "data do termo", "data venda", "data da venda",
             "data implantacao", "data da implantacao", "data base", "dt", "competencia",
             "data do pedido", "data de encerramento"),
    obrigatorio=True, peso=3,
)
CAMPO_CIDADE = Campo(
    "cidade", "texto", "Cidade / município do registro",
    aliases=("municipio", "cidade cliente", "d_cadastro cidade", "cidade_cadastro",
             "localidade", "interior cidade", "cidade/localidade"),
    peso=2,
)
CAMPO_EQUIPE = Campo(
    "equipe", "texto", "Equipe / recurso responsável",
    aliases=("recurso", "time", "turma", "equipe recurso", "nome da equipe", "colaborador",
             "executado por", "login do recurso"),
    peso=2,
)
CAMPO_FRENTE = Campo(
    "frente", "texto", "Frente de atuação (Comercial, VCG, Serviços, VCG Rio Bonito, VCG SFI)",
    aliases=("canal", "segmento", "frente de trabalho", "tipo de frente", "origem",
             "classificacao", "categoria"),
    peso=2,
)
CAMPO_MATRICULA = Campo(
    "matricula", "texto", "Matrícula / identificador do cliente ou contrato",
    aliases=("matricula cliente", "contrato", "codigo cliente", "cod cliente", "inscricao",
             "numero da conta", "n ligacao", "n do pedido", "id da atividade"),
    peso=2,
)
CAMPO_QUANTIDADE = Campo(
    "quantidade", "numero", "Quantidade do registro (1 quando cada linha é um evento)",
    aliases=("qtd", "qtde", "quantidade realizada", "volume", "total"),
    padrao=1.0,
)
CAMPO_VALOR = Campo(
    "valor", "numero", "Valor financeiro em reais, quando disponível",
    aliases=("valor total", "vlr", "valor faturado", "receita", "valor r$",
             "valor cobrado", "valor total dos debitos"),
)

# --------------------------------------------------------------------------
# PBIX 1 — Termos / Faturamento
# --------------------------------------------------------------------------
TERMOS = Dataset(
    nome="termos",
    titulo="Termos Aplicados",
    modulo="TERMOS",
    tabela="fato_termos",
    descricao=(
        "Base operacional de termos aplicados. Alimenta Realizado Total, "
        "Realizado Serviços, Realizado VCG, % de atingimento e distribuição "
        "por cidade e setor."
    ),
    campos=(
        CAMPO_DATA,
        CAMPO_CIDADE,
        CAMPO_EQUIPE,
        CAMPO_FRENTE,
        CAMPO_MATRICULA,
        Campo("tipo", "texto",
              "Classificação Serviços x VCG do termo",
              aliases=("tipo termo", "tipo de termo", "categoria", "tipo servico",
                       "grupo", "produto", "tipo de atividade", "codigo/descricao",
                       "descricao do servico"),
              peso=2),
        Campo("setor", "texto", "Setor do Recurso (PBIX: Setor do Recurso.Setor do Recurso)",
              aliases=("setor do recurso.setor do recurso", "setor do recurso",
                       "setor recurso", "area", "gerencia",
                       "area de trabalho", "distrito"), peso=2),
        Campo("status_termo", "texto", "Status do termo (PBIX: Termos.Status Termo)",
              aliases=("status", "situacao termo", "status do termo",
                       "ocorrencia_encerramento"), peso=2),
        Campo("status_atividade", "texto", "Status da Atividade do Field Service",
              aliases=("status da atividade",), peso=3),
        Campo("servico_adicional", "texto",
              "Resposta que contém os códigos 110013/210013/310013",
              aliases=("servico adicionais resposta", "serviço adicionais resposta"), peso=3),
        CAMPO_QUANTIDADE,
        CAMPO_VALOR,
    ),
    chave_unica=("data", "matricula", "tipo", "equipe"),
    dicas_nome_arquivo=("termo", "aplicado", "fild"),
)

FATURAMENTO = Dataset(
    nome="faturamento",
    titulo="Faturamento de Termos",
    modulo="TERMOS",
    tabela="fato_faturamento",
    descricao=(
        "Situação de faturamento dos termos. Alimenta Qtd Negociação, "
        "Qtd Aguardando, Qtd Cancelado, Qtd Faturado, o funil e a conversão."
    ),
    campos=(
        Campo("data", "data", "Data de referência (PBIX: Faturamento Termos.Início do Mês)",
              aliases=("inicio do mes", "inicio mes", "dat notificacao",
                       "data faturamento", "mes referencia", "competencia", "data"),
              obrigatorio=True, peso=3),
        CAMPO_CIDADE,
        Campo("situacao", "texto",
              "Situação do faturamento: Negociação, Aguardando, Faturado ou Cancelado",
              aliases=("situacao do termo", "status", "situacao termo"),
              obrigatorio=True, peso=3),
        Campo("numero_termo", "texto", "Número/identificador do termo",
              aliases=("matricula", "termo", "num termo", "nº termo", "numero do termo",
                       "num termo ocorrencia", "num termo parcelamento", "protocolo"),
              peso=2),
        CAMPO_QUANTIDADE,
        CAMPO_VALOR,
    ),
    chave_unica=("data", "numero_termo", "situacao", "cidade"),
    dicas_nome_arquivo=("faturamento", "termo"),
)

FATURAMENTO_IMPLANTACAO = Dataset(
    nome="faturamento_implantacao",
    titulo="Faturamento de Implantação",
    modulo="IMPLANTACAO",
    tabela="fato_faturamento_implantacao",
    descricao=(
        "Base usada pelas medidas Implantação Faturada, Implantação Não Faturada "
        "e Valor Total Faturado do PBIX Venda e Implantação."
    ),
    campos=(
        Campo("data", "data", "Data de execução do faturamento",
              aliases=("data execucao", "data encerramento", "data pedido", "data"),
              obrigatorio=True, peso=3),
        Campo("ligacao", "texto", "Número da ligação",
              aliases=("n ligacao", "numero ligacao", "nº ligação"),
              obrigatorio=True, peso=3),
        Campo("tipo_solicitacao", "texto", "Tipo de solicitação",
              aliases=("tipo de solicitacao",), obrigatorio=True, peso=3),
        Campo("ocorrencia", "texto", "Ocorrência de encerramento",
              aliases=("ocorrencia encerramento", "ocorrencia_encerramento"),
              obrigatorio=True, peso=3),
        Campo("departamento", "texto", "Nome do departamento",
              aliases=("nome departamento",), obrigatorio=True, peso=3),
        Campo("valor", "numero", "Valor do serviço",
              aliases=("valor do servico", "valor servico num", "valor")),
    ),
    chave_unica=("data", "ligacao", "tipo_solicitacao", "departamento"),
    dicas_nome_arquivo=("faturamento", "solicitacao"),
)

# --------------------------------------------------------------------------
# PBIX 2 — Venda / Implantação
# --------------------------------------------------------------------------
VENDAS = Dataset(
    nome="vendas",
    titulo="Venda",
    modulo="VENDA",
    tabela="fato_vendas",
    descricao=(
        "Base de vendas. Alimenta Total Venda, Venda Comercial, Venda VCG, "
        "Vendas Outros Canais, Venda por Dia e Falta Venda."
    ),
    campos=(
        CAMPO_DATA,
        CAMPO_CIDADE,
        CAMPO_EQUIPE,
        Campo("frente", "texto",
              "Canal da venda: Comercial, VCG ou Outros Canais",
              aliases=("canal", "canal de venda", "origem da venda", "segmento",
                       "tipo de venda", "origem", "classificacao", "categoria"),
              peso=3),
        Campo("tipo_atividade", "texto", "Tipo de Atividade usado pela medida Venda",
              aliases=("tipo de atividade",), peso=3),
        Campo("status_atividade", "texto", "Status da Atividade (somente Finalizada)",
              aliases=("status da atividade",), peso=3),
        Campo("codigo_descricao", "texto",
              "Código/Descrição usado nas exclusões 114003/118048",
              aliases=("codigo/descricao",), peso=2),
        CAMPO_MATRICULA,
        CAMPO_QUANTIDADE,
        CAMPO_VALOR,
    ),
    chave_unica=("data", "matricula", "frente", "equipe"),
    dicas_nome_arquivo=("venda", "comercial"),
)

IMPLANTACAO = Dataset(
    nome="implantacao",
    titulo="Implantação",
    modulo="IMPLANTACAO",
    tabela="fato_implantacao",
    descricao=(
        "Base de implantações. Alimenta Implantação Geral, Serviços x VCG, "
        "média diária, implantação faturada e não faturada e valor faturado."
    ),
    campos=(
        CAMPO_DATA,
        CAMPO_CIDADE,
        CAMPO_EQUIPE,
        CAMPO_FRENTE,
        CAMPO_MATRICULA,
        Campo("tipo", "texto", "Classificação Serviços x VCG da implantação",
              aliases=("tipo implantacao", "tipo de implantacao", "categoria",
                       "grupo", "produto", "tipo servico", "tipo de atividade"),
              peso=2),
        Campo("servico", "texto", "Serviço executado",
              aliases=("descricao servico", "atividade", "descricao", "servico executado",
                       "descricao do servico", "codigo/descricao", "tipo de atividade")),
        Campo("tipo_atividade", "texto", "Tipo de Atividade (PBIX: Ligação de Água)",
              aliases=("tipo de atividade",), peso=3),
        Campo("status_atividade", "texto", "Status da Atividade (PBIX: Finalizada)",
              aliases=("status da atividade",), peso=3),
        Campo("codigo_descricao", "texto", "Código/Descrição da atividade",
              aliases=("codigo/descricao",), peso=2),
        Campo("faturado", "booleano",
              "Indica se a implantação já foi faturada (Sim/Não, Faturado/Não Faturado)",
              aliases=("situacao faturamento", "faturada", "status faturamento",
                       "implantacao faturada", "faturamento"),
              peso=2),
        CAMPO_QUANTIDADE,
        CAMPO_VALOR,
    ),
    chave_unica=("data", "matricula", "servico", "equipe"),
    dicas_nome_arquivo=("implanta", "acompanhamento"),
)

# --------------------------------------------------------------------------
# PBIX 3 — Programação Diária
# --------------------------------------------------------------------------
PROGRAMACAO = Dataset(
    nome="programacao",
    titulo="Programação Diária",
    modulo="PROGRAMACAO",
    tabela="fato_programacao",
    descricao=(
        "Programação operacional. Alimenta Qtd OS Programadas, "
        "Qtd Equipes Programadas e a visão de carga por equipe, região e projeto."
    ),
    campos=(
        Campo("data", "data", "Data da programação (PBIX: Medidas.Data Programação)",
              aliases=("data programacao", "data da programacao", "dia", "data prog",
                       "data execucao"),
              obrigatorio=True, peso=3),
        Campo("regiao", "texto", "Região da programação (PBIX: Programação.Regiao)",
              aliases=("regiao", "polo", "base", "area", "regional",
                       "area de trabalho", "distrito", "localidade"),
              peso=3),
        Campo("recurso", "texto", "Recurso/equipe programada (PBIX: Programação.Recurso)",
              aliases=("equipe", "recurso programado", "time", "turma", "colaborador",
                       "login do recurso", "executado por"),
              obrigatorio=True, peso=3),
        Campo("projeto", "texto", "Projeto principal (PBIX: Medidas.Projeto Principal)",
              aliases=("projeto principal", "obra", "contrato", "programa"),
              peso=2),
        Campo("codigo_descricao", "texto", "Código/Descrição usado para derivar o projeto",
              aliases=("codigo/descricao",), peso=2),
        Campo("observacao", "texto", "Observação usada para derivar o projeto",
              aliases=("observacao", "observações", "observacoes")),
        Campo("tipo_atividade", "texto", "Tipo de atividade da programação",
              aliases=("tipo de atividade",)),
        CAMPO_CIDADE,
        Campo("qtd_os", "numero", "Quantidade de O.S. programadas",
              aliases=("qtd os", "os", "quantidade os", "ordens de servico", "qtd ordens",
                       "os programadas", "quantidade programada"),
              obrigatorio=True, peso=3, padrao=1.0),
    ),
    chave_unica=("data", "regiao", "recurso", "projeto"),
    dicas_nome_arquivo=("programacao", "programa"),
)

# --------------------------------------------------------------------------
# Metas oficiais
# --------------------------------------------------------------------------
METAS = Dataset(
    nome="metas",
    titulo="Metas",
    modulo="METAS",
    tabela="metas",
    descricao=(
        "Metas oficiais por mês, módulo e segmento. Quando um período não "
        "possui meta cadastrada o sistema exibe 'Meta não cadastrada' — "
        "nunca estima um valor."
    ),
    campos=(
        Campo("ano", "inteiro", "Ano da meta", aliases=("exercicio",), obrigatorio=True, peso=3),
        Campo("mes", "inteiro", "Mês da meta (1 a 12)", aliases=("mes numero", "num mes"),
              obrigatorio=True, peso=3),
        Campo("modulo", "texto", "Módulo: TERMOS, VENDA ou IMPLANTACAO",
              aliases=("indicador", "area", "tipo meta"), obrigatorio=True, peso=3),
        Campo("segmento", "texto", "Segmento: TOTAL, SERVICOS, VCG, COMERCIAL ou OUTROS",
              aliases=("tipo", "frente", "categoria"), padrao="TOTAL", peso=2),
        Campo("cidade", "texto", "Cidade da meta (vazio = meta geral)", aliases=("municipio",)),
        Campo("equipe", "texto", "Equipe da meta (vazio = meta geral)", aliases=("recurso",)),
        Campo("valor_meta", "numero", "Valor da meta",
              aliases=("meta", "valor", "quantidade meta", "meta mes"),
              obrigatorio=True, peso=3),
    ),
    chave_unica=("ano", "mes", "modulo", "segmento", "cidade", "equipe"),
    dicas_nome_arquivo=("meta",),
)

# --------------------------------------------------------------------------
# Atendimento — vendas vindas de outros canais
# --------------------------------------------------------------------------
# Base "Analitico - acomp de solicitação". Não vira uma tabela própria:
# alimenta fato_vendas com canal "Outros Canais", contando uma venda por
# linha que sobrevive aos filtros da medida do Power BI (ver
# app/etl/regras_atendimento.py).
ATENDIMENTO = Dataset(
    nome="atendimento",
    titulo="Atendimento (Vendas Outros Canais)",
    modulo="VENDA",
    tabela="fato_vendas",
    descricao=(
        "Solicitações de atendimento. Cada linha executada de implantação de "
        "ligação de água, nas localidades do Interior, conta como uma venda "
        "por Outros Canais — mesma regra da medida 'Vendas Outros Canais' do "
        "Power BI."
    ),
    campos=(
        Campo("data", "data", "Data do pedido",
              aliases=("data do pedido", "data de encerramento", "data"),
              obrigatorio=True, peso=3),
        Campo("cidade", "texto", "Localidade da solicitação",
              aliases=("localidade", "municipio"), obrigatorio=True, peso=3),
        Campo("servico", "texto", "Descrição do serviço solicitado",
              aliases=("descricao do servico", "servico"), obrigatorio=True, peso=3),
        # Não é obrigatório de propósito: uma O.S. ainda em aberto vem com a
        # ocorrência vazia, e quem deve explicar esse descarte é a regra
        # ("fora de 0-Executado"), não a validação genérica de coluna vazia.
        Campo("ocorrencia", "texto", "Ocorrência de encerramento da O.S.",
              aliases=("ocorrencia_encerramento", "ocorrencia encerramento"),
              peso=3),
        Campo("ligacao", "texto", "Número da ligação (vazio = não conta como venda)",
              aliases=("n ligacao", "no ligacao", "numero da ligacao"), peso=3),
        Campo("usuario_emissor", "texto", "Usuário que emitiu a O.S.",
              aliases=("usuario emitiu o s", "usuario emitiu os",
                       "usuario emitiu a o s"), peso=2),
        Campo("matricula", "texto", "Número do pedido",
              aliases=("n do pedido", "no do pedido", "numero do pedido"), peso=2),
        Campo("equipe", "texto", "Quem executou a O.S.",
              aliases=("executado por", "usuario concluiu o s")),
        Campo("valor", "numero", "Valor cobrado",
              aliases=("valor cobrado", "valor")),
    ),
    # Nº do pedido identifica a solicitação; data entra na chave porque o
    # mesmo pedido pode aparecer em recortes diferentes do relatório.
    chave_unica=("data", "matricula", "servico"),
    dicas_nome_arquivo=("analitico", "solicitacao", "atendimento"),
    somente_manual=True,
)

DATASETS: dict[str, Dataset] = {
    d.nome: d for d in (TERMOS, FATURAMENTO, FATURAMENTO_IMPLANTACAO, VENDAS,
                        IMPLANTACAO, PROGRAMACAO, METAS, ATENDIMENTO)
}

ORDEM_CARGA = ("metas", "termos", "faturamento", "vendas", "implantacao",
               "faturamento_implantacao", "programacao", "atendimento")


def get_dataset(nome: str) -> Dataset:
    if nome not in DATASETS:
        raise KeyError(f"Dataset desconhecido: {nome}")
    return DATASETS[nome]
