# Referência extraída dos Power BI

Os três arquivos PBIX fornecidos foram inspecionados como modelos tabulares. A
implementação usa as medidas e colunas calculadas do modelo, não apenas a
aparência das telas.

| Modelo | Medidas encontradas | Colunas calculadas | Tabelas operacionais principais |
|---|---:|---:|---|
| Venda e Implantação | 56 | 51 | Interior, Atendimento, Faturamento |
| Termos Aplicados | 78 | 172 | f_Fild, Faturamento Termos, Calendário |
| Programação Diária | 4 | 34 | Programação |

## Venda e Implantação

- Venda Comercial: conta linhas de `Venda Potenciais/Factíveis` finalizadas,
  exclui códigos `114003` e `118048` e exclui recursos VCG.
- Venda VCG: mesma atividade/status, recursos contendo `RIOVCGPOPIN`,
  `RIOVCGEXTIN` ou `RIOVCGVENIN`, excluindo código `114003`.
- Implantação: conta `Ligação de Água` finalizada.
- Frente: aplica a mesma árvore de prefixos `RIOVCGEXTIN`, `RIOVCGPOPIN`,
  `RIOVCGVENIN`, `VCG`, `RIORECIN`, `RIORECLG`, `RIOVENIN` e `RIOVENLG`.
- Implantação faturada/não faturada: `0-EXECUTADO`, departamentos
  `IMPLANTAÇÃO DE LIGAÇÃO ÁGUA` ou `VEM COM A GENTE`, solicitação contendo
  `IMPLANTAÇÃO DE LIGAÇÃO`, valor maior que zero ou igual a zero e contagem
  distinta de número da ligação.
- Valor Total Faturado: soma o valor com os filtros de ocorrência e departamento.

## Termos Aplicados

- Serviços: resposta de serviço adicional contendo `110013` ou `210013`, sem
  recurso VCG e sem `RIOVCGEXTIN` no texto.
- VCG: código `310013` e recurso contendo `RIOVCGEXTIN`.
- Ambos aceitam apenas `Finalizada` ou `Encerrada com Ocorrência`.
- A situação do faturamento remove os prefixos `1-` a `5-` antes do agrupamento.

## Programação Diária

- Qtd O.S.: conta linhas cujo `Eqp_Geral` calculado não está vazio.
- Qtd Equipes: contagem distinta de `Eqp_Geral`, desconsiderando vazio.
- `Eqp_Geral` e Região usam o mapeamento explícito de recursos do PBIX.
- Projeto Principal deriva código/observação por recurso, ignora `CHECKLIST
  INICIO` e `REFEIÇÃO` e mantém as exceções do modelo.

## Metas incorporadas

| Indicador | Serviços | VCG | Total |
|---|---:|---:|---:|
| Implantação | 234 | 188 | 422 |
| Termos | 250 | 180 | 430 |

Esses valores são o padrão do modelo. Quando houver uma planilha de metas para
o período e o recorte, o valor explícito da planilha prevalece.
