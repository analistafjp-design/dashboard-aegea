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
Notas e coloque uma pasta por linha, com o caminho completo — por exemplo,
baseado nas suas pastas atuais:

```text
C:\Users\SeuUsuario\Documents\Acompanhamento Venda e Implantação
C:\Users\SeuUsuario\Documents\Acompanhamento de Termos Aplicados - Versão
C:\Users\SeuUsuario\Documents\Programação Interior
```

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

- A cada execução, o script **reenvia todos** os arquivos das pastas
  monitoradas (não só os que mudaram). Isso é proposital: o dashboard
  identifica cada linha por uma chave própria (data + cidade + equipe, por
  exemplo) e nunca duplica um registro reenviado — apenas atualiza. Reenviar
  tudo garante que, se a instância gratuita do Render "dormiu" e perdeu os
  dados (ver aviso abaixo), a próxima sincronização os repõe sozinha.
- Arquivos temporários do Excel (que começam com `~$`, criados enquanto
  alguém tem a planilha aberta) são ignorados automaticamente.
- Se um arquivo estiver aberto/travado no momento exato da sincronização,
  ele é pulado com um aviso no log — e enviado normalmente na próxima
  rodada, sem intervenção sua.
- O tipo de cada planilha (Termos, Venda, Implantação...) é identificado
  automaticamente pelas colunas, igual ao upload manual pelo navegador.

## ⚠️ Sobre o plano gratuito do Render

Como o [`deploy.md`](deploy.md) já explica: no plano Free, a instância
"dorme" após ~15 minutos sem acesso e perde os dados ao acordar. Com a
sincronização automática ativa, o **próximo ciclo agendado repõe os dados
sozinho** — mas ainda assim pode haver uma janela de alguns minutos em que
o dashboard mostra menos dados do que deveria (ex.: se a instância dormiu
às 14h e o próximo ciclo é às 14h15). Para acompanhamento operacional
sério, o ideal é migrar para um plano com persistência (disco pago ou
Postgres — ver `deploy.md`), o que elimina essa janela por completo.

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
└── logs/                           um arquivo de log por dia (criado automaticamente)
```
