# Dashboard Executivo

Plataforma web que consolida, em um único sistema, as informações hoje
distribuídas em três arquivos Power BI:

| Módulo | Origem | Páginas |
|---|---|---|
| **Termos / Faturamento** | PBIX 1 | Termos Aplicados · Faturamento de Termos |
| **Venda / Implantação** | PBIX 2 | Venda · Implantação |
| **Programação** | PBIX 3 | Programação Diária |

Os três módulos permanecem **independentes** — nada é misturado sem regra
explícita. Acima deles há uma **Home Executiva** que responde, em menos de 30
segundos: como estamos, quanto falta, o que projeta fechar e onde está o problema.

A atualização é feita **enviando as planilhas pelo navegador**. Ninguém precisa
editar código Python para atualizar os dados.

---

## Instalação

Requisito: **Python 3.11 ou superior**.

### Linux / macOS

```bash
git clone https://github.com/analistafjp-design/dashboard-aegea.git
cd dashboard-aegea
./scripts/iniciar.sh
```

### Windows

```bat
git clone https://github.com/analistafjp-design/dashboard-aegea.git
cd dashboard-aegea
scripts\iniciar.bat
```

O script cria o ambiente virtual, instala as dependências e sobe o servidor.
Abra **http://127.0.0.1:8000**.

### Instalação manual

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Configuração opcional: copie `.env.example` para `.env` e ajuste (banco,
limite de upload, pasta de dados). O sistema funciona sem nenhuma variável.

---

## Primeiro uso

1. Abra **Atualização de Dados** na barra lateral.
2. Arraste as planilhas (Termos, Faturamento, Venda, Implantação, Programação
   e Metas) — o tipo de cada base é identificado **pelas colunas**, não pelo
   nome do arquivo.
3. Clique em **ATUALIZAR DASHBOARD**.
4. Indicadores, gráficos, rankings, projeções, alertas e insights são
   recalculados automaticamente.

### Quer ver o sistema funcionando antes de ter os dados reais?

```bash
python scripts/gerar_dados_exemplo.py       # cria planilhas sintéticas em data/exemplos
python scripts/carregar_planilhas.py data/exemplos/*.xlsx
```

> Os dados de exemplo são **sintéticos**, servem apenas para demonstração e
> teste. Antes de usar em produção, limpe a base:
> `python scripts/carregar_planilhas.py --limpar <suas_planilhas>`

---

## Páginas

| Página | O que responde |
|---|---|
| **Visão Executiva** | Como estamos, quanto falta, projeção, principais problemas e oportunidades |
| **Termos Aplicados** | Realizado Total / Serviços / VCG, meta, ritmo, distribuição por cidade e setor |
| **Faturamento de Termos** | Negociação, aguardando, faturado, cancelado, funil e conversão |
| **Venda** | Total, Comercial, VCG, outros canais, venda/dia, falta, rankings |
| **Implantação** | Serviços × VCG × Total, faturada e não faturada, valor, evolução |
| **Programação Diária** | Agenda operacional, O.S. e equipes por dia, carga e desequilíbrios |
| **Equipes** | Tabela executiva, equipes logadas, ranking e produção diária |
| **Cidades** | Ranking por módulo e cidades abaixo da meta (clique filtra o dashboard) |
| **Metas** | Meta, meta acumulada, ritmo necessário, projeção e metas cadastradas |
| **Análises** | Insights automáticos, comparação com período anterior e projeções |
| **Alertas** | 🔴 crítico · 🟡 atenção · 🟢 normal |
| **Atualização de Dados** | Upload, validação, progresso e histórico de importações |
| **Configurações** | Tema, período padrão, exportação e informações do sistema |
| **Dicionário de dados** | Todas as colunas aceitas em cada planilha |

Todas as páginas respeitam os **filtros globais** (período, ano, mês, cidade,
frente, equipe, região, projeto) e permitem exportar em **Excel, CSV ou PDF**.

---

## Planilhas aceitas

O sistema identifica a base pela **estrutura das colunas** e aceita variações
de cabeçalho ("Data da Atividade", "Data", "Dt. Atividade" caem no mesmo campo).
A lista completa de sinônimos está na página **Dicionário de dados** e em
`GET /api/datasets`.

| Base | Colunas obrigatórias | Colunas opcionais mais usadas |
|---|---|---|
| Termos Aplicados | data | cidade, equipe/recurso, frente, setor do recurso, matrícula, tipo, status do termo, quantidade, valor |
| Faturamento de Termos | data (início do mês), situação | cidade, nº do termo, quantidade, valor |
| Venda | data, canal/frente | cidade, equipe, matrícula, quantidade, valor |
| Implantação | data | cidade, equipe, frente, tipo, serviço, situação de faturamento, quantidade, valor |
| Programação Diária | data, região, recurso, qtd O.S. | projeto, cidade |
| Metas | ano, mês, indicador/módulo, meta | segmento/tipo, cidade, equipe |

**Metas nunca são estimadas.** Sem cadastro, o dashboard exibe
*"Meta não cadastrada"* em vez de um número inventado.

---

## Como o sistema trata dados problemáticos

| Situação | Comportamento |
|---|---|
| Coluna obrigatória ausente | `Arquivo incompatível com a base Venda. A coluna 'frente' não foi encontrada.` |
| Datas inválidas | `17 registro(s) com data inválida em 'data' (descartado)` — as demais linhas entram |
| Linhas duplicadas | Removidas pela chave única e reportadas no relatório |
| Reenvio do mesmo arquivo | Atualiza os registros existentes; **não duplica** |
| Base sem registros no filtro | Mostra **"Sem dados"** — nunca zero |
| Erro inesperado | Mensagem amigável na tela; stack trace só no log |

---

## Testes

```bash
.venv/bin/python -m pytest
```

103 testes cobrindo calendário e dias úteis, conversão de tipos, detecção de
arquivos, importação (duplicidade, datas inválidas, coluna ausente, carga
incremental, número exato da linha com erro no Excel), regras de indicadores
(meta, atingimento, projeção, "sem dados" × zero), API, upload, exportação e
todas as páginas.

---

## Conferência com o Power BI

Antes de considerar os números definitivos, compare-os com os PBIX:

```bash
# 1. preencha docs/referencia_powerbi.csv com os valores lidos no Power BI
# 2. rode a conferência
python scripts/validar_indicadores.py --ano 2026 --mes 7
```

O procedimento completo e o que fazer diante de divergências estão em
[`docs/validacao_powerbi.md`](docs/validacao_powerbi.md).

---

## Estrutura do projeto

```text
dashboard-aegea/
├── app/
│   ├── main.py                 aplicação FastAPI
│   ├── config.py               caminhos, limites, banco, cache
│   ├── models/                 modelo dimensional (SQLAlchemy) e sessão
│   ├── etl/                    leitura, detecção, validação, carga incremental
│   ├── analytics/              indicadores, metas, projeções, insights, alertas
│   ├── services/               upload, exportação, preferências
│   ├── routes/                 páginas HTML e API JSON
│   ├── schemas/                filtros da query string
│   └── utils/                  logs, erros, formatação, texto
├── frontend/
│   ├── templates/              base.html + uma página por rota
│   └── static/                 css, js (Plotly local), ícones
├── data/                       uploads, processados, banco e logs (não versionados)
├── docs/                       indicadores, regras de negócio, arquitetura, validação Power BI
├── scripts/                    iniciar, carregar planilhas, validar, dados de exemplo
├── tests/                      suíte pytest
├── requirements.txt
└── .env.example
```

## Documentação

- [Dicionário de indicadores](docs/indicadores.md) — regra de cada número, com referência ao PBIX
- [Mapa de regras de negócio](docs/regras_negocio.md) — a lógica exata implementada, ligada ao código-fonte
- [Matriz de dados real](docs/matriz_dados_real.csv) — toda coluna aceita em cada planilha, gerada a partir do código
- [Arquitetura](docs/arquitetura.md) — camadas, modelo de dados, publicação
- [Conferência Power BI](docs/validacao_powerbi.md) — como validar os números
- [Relatório final de validação](docs/relatorio_final_validacao.md) — status real de cada critério de aprovação
- API interativa: **http://127.0.0.1:8000/api/docs**

> **Status de validação**: o sistema está funcional, testado (103 testes
> automatizados) e auditado, mas a comparação numérica com os três Power BI
> originais está pendente — os arquivos `.pbix` e os Excel reais ainda não
> foram disponibilizados. Veja o relatório final de validação para o
> detalhamento completo.

---

## Publicação em servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Com mais de um worker, use PostgreSQL:

```bash
DATABASE_URL=postgresql+psycopg://usuario:senha@servidor:5432/dashboard
```

Nenhuma dependência do Power BI é necessária para executar o dashboard.
Os PBIX servem apenas como referência das regras de negócio.
