# Arquitetura

```text
USUÁRIO
   ↓  navegador
UPLOAD DOS EXCELS ──► app/services/upload.py        (extensão, tamanho, nome)
   ↓
VALIDAÇÃO         ──► app/etl/leitura.py            (abre a planilha, acha o cabeçalho)
   ↓
IDENTIFICAÇÃO     ──► app/etl/deteccao.py           (qual base é, pelas colunas)
   ↓
TRATAMENTO        ──► app/etl/transformacao.py      (tipos, domínios, duplicidade)
   ↓
BANCO DE DADOS    ──► app/etl/carga.py              (carga incremental por chave única)
   ↓
REGRAS DE NEGÓCIO ──► app/analytics/*.py            (metas, ritmo, projeção, status)
   ↓
INDICADORES/API   ──► app/routes/api.py             (JSON)
   ↓
GRÁFICOS / HOME   ──► frontend/static/js + Plotly
```

## Camadas

| Camada | Pasta | Responsabilidade |
|---|---|---|
| Configuração | `app/config.py` | Caminhos, limites, banco, cache |
| Persistência | `app/models/` | Modelo dimensional e sessão SQLAlchemy |
| ETL | `app/etl/` | Ler, identificar, validar, transformar e carregar |
| Análise | `app/analytics/` | Indicadores, metas, projeções, insights, alertas |
| Serviços | `app/services/` | Upload, exportação, preferências |
| Rotas | `app/routes/` | Páginas HTML e API JSON |
| Frontend | `frontend/` | Templates Jinja2, CSS e JS (Plotly local) |

## Modelo de dados

Esquema estrela: dimensões compartilhadas + **uma tabela fato por módulo**.
Os três módulos nunca compartilham a mesma tabela de fatos.

```text
dim_calendario   dim_cidade   dim_equipe   dim_frente   dim_regiao   dim_projeto   dim_setor
        │             │            │            │            │            │           │
        └─────────────┴────────────┴────────────┴────────────┴────────────┴───────────┘
                                        │
        ┌───────────────┬───────────────┼────────────────┬──────────────────┐
   fato_termos   fato_faturamento   fato_vendas   fato_implantacao   fato_programacao
                                        │
                              metas          historico_uploads          configuracoes
```

## Carga incremental

Cada fato tem uma `chave_unica` derivada das colunas de negócio:

| Base | Chave única |
|---|---|
| Termos | data + matrícula + tipo + equipe |
| Faturamento | data + nº do termo + situação + cidade |
| Venda | data + matrícula + frente + equipe |
| Implantação | data + matrícula + serviço + equipe |
| Programação | data + região + recurso + projeto |
| Metas | ano + mês + módulo + segmento + cidade + equipe |

Registro existente é **atualizado**; registro novo é **inserido**. Reenviar o
mesmo arquivo não duplica nada — é o caminho normal de correção de dados.

## Cache

Cache em memória com versionamento: toda carga chama `cache.invalidar()`,
o que zera as entradas e incrementa a versão. O dashboard nunca devolve número
anterior ao último upload. O TTL (`CACHE_TTL`, padrão 300 s) é apenas um limite
adicional para instâncias com múltiplos processos.

## Erros

`ErroDashboard` e suas filhas carregam mensagem pronta em português. Qualquer
exceção não prevista é registrada no log (`data/logs/dashboard.log`) com stack
trace completo e devolvida à interface como mensagem genérica — o usuário final
nunca vê traceback.

## Publicação em servidor

O sistema roda com qualquer servidor ASGI:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Para vários workers, aponte `DATABASE_URL` para PostgreSQL:

```bash
DATABASE_URL=postgresql+psycopg://usuario:senha@servidor:5432/dashboard
```

Nenhuma outra alteração de código é necessária — o modelo é SQLAlchemy puro.
