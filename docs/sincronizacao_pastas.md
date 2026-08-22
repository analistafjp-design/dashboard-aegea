# Sincronização automática das pastas (Windows)

Faz o dashboard se atualizar sozinho a partir das mesmas pastas que você já
usa hoje para guardar as planilhas — sem precisar abrir o navegador toda
vez. Um script roda em segundo plano no seu computador e envia qualquer
arquivo novo ou alterado para o dashboard, de tempos em tempos.

## Antes de começar

Você precisa de três coisas:

1. **A URL do seu dashboard** (ex.: `https://dashboard-executivo.onrender.com`).
2. **Usuário e senha do login**, se você configurou (ver
   [`deploy.md`](deploy.md) — variáveis `AUTH_USUARIO`/`AUTH_SENHA` no
   Render). Se ainda não configurou login, tudo bem, o script funciona sem.
3. **Os caminhos das pastas** onde você guarda as planilhas de Termos,
   Venda/Implantação e Programação.

## Passo a passo

### 1. Baixar os scripts no seu computador

Se você já clonou o repositório para rodar localmente, os scripts já estão
em `scripts/`. Se não, baixe pelo menos a pasta `scripts/` do repositório
`dashboard-aegea` (branch `claude/novo-projeto-independente-ao910q`) para
uma pasta no seu PC, por exemplo `C:\DashboardExecutivo\scripts`.

### 2. Configurar as pastas monitoradas

Na pasta `scripts`, copie o arquivo **`pastas-monitoradas.exemplo.txt`** e
renomeie a cópia para **`pastas-monitoradas.txt`**. Abra com o Bloco de
Notas e coloque uma pasta por linha, com o caminho completo.

**Funciona com OneDrive e Google Drive**: a pasta sincronizada deles é uma
pasta normal no seu PC, então basta apontar para ela — não precisa de
senha nem configuração extra. Arquivos que estejam "somente na nuvem"
(Arquivos Sob Demanda) são baixados automaticamente na hora da leitura; a
primeira sincronização pode demorar mais por causa disso, e o script avisa
no log quando encontra esse caso.

Você pode fixar a base de cada pasta acrescentando `= base` no fim da
linha — é o mesmo efeito de escolher a aba na tela de Atualização de
Dados, e evita depender da identificação automática.

Uma pasta pode alimentar **várias bases de uma vez**, separando por
vírgula: os arquivos são enviados uma vez para cada base. É o caso de uma
pasta cujas planilhas servem para Venda, Implantação e Termos ao mesmo
tempo:

```text
...\DashBoard - Interior\Interior = vendas, implantacao, termos
...\DashBoard - Interior\Faturamento = faturamento
...\DashBoard - Interior\Programação Diaria = programacao
```

Bases aceitas: `termos`, `faturamento`, `vendas`, `implantacao`,
`programacao`, `metas`. Sem o `= base`, o sistema identifica pelas colunas
do arquivo.

O controle do que já foi enviado é feito **por arquivo e por base**: o
mesmo arquivo enviado para Venda continua pendente para Implantação e
Termos até que cada uma receba a sua cópia.

**Dica para pegar o caminho certo**: abra a pasta no Explorer do Windows,
clique uma vez na barra de endereço no topo (o texto fica selecionado em
azul), aperte Ctrl+C, e cole (Ctrl+V) no Bloco de Notas.

O script entra em subpastas automaticamente — não precisa listar
"Atendimento", "Interior" e "Faturamento" separadamente se elas já estão
dentro de uma das pastas que você listou.

### 3. Configurar o login (se o dashboard tiver senha)

Copie **`credenciais.exemplo.txt`** para **`credenciais.txt`** e preencha:

```text
USUARIO=admin
SENHA=a-senha-que-voce-configurou-no-render
```

Se o dashboard não tiver login, deixe os dois valores em branco
(`USUARIO=` e `SENHA=`).

> Esse arquivo fica só no seu computador — nunca é enviado para o Git.

### 4. Testar uma vez, manualmente

Clique com o botão direito em **`sincronizar_pastas.ps1`** → **Executar com
o PowerShell**. (Se aparecer um aviso azul de "Windows protegeu o
computador", clique em "Mais informações" → "Executar assim mesmo" — é
normal para scripts baixados da internet, o Windows só está avisando que
não reconhece quem assinou o arquivo.)

Uma janela preta abre, mostra o que está acontecendo e fecha sozinha (ou
fica aberta, dependendo de como você executou — pode fechar depois). Se
tudo deu certo, você verá linhas como:

```text
2026-08-22 09:03:01 | INFO    | Encontrados 6 arquivo(s) em 3 local(is) monitorado(s).
2026-08-22 09:03:02 | INFO    | Enviando 6 arquivo(s) para .../api/upload ...
2026-08-22 09:03:04 | INFO    | Resposta do servidor: Dashboard atualizado: 6 registro(s) de 6 arquivo(s).
2026-08-22 09:03:04 | INFO    | Sincronizacao concluida com sucesso.
```

Se aparecer `ERRO`, leia a mensagem — ela é escrita em português e diz
exatamente o que verificar (URL errada, senha errada, pasta não
encontrada...). O mesmo texto fica guardado em `scripts\logs\`.

> **Primeira execução com muito histórico**: se suas pastas já têm meses de
> planilhas acumuladas (dezenas ou centenas de arquivos), essa primeira
> sincronização é a única que envia tudo — as próximas só mandam o que for
> novo ou mudar (ver seção abaixo). Pode demorar alguns minutos; é normal.

### 5. Ligar a sincronização automática

Depois que o teste manual funcionar, clique com o botão direito em
**`instalar_agendamento.ps1`** → **Executar com o PowerShell**. Isso roda
**uma única vez** e configura o Agendador de Tarefas do Windows para
chamar `sincronizar_pastas.ps1` sozinho a cada 15 minutos, enquanto você
estiver logado no computador — não precisa administrador.

Pronto. De agora em diante, sempre que você salvar uma planilha atualizada
numa das pastas monitoradas, em até 15 minutos ela aparece no dashboard.

Para mudar o intervalo (por exemplo, a cada 30 minutos), abra o PowerShell
na pasta `scripts` e rode:

```powershell
.\instalar_agendamento.ps1 -IntervaloMinutos 30
```

### 6. Desligar, se precisar

Clique com o botão direito em **`remover_agendamento.ps1`** → **Executar
com o PowerShell**. Isso só desliga o agendamento — nenhum dado já enviado
ao dashboard é apagado.

## Como funciona por trás dos panos

- **Envio incremental**: o script guarda um "manifesto" local
  (`logs\manifesto_sincronizacao.json`) com o tamanho e a data de
  modificação de cada arquivo já enviado. A cada execução, só envia o que é
  **novo ou mudou** desde a última vez — se nada mudou, ele nem chega a
  contatar o servidor. Isso é o que permite monitorar pastas com centenas
  de planilhas históricas (uma por dia, por exemplo) sem reenviar tudo a
  cada 15 minutos.
- **Envio em lotes**: quando há muitos arquivos para enviar (ex.: a
  primeira sincronização, com meses de histórico), eles vão em grupos de
  até 20 arquivos ou 40 MB por vez — não tudo numa única requisição gigante,
  que poderia travar em conexões mais lentas.
- Arquivos temporários do Excel (que começam com `~$`, criados enquanto
  alguém tem a planilha aberta) são ignorados automaticamente.
- Se um arquivo estiver aberto/travado no momento exato da sincronização,
  ele é pulado com um aviso no log — e enviado normalmente na próxima
  rodada, sem intervenção sua.
- O tipo de cada planilha (Termos, Venda, Implantação...) é identificado
  automaticamente pelas colunas, igual ao upload manual pelo navegador.

### Forçar um reenvio completo

Às vezes você precisa reenviar tudo de novo, ignorando o manifesto — por
exemplo, se desconfia que a instância gratuita do Render "dormiu" e perdeu
os dados (ver aviso abaixo). Abra o PowerShell na pasta `scripts` e rode:

```powershell
.\sincronizar_pastas.ps1 -Completo
```

Como o dashboard nunca duplica um registro reenviado (identifica cada linha
por uma chave própria — data, cidade, equipe, etc.), reenviar tudo é sempre
seguro, só demora mais.

## ⚠️ Sobre o plano gratuito do Render

Como o [`deploy.md`](deploy.md) já explica: no plano Free, a instância
"dorme" após ~15 minutos sem acesso e perde os dados ao acordar. Diferente
da primeira versão deste script, a sincronização automática **não repõe
isso sozinha a cada ciclo** (agora ela só envia o que mudou, para não
sobrecarregar pastas com muito histórico) — então, se desconfiar que a
instância dormiu e perdeu dados, rode manualmente:

```powershell
.\sincronizar_pastas.ps1 -Completo
```

Para acompanhamento operacional sério, sem se preocupar com isso, o ideal é
migrar para um plano com persistência (disco pago ou Postgres — ver
`deploy.md`), que elimina o problema por completo.

## Onde os arquivos ficam

```text
scripts/
├── sincronizar_pastas.ps1          script principal
├── instalar_agendamento.ps1        liga a sincronização automática
├── remover_agendamento.ps1         desliga a sincronização automática
├── pastas-monitoradas.exemplo.txt  modelo — copie e edite
├── pastas-monitoradas.txt          suas pastas reais (você cria, não vai para o Git)
├── credenciais.exemplo.txt         modelo — copie e edite
├── credenciais.txt                 seu usuário/senha reais (você cria, não vai para o Git)
└── logs/
    ├── sincronizacao_AAAAMMDD.log      um arquivo de log por dia (criado automaticamente)
    └── manifesto_sincronizacao.json    controle do que já foi enviado (criado automaticamente)
```
