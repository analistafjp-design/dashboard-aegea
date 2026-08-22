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

## Como o upload funciona (e por que ele não trava a instância)

Processar planilha é trabalho pesado e demorado, ainda mais nos **0.1 de
CPU** do plano gratuito. Por isso o upload é feito em duas partes:

1. `POST /api/upload` só **grava os arquivos em disco** e devolve na hora um
   `trabalho_id` (resposta HTTP 202). É rápido mesmo com muitos arquivos.
2. O processamento roda numa **thread separada**, um arquivo por vez, com
   uma sessão de banco por arquivo. A tela acompanha em
   `GET /api/upload/{trabalho_id}` e mostra progresso real ("arquivo 3 de
   12").

Isso não é preciosismo: se o processamento acontecesse dentro da
requisição, ele bloquearia o event loop e o servidor pararia de responder
**tudo** enquanto durasse — inclusive o health check (`/api/status`) que o
Render usa para saber se a instância está viva. O Render então mata e
reinicia o container no meio do upload, e o navegador mostra "Falha de
comunicação com o servidor" (ou 502 em qualquer outra página aberta na
mesma hora). Foi exatamente esse o comportamento observado antes desta
mudança.

Efeito colateral bom: como cada arquivo tem a própria sessão de banco, a
memória fica **constante** ao longo do lote em vez de crescer a cada
arquivo, e um arquivo já processado não se perde se algo falhar depois.

## ⚠️ Sobre memória (RAM) no plano Free

O plano **Free** do Render tem só **512 MB de RAM**. A aplicação sozinha
(FastAPI + pandas + SQLAlchemy) já usa cerca de **115 MB** só de subir;
processar um arquivo Excel consome mais memória proporcional ao número de
linhas — na prática, em torno de **140 MB a cada 60 mil linhas**. Um
arquivo com centenas de milhares de linhas pode estourar os 512 MB durante
o processamento, o que derruba o processo no meio do upload (a instância
reinicia sozinha e aparece "502 Bad Gateway" no navegador).

Para lidar com isso sem recusar nada, um arquivo `.xlsx`/`.xlsm` acima de
**100.000 linhas** (`LIMITE_LINHAS_ARQUIVO`) deixa de ser lido de uma vez e
passa a ser processado **em blocos** de 20.000 linhas
(`LINHAS_POR_BLOCO`), gravando cada bloco antes de ler o próximo. Assim a
memória fica constante independentemente do tamanho do arquivo: medido com
um arquivo real de 152.934 linhas (16,8 MB), o pico foi de **240 MB** —
bem dentro dos 512 MB — e as 152.934 linhas foram importadas por completo.

Os arquivos de um mesmo envio também são processados **um a um**, cada um
com a própria sessão de banco, então o consumo não cresce com a quantidade
de arquivos.

Restrições que continuam valendo:

- **CSV** acima do limite ainda é recusado (a leitura em blocos hoje cobre
  só `.xlsx`/`.xlsm`). Converta para Excel ou divida o arquivo.
- Arquivo acima de `TAMANHO_MAXIMO_MB` (50 MB) segue recusado no upload.

Se um arquivo for recusado por tamanho:

- **Divida o arquivo** em partes menores (por mês, por cidade etc.) e
  envie cada parte separadamente — reenviar não duplica nada, cada linha
  é identificada pela própria chave (data, cidade, equipe...).
- **Ou migre para um plano com mais RAM** no Render (os planos pagos
  chegam a 2 GB+) e aumente `LIMITE_LINHAS_ARQUIVO` de acordo.

## 5. Atualizando o deploy depois de um novo `git push`

O Render reimplanta automaticamente a cada push na branch configurada em
`render.yaml` (`branch:`). Não é necessário nenhum passo manual.

O `render.yaml` acompanha a branch `main`. Depois que o PR #1 for mesclado,
confirme uma única vez em **Settings > Build & Deploy > Branch** que o serviço
também aponta para `main`. A partir daí, cada novo push nessa branch inicia um
deploy automático.

## 6. Próximo passo: atualização automática das planilhas

Em vez de enviar os arquivos manualmente pelo navegador toda vez, dá para
automatizar a partir das mesmas pastas que você já usa hoje — ver
[`sincronizacao_pastas.md`](sincronizacao_pastas.md).
