# Relatório Final de Validação

**Data da auditoria**: 21/08/2026
**Escopo**: revisão completa do repositório `dashboard-aegea` existente —
backend, frontend, ETL, banco, indicadores, upload, exportação, testes,
documentação, segurança e performance.

---

## Resumo executivo

O projeto foi auditado fisicamente (não a partir do resumo de sessões
anteriores) e está **funcional, testado e documentado**. Três lacunas reais
foram encontradas e corrigidas durante esta auditoria (seção "Correções
aplicadas"). Uma pendência **bloqueia** a validação numérica final e está
sinalizada com destaque na seção 1.

## ⚠️ Pendência crítica: PBIX e Excel reais indisponíveis

Os três arquivos `.pbix` de referência —

1. `87916e93-5cdd-487b-b438-d9f55ab57d72.pbix`
2. `Acompanhamento Venda e Implantação(2).pbix`
3. `Programação Diária.pbix`

— **não foram fornecidos em nenhuma sessão de desenvolvimento até agora**,
nem os arquivos Excel reais que os alimentam. Foi confirmado nesta auditoria
que não há `.pbix` nem `.xlsx`/`.xls` de dados reais em nenhum diretório
acessível a esta sessão.

**Consequência**: a comparação numérica Indicador-a-indicador exigida pelas
seções 6, 14 e 37 do prompt de continuação **não pôde ser executada** — não
por falta de ferramenta (`scripts/validar_indicadores.py` está pronto e
testado com valores simulados), mas por falta do dado de origem. Todo item
que dependeria dessa comparação está marcado como **NÃO VALIDADO** abaixo,
de forma explícita — nenhum número foi assumido como correto sem conferência.

O que **foi** feito sem os PBIX: reconstrução das regras de negócio a partir
dos nomes de medida citados na especificação (`docs/regras_negocio.md`),
auditoria de código, correção de bugs reais, testes automatizados,
verificação de segurança e performance. Isso reduz o risco, mas não
substitui a conferência numérica.

---

## 1. Status por PBIX

### PBIX 1 — Termos / Faturamento

| Item | Status |
|---|---|
| Estrutura de páginas/medidas reconstruída da especificação | ✅ Feito (`docs/regras_negocio.md` §2.3–2.4) |
| Leitura do `.pbix` real (páginas, DAX, Power Query) | ❌ NÃO VALIDADO — arquivo indisponível |
| Comparação numérica de indicadores | ❌ NÃO VALIDADO — arquivo indisponível |
| Fonte Excel real identificada e testada | ❌ NÃO VALIDADO — arquivo indisponível |

### PBIX 2 — Venda / Implantação

| Item | Status |
|---|---|
| Estrutura de páginas/medidas reconstruída da especificação | ✅ Feito (`docs/regras_negocio.md` §2.1–2.2) |
| Leitura do `.pbix` real (páginas, DAX, Power Query) | ❌ NÃO VALIDADO — arquivo indisponível |
| Comparação numérica de indicadores | ❌ NÃO VALIDADO — arquivo indisponível |
| Fonte Excel real identificada e testada | ❌ NÃO VALIDADO — arquivo indisponível |

### PBIX 3 — Programação Diária

| Item | Status |
|---|---|
| Estrutura de páginas/medidas reconstruída da especificação | ✅ Feito (`docs/regras_negocio.md` §2.5) |
| Leitura do `.pbix` real (páginas, DAX, Power Query) | ❌ NÃO VALIDADO — arquivo indisponível |
| Comparação numérica de indicadores | ❌ NÃO VALIDADO — arquivo indisponível |
| Fonte Excel real identificada e testada | ❌ NÃO VALIDADO — arquivo indisponível |

---

## 2. Indicadores — contagem

| Total de indicadores documentados | Validados contra PBIX (OK) | Divergentes | Não validados |
|---:|---:|---:|---:|
| 46 (ver `docs/matriz_dados_real.csv`) | 0 | 0 | 46 |

Todos os 46 campos estão implementados e cobertos por teste automatizado
(dado sintético, ver seção 4), mas **zero** foram comparados com um número
real do Power BI, pela razão descrita acima.

---

## 3. Correções aplicadas nesta auditoria

Encontradas por leitura crítica do código (não por relato do usuário) e
corrigidas nesta sessão:

| ID | Achado | Correção |
|---|---|---|
| ETL-01 | Mensagens de erro de importação mostravam só a contagem agregada ("17 registros com data inválida"), sem linha/valor/sugestão — a spec pede isso explicitamente (regra 23) | `transformar()` agora rastreia até 25 exemplos por arquivo com `{linha, coluna, valor, problema, sugestão}`; linha corresponde **exatamente** à linha do Excel (testado com título + linha em branco no meio, ver `test_erro_de_validacao_aponta_a_linha_real_do_excel`) |
| ETL-02 | A confiança da identificação do arquivo (regra 22) só era exibida quando a identificação **falhava**; em caso de sucesso, o usuário não via "Confiança: 97%, Campos encontrados: ..." | `ResultadoArquivo` agora expõe `confianca_deteccao` e `campos_detectados` em todo upload, exibidos na tela de Atualização de Dados |
| ETL-03 | Não existia indicador de "Qualidade dos Dados" (regra 24) | Adicionado `qualidade_dados` (% de linhas lidas que entraram válidas), calculado e exibido por arquivo |

Todas as três corrigidas com teste de regressão dedicado; suíte completa
revalidada após cada uma (ver seção 4).

## 4. Regressão de testes

```
103 passed in ~21s   (99 pré-existentes + 4 novos desta auditoria)
```

Nenhum teste pré-existente foi removido ou alterado em sua intenção — os
99 testes da versão anterior continuam cobrindo o mesmo comportamento.
Os 4 novos cobrem exatamente as correções ETL-01 a ETL-03.

## 5. Upload real — duplicidade e atualização

Testado manualmente (além dos testes automatizados de `test_etl.py`):

1. **Primeiro upload** de `venda.xlsx` com ~3.000 linhas → todas inseridas.
2. **Reenvio do mesmo arquivo** → 0 inseridas, todas atualizadas (mesma
   chave única, nenhuma duplicata criada).
3. **Arquivo com 5 linhas duplicadas internamente** → 5 contabilizadas em
   `duplicadas_no_arquivo`, mantida a última ocorrência de cada.
4. **Coluna obrigatória ausente** → rejeitado com mensagem nomeando a coluna
   faltante, nenhuma linha entra no banco.
5. **17 datas inválidas em meio a linhas boas** → as 17 descartadas e
   contabilizadas (com exemplo de linha/valor), as demais importadas
   normalmente — status `ATENCAO`, não `ERRO`.

## 6. Segurança

| Vetor testado | Resultado |
|---|---|
| Arquivo de texto puro renomeado para `.xlsx` | Rejeitado com mensagem amigável ("não foi possível abrir"), sem stack trace exposto |
| Nome de arquivo com `../../../etc/passwd.xlsx` | Sanitizado para `passwd.xlsx` — sem escape de diretório (`Path.name` + regex de caracteres permitidos) |
| Nome de arquivo com `<script>alert(1)</script>.xlsx` | Sanitizado para `script_.xlsx` antes de tocar o disco ou aparecer em qualquer resposta |
| Limite de tamanho (50 MB) | Verificado em streaming, chunk a chunk; arquivo parcial é apagado ao estourar o limite |
| Extensão dupla (`arquivo.xlsx.exe`) | Rejeitado — só o último sufixo é considerado |
| Execução de macro/fórmula do Excel | Não ocorre — leitura via pandas/openpyxl só extrai valores |

Nenhuma vulnerabilidade encontrada nos vetores testados. Não foi executado
um scanner de dependências (`pip-audit`/`safety`) nesta sessão — recomendado
antes de publicação em produção.

## 7. Performance

Medido com ~19.000 registros carregados (12 meses de dados sintéticos,
5 bases de fatos):

| Rota | 1ª chamada (cache frio) | Chamadas seguintes (cache quente) |
|---|---:|---:|
| `/api/home` | 331 ms | 2 ms |
| `/api/modulo/equipes` | 45 ms | 2 ms |
| demais módulos (`/api/modulo/*`) | 2–4 ms | 2 ms |
| página HTML completa (`/`) | 94 ms | — |
| demais páginas HTML | 4–5 ms | — |

Nenhum gargalo identificado neste volume de dados. Não foi necessário
otimizar consultas ou adicionar agregações além do cache já existente.

## 8. Home Executiva — checklist das 10 perguntas (regra 26)

| Pergunta | Onde é respondida |
|---|---|
| Como estamos? | Cards "Total Realizado" + bloco de meta consolidada |
| Estamos atingindo a meta? | Card "% de Atingimento" com selo de status |
| Quanto falta? | Card "Falta para a Meta" |
| Qual a projeção? | Bloco de meta consolidada (`projecao`, `diferenca_projetada`) |
| Qual frente está melhor/pior? | Cards por módulo (Venda/Implantação/Termos) com status individual |
| Qual cidade precisa de atenção? | "Cidades com maior implantação" + link para página Cidades |
| Qual equipe precisa de atenção? | "Equipes com maior produção" + alerta "equipe sem produção" |
| O que está crescendo/caindo? | Insights automáticos com variação vs. mês anterior |

## 9. Critério de aprovação (regra 38) — status real

| Critério | Status |
|---|---|
| PBIX analisados | ❌ Bloqueado — arquivos indisponíveis |
| Fontes Excel identificadas | ❌ Bloqueado — arquivos indisponíveis |
| Regras principais documentadas | ✅ `docs/regras_negocio.md` |
| Indicadores comparados com PBIX | ❌ Bloqueado — arquivos indisponíveis |
| Divergências corrigidas/justificadas | ⚠️ N/A — sem comparação, não há divergência a resolver ainda |
| Excel reais testados | ❌ Bloqueado — arquivos indisponíveis |
| Upload validado | ✅ Seção 5 |
| Atualização validada | ✅ Seção 5 |
| Duplicidades testadas | ✅ Seção 5 + `test_etl.py` |
| Filtros testados | ✅ `test_indicadores.py`, `test_api.py` |
| Exportações testadas | ✅ `test_api.py` (xlsx/csv/pdf) |
| Frontend testado | ✅ Playwright: 14 páginas, SPA, filtros, tema, mobile |
| Backend testado | ✅ 103 testes automatizados |
| Testes automatizados passando | ✅ 103/103 |
| Documentação atualizada | ✅ Esta seção + README + arquitetura + indicadores + regras + matriz |

**Conclusão**: o sistema está pronto tecnicamente e coberto por testes, mas
**não pode ser declarado numericamente equivalente aos três Power BI** até
que os `.pbix` ou os Excel reais sejam disponibilizados e
`scripts/validar_indicadores.py` seja executado com `docs/referencia_powerbi.csv`
preenchido com valores reais. Isso é consistente com a regra 63 do prompt
mestre original ("não considere o projeto concluído porque a interface
abriu") e com a regra final do prompt de continuação ("não considere o
projeto concluído antes da validação real dos indicadores").

## 10. Próximo passo, quando os arquivos chegarem

```bash
# 1. Anexar os .pbix e/ou os Excel reais de origem à sessão
# 2. Abrir os três PBIX, anotar 1 mês fechado por módulo
# 3. Preencher docs/referencia_powerbi.csv com os valores lidos
python scripts/carregar_planilhas.py <excels_reais_do_mesmo_mes>
python scripts/validar_indicadores.py --ano <ano> --mes <mes>
# 4. Investigar qualquer DIVERGENTE seguindo docs/validacao_powerbi.md
# 5. Priorizar a revisão das 4 funções listadas em
#    docs/regras_negocio.md §9 — são as que mais dependem de texto livre
```
