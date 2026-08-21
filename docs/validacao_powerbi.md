# Conferência Power BI × Python

## Situação atual

Os três arquivos `.pbix` de referência **continuam não disponibilizados**
— confirmado em duas sessões de trabalho distintas (desenvolvimento inicial
e a auditoria registrada em `relatorio_final_validacao.md`), a mais recente
tendo verificado ativamente que nenhum `.pbix` nem Excel real de origem
existe em qualquer diretório acessível a esta sessão. Apenas a especificação
com os nomes das medidas foi fornecida. Por isso:

1. As regras foram reconstruídas a partir dos nomes de medidas, campos e
   filtros citados na especificação e estão documentadas, campo a campo, em
   [`indicadores.md`](indicadores.md) (visão por indicador) e
   [`regras_negocio.md`](regras_negocio.md) (visão por função de código,
   com a lógica exata implementada);
2. **Nenhum número foi inventado**: sem dados importados o dashboard mostra
   "Sem dados"; sem meta cadastrada mostra "Meta não cadastrada";
3. A ferramenta de conferência está pronta, testada com valores simulados
   (ver exemplo abaixo) e deve ser executada assim que os números dos PBIX
   estiverem em mãos.

Enquanto a conferência não for feita, considere o projeto **funcionalmente
completo, testado e auditado — porém pendente de validação numérica**. Veja
o status detalhado, item a item, em
[`relatorio_final_validacao.md`](relatorio_final_validacao.md).

## Como executar a conferência

1. Abra os três PBIX e escolha **um mês já fechado** (evita diferença por dado
   parcial).
2. Importe no dashboard as planilhas do mesmo período.
3. Preencha `docs/referencia_powerbi.csv`: coluna `valor_powerbi` com o número
   lido no PBIX e as colunas `ano`/`mes` com o período.
4. Rode:

```bash
python scripts/validar_indicadores.py --ano 2026 --mes 7
```

Saída:

```text
INDICADOR                             POWER BI       PYTHON    DIFERENÇA  STATUS
----------------------------------------------------------------------------------
total_venda                              1.240        1.240            0  OK
total_implantacao                          853          853            0  OK
qtd_faturado                               620          618           -2  DIVERGENTE
```

O script devolve código de saída `2` quando há divergência, o que permite usá-lo
em rotina automatizada.

## O que fazer diante de uma divergência

Não ignore. Siga a ordem:

1. **Período** — o PBIX está no mesmo mês e com os mesmos filtros de tela?
2. **Escopo de linhas** — o PBIX filtra algum status que o Python não filtra
   (por exemplo, termos cancelados fora do realizado)?
3. **Classificação** — Serviços × VCG está caindo na mesma frente? Confira a
   coluna que alimenta `tipo` na planilha.
4. **Duplicidade** — a chave única do dataset está descartando linhas que o
   PBIX conta? Veja o campo `duplicadas_no_arquivo` no histórico de importação.
5. **Meta** — a meta cadastrada é a mesma do PBIX, no mesmo segmento?

Achada a causa, ajuste a regra no módulo correspondente de `app/analytics/`,
registre a mudança em `indicadores.md` e rode `pytest` antes de reconferir.

## Registro das conferências

| Data | Período | Indicadores conferidos | Divergências | Responsável |
|---|---|---|---|---|
| _(preencher)_ | | | | |
