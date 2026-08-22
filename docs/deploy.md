# Publicar o Dashboard com URL pública (Render)

Passo a passo para colocar o sistema no ar em https://render.com, plano
gratuito, para visualização e demonstração.

## 1. Conectar o Render ao GitHub

1. Crie uma conta em https://render.com (dá para entrar direto com GitHub).
2. No painel, clique em **New +** → **Blueprint**.
3. Autorize o Render a acessar sua conta/organização `analistafjp-design`
   no GitHub, se ainda não tiver feito isso.
4. Selecione o repositório **`dashboard-aegea`**.

## 2. Definir o login (obrigatório — a URL é pública)

Antes de clicar em **Deploy Blueprint**, o Render mostra dois campos para
preencher porque `render.yaml` os marca como segredo (`sync: false`):

| Variável | O que colocar |
|---|---|
| `AUTH_USUARIO` | Um nome de usuário à sua escolha (ex.: `admin`) |
| `AUTH_SENHA` | Uma senha forte à sua escolha |

**Sem isso, qualquer pessoa com o link consegue ver os dados da empresa e
até enviar arquivos** — o dashboard não tem outra proteção. Preencha os
dois campos antes de continuar. Guarde essa senha: você vai usá-la para
entrar pelo navegador e também no script de sincronização automática (ver
[`sincronizacao_pastas.md`](sincronizacao_pastas.md)).

Se algum dia quiser trocar a senha, edite as duas variáveis em
**Environment**, na página do serviço no painel do Render — o Render
reimplanta sozinho depois de salvar.

## 3. Deploy

Clique em **Deploy Blueprint**. O Render cria o serviço `dashboard-executivo`
já configurado (build, start, variáveis de ambiente, login).

O primeiro build leva de 2 a 5 minutos. Quando terminar, o Render mostra a
URL pública, algo como:

```
https://dashboard-executivo.onrender.com
```

Essa URL já funciona no navegador, celular, etc. — sem precisar instalar
nada. Ao abrir, o navegador pede o usuário/senha que você definiu no
passo 2.

## 4. Importar os dados

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

## ⚠️ Sobre memória (RAM) no plano Free

O plano **Free** do Render tem só **512 MB de RAM**. A aplicação sozinha
(FastAPI + pandas + SQLAlchemy) já usa cerca de **115 MB** só de subir;
processar um arquivo Excel consome mais memória proporcional ao número de
linhas — na prática, em torno de **140 MB a cada 60 mil linhas**. Um
arquivo com centenas de milhares de linhas pode estourar os 512 MB durante
o processamento, o que derruba o processo no meio do upload (a instância
reinicia sozinha e aparece "502 Bad Gateway" no navegador).

Para evitar isso, o sistema **recusa educadamente** (antes de gastar
memória lendo o arquivo inteiro) qualquer planilha com mais de
**100.000 linhas** — o limite fica configurável pela variável de ambiente
`LIMITE_LINHAS_ARQUIVO`, caso o plano seja outro com mais RAM. A mesma
verificação também soma as linhas de **todos os arquivos enviados juntos**
numa mesma atualização: vários arquivos pequenos processados na mesma
requisição consomem memória da mesma forma que um arquivo grande, então o
lote inteiro é recusado se a soma passar do limite, mesmo que nenhum
arquivo sozinho ultrapasse — nesse caso, envie em lotes menores (poucos
arquivos por vez). Se um arquivo ou lote for recusado por esse motivo:

- **Divida o arquivo** em partes menores (por mês, por cidade etc.) e
  envie cada parte separadamente — reenviar não duplica nada, cada linha
  é identificada pela própria chave (data, cidade, equipe...).
- **Ou migre para um plano com mais RAM** no Render (os planos pagos
  chegam a 2 GB+) e aumente `LIMITE_LINHAS_ARQUIVO` de acordo.

## 5. Atualizando o deploy depois de um novo `git push`

O Render reimplanta automaticamente a cada push na branch configurada em
`render.yaml` (`branch:`). Não é necessário nenhum passo manual.

Quando o PR #1 for mesclado na `main`, edite `render.yaml` trocando
`branch: claude/novo-projeto-independente-ao910q` para `branch: main` (ou
remova a linha — o Render usa a branch padrão do repositório por padrão) e
reconecte o serviço a essa branch nas configurações do Render.

## 6. Próximo passo: atualização automática das planilhas

Em vez de enviar os arquivos manualmente pelo navegador toda vez, dá para
automatizar a partir das mesmas pastas que você já usa hoje — ver
[`sincronizacao_pastas.md`](sincronizacao_pastas.md).
