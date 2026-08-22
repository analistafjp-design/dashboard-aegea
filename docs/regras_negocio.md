# Mapa de Regras de Negócio

Este documento descreve, de forma verificável, **exatamente o que o sistema
faz hoje** — cada regra aqui aponta para o arquivo e a função que a
implementa. É a fonte confiável para auditoria e para comparação com os PBIX
quando eles estiverem disponíveis (ver `docs/validacao_powerbi.md`).

> **Como este documento foi produzido**: lendo o código-fonte linha a linha,
> não de memória. Onde uma regra foi inferida da especificação em vez de
> extraída de um PBIX real, isso está marcado explicitamente.

---

## 1. O que conta e o que não conta

### 1.1 Frentes (Comercial, VCG, Serviços, VCG Rio Bonito, VCG Bairro Legal/SFI)

Implementado em `app/etl/dominio.py::normalizar_frente`. Nunca agrupa frentes
— apenas padroniza a grafia. Ordem de decisão (a primeira que casar vence):

1. contém "rio bonito" → **VCG Rio Bonito**
2. contém "sfi" ou "bairro legal" → **VCG Bairro Legal/SFI**
3. contém "vcg" → **VCG**
4. contém "comercial" → **Comercial**
5. contém "servico"/"serviço" → **Serviços**
6. contém "outro", "canal", "parceiro" ou "digital" → **Outros Canais**
7. nenhuma regra casou → mantém o texto original da planilha (nunca é
   forçado para uma frente errada)

Célula vazia → **Não Informado** (nunca é omitida silenciosamente do
agrupamento; aparece como categoria própria nos rankings).

### 1.2 Canal de venda (Comercial × VCG × Outros)

Implementado em `dominio.py::canal_venda`. Deriva da frente já normalizada:

| Frente canônica | Canal |
|---|---|
| Comercial | `COMERCIAL` |
| VCG, VCG Rio Bonito, VCG Bairro Legal/SFI | `VCG` |
| qualquer outra (inclusive Outros Canais e Não Informado) | `OUTROS` |

Usado só no módulo **Venda**, para alimentar `Medidas.Venda Comercial`,
`Medidas.Venda VCG` e `Medidas.Vendas Outros Canais`. A frente original
continua disponível em `fato_vendas` para os gráficos "por frente".

### 1.3 Tipo de produção (Serviços × VCG) — Termos e Implantação

Implementado em `dominio.py::classificar_tipo`. Recebe, nesta ordem de
prioridade, os valores de **tipo → frente → serviço** (a primeira coluna
disponível e não vazia decide):

1. contém "vcg" → `VCG`
2. contém "servico"/"serviço" → `SERVICOS`
3. nenhuma bateu (ou todas vazias) → `NAO_CLASSIFICADO`

`NAO_CLASSIFICADO` **nunca** é somado a Serviços nem a VCG — aparece
separadamente para que a divergência de dado bruto fique visível em vez de
distorcer um dos dois totais.

### 1.4 Situação do faturamento de termos (funil)

Implementado em `dominio.py::normalizar_situacao_faturamento`. Ordem:

1. contém "cancel" → **Cancelado**
2. contém "fatur" e não contém "nao"/"não" → **Faturado**
3. contém "aguard"/"pendente"/"analise" → **Aguardando**
4. contém "negocia"/"andamento"/"tratativa" → **Negociação**
5. contém "concluid"/"pago" → **Faturado**
6. nenhuma regra casou → mantém o texto original (categoria "avulsa", não
   force-encaixada em nenhuma das quatro do funil)

O funil da tela (Termos → Negociação → Aguardando → Faturamento →
Concluído) usa exatamente essas quatro categorias; "Concluído" reaproveita
a contagem de "Faturado" (não é uma quinta situação separada nos dados).

### 1.5 Status do termo (Termos Aplicados)

Implementado em `dominio.py::normalizar_status_termo`:
"aplicad"/"ativo" → **Aplicado**; "cancel" → **Cancelado**;
"pendente"/"aguard" → **Pendente**; caso contrário mantém o texto original.

### 1.6 Faturado / Não faturado (Implantação)

Implementado em `app/etl/transformacao.py::_derivar`. A coluna `faturado` é
booleana (ver conversor em `app/etl/tipos.py::converter_booleano`, aceita
Sim/Não, Faturado/Não Faturado, 1/0). **Quando a coluna não existe na
planilha**, o sistema assume `False` (não faturado) — mas registra o aviso
`"colunas opcionais ausentes: faturado"` no relatório de importação, para
que a ausência de informação não seja lida como certeza de que nada foi
faturado. Ver `docs/matriz_dados_real.csv`, linha `implantacao / faturado`.

---

## 2. Como cada indicador é calculado

### 2.1 Venda (`app/analytics/vendas.py`)

| Indicador | Cálculo |
|---|---|
| Total de Vendas | soma de `quantidade` no mês, sem filtro de canal |
| Venda Comercial / VCG / Outros | soma de `quantidade`, filtrando `canal` |
| Venda por Dia | Total ÷ dias úteis decorridos no mês |
| Falta para a Meta | `max(Meta − Realizado, 0)` |
| Meta | soma de `metas.valor_meta` do módulo `VENDA`; se não houver meta
  `TOTAL`, soma as metas por segmento (Comercial + VCG + Outros) |

### 2.2 Implantação (`app/analytics/implantacao.py`)

| Indicador | Cálculo |
|---|---|
| Implantação Total | soma de `quantidade` no mês |
| Implantação Serviços / VCG | soma filtrando `tipo` |
| Implantação Faturada / Não Faturada | soma filtrando `faturado = True/False` |
| Valor Total Faturado | soma de `valor` **apenas** das linhas com `faturado = True` |
| % faturado / não faturado | `faturada ÷ total × 100` e o complemento |
| Alerta de faturamento pendente | disparado sempre que `não_faturada > 0`;
  texto: "Existem X implantação(ões) realizada(s) ainda não faturada(s) em `<mês>`." |
| Média Implantação/Dia | Realizado ÷ dias úteis decorridos |

### 2.3 Termos Aplicados (`app/analytics/termos.py`)

| Indicador | Cálculo |
|---|---|
| Realizado Total | soma de `quantidade` no mês |
| Realizado Serviços / VCG | soma filtrando `tipo` |
| Termos Aplicados | contagem de registros (não soma de `quantidade`) |
| Meta | soma de metas do módulo `TERMOS`; sem `TOTAL`, soma Serviços + VCG |

### 2.4 Faturamento de Termos (`app/analytics/faturamento.py`)

| Indicador | Cálculo |
|---|---|
| Termos Faturados / Em Negociação / Aguardando / Cancelados | soma de
  `quantidade`, filtrando `situacao` |
| Valor Faturado | soma de `valor` apenas dos registros com `situacao = Faturado` |
| Conversão Termo → Faturamento | `faturados_do_mês ÷ termos_aplicados_do_mesmo_mês × 100`
  — usa a base de **Termos Aplicados**, não a de Faturamento, como
  denominador; se não houver termos aplicados no mês, o indicador fica
  "Sem dados" em vez de dividir por zero |

### 2.5 Programação Diária (`app/analytics/programacao.py`)

| Indicador | Cálculo |
|---|---|
| O.S. Programadas (dia) | soma de `qtd_os` na **data de referência** (ver §4) |
| Equipes Programadas | recursos distintos na data de referência |
| Média de O.S. por Equipe | O.S. do dia ÷ equipes do dia |
| Desequilíbrio "sobrecarregada" | `os_da_equipe ≥ 1,5 × média do dia` |
| Desequilíbrio "subutilizada" | `os_da_equipe ≤ 0,5 × média do dia` |
| Cálculo de desequilíbrio só roda | com no mínimo 3 equipes programadas no dia
  (com menos, a "média" não é um parâmetro estatístico confiável) |

### 2.6 Home Executiva (`app/analytics/home.py`)

**Regra explícita e única do consolidado**: Total Realizado = soma dos
`realizado` de Termos + Venda + Implantação; Meta Consolidada = soma das
`meta` desses três módulos (cada uma já teve sua própria regra de composição
aplicada, ver 2.1–2.3). Faturamento de Termos e Programação **não entram**
no consolidado — têm cards próprios, sem serem somados a nada.

---

## 3. Metas — nunca estimadas

`app/analytics/metas.py`:

- `meta(modulo, ano, mes, segmento)` busca em `metas` filtrando por
  `cidade IS NULL` quando não há filtro de cidade, `equipe IS NULL` quando
  não há filtro de equipe (ou seja, a meta "geral" é distinta da meta
  específica de uma cidade/equipe, se ela existir). **Não faz fallback
  automático de meta geral para uma cidade filtrada** — se a cidade não tem
  meta própria, o indicador mostra "Meta não cadastrada" mesmo que exista
  meta nacional.
- `meta_total_composta` só soma os segmentos (Serviços+VCG, etc.) quando
  **não existe** meta `TOTAL` cadastrada — não soma os dois.
- Nunca há cálculo, projeção ou "estimativa razoável" de meta. Ausência de
  linha em `metas` = "Meta não cadastrada" em toda a interface.

---

## 4. Dias úteis e calendário

`app/analytics/calendario.py`:

- Dia útil = segunda a sexta, excluindo feriados nacionais fixos (Ano Novo,
  Tiradentes, Dia do Trabalho, Independência, N. Sra. Aparecida, Finados,
  Proclamação da República, Natal — lista em `app/config.py`) e feriados
  móveis calculados a partir da Páscoa (algoritmo de Meeus/Jones/Butcher):
  Carnaval (segunda e terça), Sexta-feira Santa, Corpus Christi.
- "Dias úteis decorridos" e "dias úteis restantes" usam a **data de
  referência do período** (`app/analytics/periodo.py::resolver`), que é a
  última data com dado no mês — nunca a data do relógio do servidor. Isso
  significa que reabrir o sistema um mês depois de importar dados de julho,
  sem nunca ter importado agosto, continua mostrando julho como período
  ativo (com "dias restantes" calculados a partir do fim de julho).

## 5. Comparação com o período anterior

`app/analytics/nucleo.py::comparar_meses`. Um mês em andamento **nunca** é
comparado com um mês fechado: a base do mês anterior é cortada no mesmo
número de dias úteis decorridos do mês atual (`data_no_enesimo_dia_util`).
Exemplo: se hoje é o 6º dia útil de agosto, julho é cortado no seu próprio
6º dia útil antes de calcular a variação percentual.

## 6. Projeção do mês

`app/analytics/nucleo.py::projecao`:

```
projeção = realizado + (realizado ÷ dias_úteis_decorridos) × dias_úteis_restantes
```

A média **não é arredondada antes de multiplicar** (bug corrigido nesta
auditoria — ver `docs/relatorio_final_validacao.md`, item ETL-01).
Sem dias úteis decorridos (mês ainda não começou ou sem dado nenhum), a
projeção é `None` — nunca extrapola a partir de zero.

## 7. Duplicidade e chave única

Cada base tem uma chave de negócio (ver `docs/matriz_dados_real.csv`,
coluna `faz_parte_da_chave_unica`), por exemplo, para Vendas:
`data + matrícula + frente + equipe`. Dentro de um mesmo arquivo, linhas
com a mesma chave mantêm **a última ocorrência** e as anteriores são
contabilizadas em "duplicadas_no_arquivo". Entre arquivos (reimportação),
a chave decide **update** (linha já existe) vs. **insert** (linha nova) —
nunca duplica no banco.

## 8. Segmentação de metas

`dominio.py::normalizar_modulo_meta` / `normalizar_segmento_meta` mapeiam a
planilha de metas para os módulos `TERMOS`, `VENDA`, `IMPLANTACAO` e para os
segmentos `TOTAL`, `SERVICOS`, `VCG`, `COMERCIAL`, `OUTROS` — mesma lógica
de "contém a palavra-chave" usada nas demais normalizações, nunca por
posição de coluna ou índice numérico.

---

## 9. Regras inferidas da especificação, não de um PBIX real

Como os três arquivos `.pbix` não foram fornecidos nesta sessão (ver
`docs/validacao_powerbi.md`), as regras acima com maior risco de divergir
do Power BI real são as que dependem de **texto livre nas planilhas**
(classificação de frente/tipo/situação por palavra-chave) — o Power BI
original provavelmente usa uma coluna já codificada ou uma tabela de
De-Para explícita. Quando os PBIX ou os Excel reais estiverem disponíveis,
revisar primeiro estas quatro funções de `dominio.py`, na ordem:

1. `classificar_tipo` (Serviços × VCG)
2. `normalizar_frente`
3. `normalizar_situacao_faturamento`
4. `canal_venda`
