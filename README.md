# Dashboard AEGEA — versão local simplificada

Dashboard local baseado nos três Power BI fornecidos. A interface mantém apenas
as três visões operacionais necessárias:

| Aba | Origem de referência |
|---|---|
| Venda e Implantação | `Acompanhamento Venda e Implantação.pbix` |
| Termos Aplicados | `Acompanhamento de Termos Aplicados.pbix` |
| Programação Diária | `Programação Diária.pbix` |

As medidas DAX, filtros, classificações, metas e colunas calculadas desses PBIX
são a fonte de verdade. O detalhamento está em
[`docs/referencia_powerbi_extraida.md`](docs/referencia_powerbi_extraida.md).

## Uso no Windows

Requisito: Python 3.11 ou superior.

1. Baixe ou atualize este repositório no computador.
2. Abra `scripts\CONFIGURAR_ATALHO.cmd` uma única vez.
3. Depois, use o botão **Atualizar Dashboard AEGEA** criado na Área de Trabalho.

O botão lê diretamente as pastas sincronizadas do OneDrive, atualiza o banco
SQLite no computador e abre `http://127.0.0.1:8000`. Não envia planilhas para o
Render, não solicita URL, usuário ou senha e não cria tarefa agendada.

O primeiro clique importa o histórico. Nos seguintes, um manifesto local
compara tamanho e data de modificação e processa somente arquivos novos ou
alterados. O manifesto é salvo depois de cada arquivo concluído; uma falha não
faz o processo esquecer o que já terminou.

Guia completo: [`docs/sincronizacao_pastas.md`](docs/sincronizacao_pastas.md).

## Pastas padrão

| Pasta do OneDrive | Bases reconhecidas |
|---|---|
| Atendimento | Vendas de Outros Canais |
| Faturamento | Faturamento de Termos e de Implantação |
| Interior | Venda, Implantação e Termos |
| Programação Diária | Programação Diária |

Arquivos temporários do Excel (`~$...`) são ignorados. Cada arquivo físico é
lido uma única vez por execução e somente as abas compatíveis são carregadas.

## Medidas principais preservadas

- Venda Comercial e Venda VCG: atividade `Venda Potenciais/Factíveis`, status
  `Finalizada` e as mesmas exclusões de códigos/recursos do PBIX.
- Implantação: atividade `Ligação de Água`, status `Finalizada` e a mesma
  classificação de frentes do PBIX.
- Termos: códigos `110013`/`210013` para Serviços e `310013` para VCG, com os
  mesmos filtros de recurso e status.
- Programação: `Eqp_Geral`, região e Projeto Principal reproduzem as colunas
  calculadas do PBIX.
- Metas padrão do modelo: Implantação 422 (Serviços 234, VCG 188) e Termos 430
  (Serviços 250, VCG 180). Uma planilha de metas explícita tem prioridade.

## Desenvolvimento

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload
```

Estrutura principal:

```text
app/etl/regras_powerbi.py             regras extraídas dos PBIX
scripts/atualizar_dashboard_local.py atualização incremental local
scripts/ATUALIZAR_DASHBOARD.cmd       alvo do atalho do Windows
data/local/                           banco e manifesto locais (não versionados)
```

O dicionário das colunas aceitas também está disponível em `GET /api/datasets`.
