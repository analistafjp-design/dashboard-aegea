# Dicionário de Indicadores

Cada indicador responde a uma pergunta gerencial e tem regra explícita.
Formato: **Fonte · Colunas · Filtros · Regra · Resultado**.

Convenções válidas para todo o documento:

- **Mês de referência**: quando o usuário não escolhe ano/mês, o sistema usa o
  último mês **com dados**, nunca o mês do relógio.
- **Dias úteis**: excluem sábados, domingos, feriados nacionais fixos, Carnaval
  (segunda e terça), Sexta-feira Santa e Corpus Christi.
- **Meta**: usa primeiro a planilha de metas. Sem valor explícito, aplica as
  metas constantes dos PBIX: Implantação 422 (234 Serviços + 188 VCG) e
  Termos 430 (250 Serviços + 180 VCG).
- **Sem dados ≠ 0**: base vazia devolve `null` e a tela mostra "Sem dados"; zero
  só aparece quando o zero é real.

---

## Fórmulas comuns

| Indicador | Regra |
|---|---|
| Realizado | Soma da coluna de medida no recorte filtrado |
| Meta | Valor oficial cadastrado (`metas.valor_meta`) |
| Falta | `max(Meta − Realizado, 0)` |
| % Atingimento | `Realizado ÷ Meta × 100` |
| Meta acumulada | `Meta × (dias úteis decorridos ÷ dias úteis totais)` |
| Atingimento do ritmo | `Realizado ÷ Meta acumulada × 100` |
| Média por dia | `Realizado ÷ dias úteis decorridos` |
| Necessário por dia | `max(Meta − Realizado, 0) ÷ dias úteis restantes` |
| Projeção | `Realizado + (Realizado ÷ dias úteis decorridos) × dias úteis restantes` |
| Variação vs. anterior | Compara com o mês anterior **cortado no mesmo número de dias úteis** |

### Cores (status)

| Cor | Regra |
|---|---|
| 🟢 Verde | Atingimento do ritmo ≥ 100% |
| 🟡 Amarelo | Entre 90% e 100% |
| 🔴 Vermelho | Abaixo de 90% |
| 🔵 Azul | Indicador sem meta — apenas acompanhamento |
| ⚪ Cinza | Sem dados |

---

## Módulo 1 — Termos Aplicados (PBIX 1)

| Indicador | Pergunta | Referência no PBIX | Regra |
|---|---|---|---|
| Realizado Total | Como estamos no mês? | `f_Fild.Realizado Total`, `Medidas.Realizado Total` | Soma de `fato_termos.quantidade` no mês |
| Realizado Serviços | Como está Serviços? | `f_Fild.Realizado Serviços` | Códigos 110013/210013, status permitido e exclusões VCG do PBIX |
| Realizado VCG | Como está VCG? | `f_Fild.Realizado VCG` | Código 310013, recurso RIOVCGEXTIN e status permitido |
| Meta / Meta Serviços / Meta VCG | Qual o compromisso? | Medidas de meta do PBIX | `metas` com módulo `TERMOS` |
| % Atingimento | Estamos atingindo? | `Medidas.% Atingimento` | Realizado ÷ Meta × 100 |
| Meta acumulada | Estamos no ritmo? | — | Meta × fração de dias úteis decorridos |
| Dias Restantes | Quanto tempo resta? | `Medidas.Dias Restantes` | Dias úteis até o fim do mês |
| Realizado por Dia | Qual o ritmo? | — | Realizado ÷ dias úteis decorridos |
| Termos Aplicados | Quantos termos? | `Termos.Qtd Termos Aplicados` | Contagem de registros |
| Status dos Termos | Qual a situação? | `Termos.Status Termo` | Agrupamento por status normalizado |
| Distribuição por cidade | Onde está concentrado? | `d_Cadastro.CIDADE`, `Interior.Cidade` | Soma por cidade |
| Distribuição por setor | Qual área produz mais? | `Setor do Recurso.Setor do Recurso` | Soma por setor |

**Classificação Serviços × VCG.** Na exportação bruta, segue exatamente códigos,
recursos e status do PBIX. A dedução por `tipo`/`frente` permanece somente para
planilhas antigas já consolidadas.

---

## Módulo 1 — Faturamento de Termos (PBIX 1)

| Indicador | Pergunta | Referência no PBIX | Regra |
|---|---|---|---|
| Termos Faturados | Quanto foi faturado? | `Faturamento Termos.Situação` | Soma com `situacao = Faturado` |
| Em Negociação | O que está em tratativa? | `Faturamento Termos.Qtd Negociação` | Soma com `situacao = Negociação` |
| Aguardando | O que está parado? | `Faturamento Termos.Qtd Aguardando` | Soma com `situacao = Aguardando` |
| Cancelados | Quanto se perdeu? | `Faturamento Termos.Qtd Cancelado` | Soma com `situacao = Cancelado` |
| Valor Faturado | Qual o valor? | Coluna de valor do PBIX | Soma de `valor` dos faturados |
| Conversão Termo → Faturamento | Quanto virou receita? | — | Termos faturados ÷ termos aplicados no mesmo mês |
| Funil | Onde trava o processo? | — | Termos → Negociação → Aguardando → Faturamento → Concluído |

**Normalização da situação.** Texto livre é mapeado para quatro situações
canônicas: "cancel*" → Cancelado; "fatur*"/"concluíd*"/"pago" → Faturado;
"aguard*"/"pendente"/"análise" → Aguardando; "negocia*"/"tratativa"/"andamento"
→ Negociação. Qualquer outro valor é preservado como veio, em "Outras".

---

## Módulo 2 — Venda (PBIX 2)

| Indicador | Pergunta | Referência no PBIX | Regra |
|---|---|---|---|
| Total de Vendas | Como está a venda? | `Medidas.Total Venda` | Venda Comercial + Venda VCG no filtro |
| Venda Comercial | Como está o Comercial? | `Medidas.Venda Comercial` | Venda Potenciais/Factíveis finalizada, sem recursos VCG e sem códigos 114003/118048 |
| Venda VCG | Como está VCG? | `Medidas.Venda VCG` | Mesma atividade/status, recursos VCG e sem código 114003 |
| Outros Canais | Quanto vem de fora? | `Medidas.Vendas Outros Canais` | `canal = OUTROS` |
| Venda por Dia | Qual o ritmo? | `Medidas.Venda por Dia` | Total ÷ dias úteis decorridos |
| Falta Venda | Quanto falta? | `Medidas.Falta Venda` | `max(Meta − Realizado, 0)` |
| Top cidades / equipes | Onde está o resultado? | — | Ranking por soma |

**Canal.** A frente original é preservada em `dim_frente` (Comercial, VCG,
VCG Rio Bonito, VCG Bairro Legal/SFI, Outros Canais). O campo `canal` é apenas
o agrupamento usado pelas três medidas de venda do PBIX.

---

## Módulo 2 — Implantação (PBIX 2)

| Indicador | Pergunta | Referência no PBIX | Regra |
|---|---|---|---|
| Implantação Total | Quanto foi implantado? | `Medidas.Total Implantação`, `Implantação Geral` | Contagem de Ligação de Água finalizada |
| Implantação Serviços | Como está Serviços? | `Medidas.Implantação por Mês - Serviços` | `tipo = SERVICOS` |
| Implantação VCG | Como está VCG? | `Medidas.Implantação Mês - VCG` | `tipo = VCG` |
| Média Implantação/Dia | Qual o ritmo? | `Medidas.Média Implantação Dia - Serviços`, `Implantação Dia VCG` | Realizado ÷ dias úteis decorridos |
| Implantação Faturada | Quanto virou receita? | `Medidas.Implantação Faturada` | Nº de ligação distinto, ocorrência 0-EXECUTADO, departamentos e tipo de solicitação do PBIX, valor > 0 |
| Implantação Não Faturada | Qual receita represada? | `Medidas.Implantação Não Faturada` | Mesmos filtros, valor = 0 |
| Valor Total Faturado | Quanto entrou? | `Medidas.Valor Total Faturado` | Soma de valor com ocorrência e departamentos do PBIX |
| Falta Total | Quanto falta? | `Medidas.Falta Total`, `Total a Realizar` | `max(Meta − Realizado, 0)` |
| Alerta de faturamento | O que precisa de ação? | — | "Existem X implantações realizadas ainda não faturadas" |

Planilhas consolidadas antigas com o campo `faturado` continuam aceitas como
compatibilidade; a exportação bruta da pasta Faturamento tem prioridade.

---

## Módulo 3 — Programação Diária (PBIX 3)

| Indicador | Pergunta | Referência no PBIX | Regra |
|---|---|---|---|
| O.S. Programadas (dia) | Qual a carga de hoje? | `Medidas.Qtd OS Programadas` | Soma de `qtd_os` na data de referência |
| Equipes Programadas | Quantas equipes em campo? | `Medidas.Qtd Equipes Programadas` | `Eqp_Geral` distinta e não vazia na data |
| Média de O.S. por Equipe | A carga está equilibrada? | — | O.S. do dia ÷ equipes do dia |
| O.S. Programadas (mês) | Qual o volume do mês? | — | Soma de `qtd_os` no mês |
| Desequilíbrios | Onde rebalancear? | — | Equipe ≥ 1,5× a média (sobrecarregada) ou ≤ 0,5× (subutilizada), com no mínimo 3 equipes no dia |
| Agenda operacional | Quem faz o quê? | `Programação.Regiao`, `Programação.Recurso`, `Medidas.Projeto Principal` | Lista data/região/equipe/projeto/O.S. |

---

## Equipes

"Equipe logada" é lida como **equipe com produção registrada no período** — é o
que a base operacional permite afirmar.

| Indicador | Referência no PBIX | Regra |
|---|---|---|
| Equipes Logadas Serviços | `Medidas.Equipes Logadas Serviços` | Equipes distintas com implantação `tipo = SERVICOS` |
| Equipes Logadas Venda | `Medidas.Equipes Logadas Venda` | Equipes distintas com venda no mês |
| Equipes Logadas VCG | `Medidas.Equipes Logadas VCG Rio Bonito` / `VCG SFI` | Equipes distintas com implantação `tipo = VCG` |
| Equipes Programadas | `Medidas.Qtd Equipes Programadas` | Recursos distintos na programação do mês |

A tabela executiva mostra **Termos, Venda e Implantação em colunas separadas**.
A coluna "Realizado", a meta e o ranking usam a base escolhida no seletor —
os módulos nunca são somados entre si.

---

## Home Executiva — consolidado

| Indicador | Regra |
|---|---|
| Total Realizado | Soma dos realizados de Termos + Venda + Implantação |
| Meta Consolidada | Soma das metas cadastradas desses três módulos |
| % de Atingimento | Total Realizado ÷ Meta Consolidada × 100 |
| Falta para a Meta | `max(Meta Consolidada − Total Realizado, 0)` |
| Equipes Ativas | Equipes distintas com produção em qualquer módulo no mês |
| Dias Úteis Restantes | Dias úteis entre a referência e o fim do mês |

A soma dos três módulos é uma **regra declarada**, existente apenas na Home,
para dar uma leitura única de "como estamos". O detalhe de cada módulo continua
separado nas páginas específicas, como exige a regra de não misturar registros.

---

## Alertas

| Categoria | Regra |
|---|---|
| 🔴 Crítico | Atingimento do ritmo < 80%; queda de venda ≥ 10%; ≥ 30% da implantação sem faturamento; cidades com atingimento < 80% |
| 🟡 Atenção | Ritmo entre 80% e 95%; queda de venda entre 5% e 10%; faturamento pendente; equipe sem produção; equipe sobrecarregada |
| 🟢 Normal | Ritmo ≥ 95% |
