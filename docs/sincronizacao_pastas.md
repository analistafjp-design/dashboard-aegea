# Botão de atualização local no Windows

Esta versão não envia arquivos para um servidor. O dashboard e o banco rodam no
próprio computador, enquanto as planilhas continuam nas pastas sincronizadas do
OneDrive.

## Configuração inicial

1. Abra a pasta `scripts` do repositório.
2. Dê dois cliques em `CONFIGURAR_ATALHO.cmd`.
3. Se o caminho padrão não existir, copie o caminho da pasta
   `DashBoard - Interior` pela barra de endereço do Explorador e cole no prompt.

O assistente cria `pastas-monitoradas.txt` e o atalho **Atualizar Dashboard
AEGEA** na Área de Trabalho. Ele não pede URL, usuário ou senha.

Estrutura padrão:

```text
<PASTA_ONEDRIVE>\DashBoard - Interior\Atendimento = atendimento
<PASTA_ONEDRIVE>\DashBoard - Interior\Faturamento = faturamento, faturamento_implantacao
<PASTA_ONEDRIVE>\DashBoard - Interior\Interior = vendas, implantacao, termos
<PASTA_ONEDRIVE>\DashBoard - Interior\Programação Diária = programacao
```

## Atualizar

1. Coloque ou substitua uma planilha na pasta correta.
2. Aguarde o ícone verde do OneDrive.
3. Dê dois cliques no atalho da Área de Trabalho.

Na primeira execução o script cria o ambiente Python e importa o histórico. Nas
execuções seguintes mostra quantos arquivos foram ignorados sem alteração e lê
somente os novos ou modificados. Ao terminar, abre o dashboard em
`http://127.0.0.1:8000`.

## Controle incremental

O catálogo fica em `data\local\manifesto_atualizacao.json`. Para cada arquivo,
ele guarda caminho, tamanho, horário de modificação, bases carregadas e status.
O registro é gravado imediatamente após o sucesso; por isso uma interrupção não
obriga a reiniciar todo o histórico.

Para reconstruir tudo deliberadamente:

```powershell
.venv\Scripts\python.exe scripts\atualizar_dashboard_local.py --completo
```

Normalmente não use `--completo`.

## Solução de problemas

| Mensagem | Ação |
|---|---|
| Pasta não encontrada | Execute novamente `CONFIGURAR_ATALHO.cmd` e cole o caminho correto. |
| Nenhuma planilha encontrada | Confirme extensão `.xlsx`, `.xlsm`, `.xls` ou `.csv` e sincronização do OneDrive. |
| Nenhuma aba compatível | Confira se o arquivo está na pasta correta e se mantém as colunas do Power BI. |
| Porta 8000 ocupada | Feche outra instância do dashboard e clique no atalho novamente. |
| Arquivo temporário `~$` | Feche o Excel; esses arquivos são ignorados automaticamente. |

Não é necessário configurar Render, disco persistente, login, upload pelo
navegador ou agendamento do Windows.
