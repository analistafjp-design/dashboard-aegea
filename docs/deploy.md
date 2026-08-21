# Publicar o Dashboard com URL pública (Render)

Passo a passo para colocar o sistema no ar em https://render.com, plano
gratuito, para visualização e demonstração.

## 1. Conectar o Render ao GitHub

1. Crie uma conta em https://render.com (dá para entrar direto com GitHub).
2. No painel, clique em **New +** → **Blueprint**.
3. Autorize o Render a acessar sua conta/organização `analistafjp-design`
   no GitHub, se ainda não tiver feito isso.
4. Selecione o repositório **`dashboard-aegea`**.

## 2. Deploy

O Render encontra automaticamente o arquivo `render.yaml` na raiz do
repositório e propõe criar o serviço `dashboard-executivo` já configurado
(build, start, variáveis de ambiente). Só confirme em **Apply**.

O primeiro build leva de 2 a 5 minutos. Quando terminar, o Render mostra a
URL pública, algo como:

```
https://dashboard-executivo.onrender.com
```

Essa URL já funciona no navegador, celular, etc. — sem precisar instalar
nada.

## 3. Importar os dados

O deploy sobe com o banco **vazio**. Acesse a URL, vá em
**Atualização de Dados** e envie as planilhas (ou gere dados de exemplo
localmente com `python scripts/gerar_dados_exemplo.py` e suba os arquivos
gerados em `data/exemplos/`, só para ver o dashboard funcionando).

## ⚠️ Sobre persistência de dados no plano Free

O plano **Free** do Render **não tem disco persistente**. A instância
"dorme" depois de ~15 minutos sem acesso e, ao acordar (na próxima
requisição), sobe um container novo e limpo — **o banco SQLite e os
uploads são perdidos**. Isso é normal e esperado no plano gratuito.

- **Serve para**: mostrar o dashboard funcionando, testar telas, validar
  com a equipe antes de decidir usar de verdade.
- **Não serve para**: manter dados operacionais reais entre reinícios.

### Para uso operacional real, escolha uma das opções:

| Opção | O que fazer | Custo aproximado |
|---|---|---|
| Disco persistente | Trocar `plan: free` para `starter` no `render.yaml` e descomentar o bloco `disk:` | ~US$ 7/mês (plano) + disco |
| Banco Postgres gerenciado | Descomentar o bloco `databases:` e a variável `DATABASE_URL` no `render.yaml`; o app já suporta Postgres nativamente (SQLAlchemy) | Free por 30 dias, depois pago |
| Rodar localmente/servidor próprio | Ver `README.md` — sem custo de hospedagem, dado fica no seu disco | Grátis |

## 4. Atualizando o deploy depois de um novo `git push`

O Render reimplanta automaticamente a cada push na branch configurada em
`render.yaml` (`branch:`). Não é necessário nenhum passo manual.

Quando o PR #1 for mesclado na `main`, edite `render.yaml` trocando
`branch: claude/novo-projeto-independente-ao910q` para `branch: main` (ou
remova a linha — o Render usa a branch padrão do repositório por padrão) e
reconecte o serviço a essa branch nas configurações do Render.
