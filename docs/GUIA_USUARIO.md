# Guia do Usuário — Dashboard Executivo

Este guia explica como acessar, atualizar e conferir o Dashboard Executivo.
Não é necessário editar código para usar o sistema.

## 1. Acesso

1. Abra a URL fornecida pelo responsável pelo dashboard.
2. Informe o usuário e a senha cadastrados no Render.
3. A página inicial apresenta o resumo dos módulos e a última atualização.

Se a tela de login reaparecer, confira usuário e senha. O navegador pode
guardar credenciais antigas; nesse caso, feche todas as janelas do dashboard
e abra novamente em uma janela anônima.

## 2. Navegação e filtros

Use o menu lateral para abrir Venda, Implantação, Termos, Faturamento,
Programação e as páginas analíticas. Os filtros no topo são globais: período,
cidade, frente, equipe, região e projeto afetam todos os indicadores da página.

- **Sem dados** significa que não existem registros para o filtro escolhido.
- **Zero** significa que existem dados, mas o resultado calculado é zero.
- **Meta não cadastrada** significa que a meta precisa ser importada; o sistema
  nunca inventa uma meta.

Para voltar à visão completa, use **Limpar filtros**.

## 3. Atualização manual

1. Abra **Atualização de Dados**.
2. Arraste ou selecione as planilhas.
3. Confira o tipo identificado. Se necessário, selecione a base manualmente.
4. Clique em **Atualizar dashboard**.
5. Aguarde o progresso chegar a concluído e confira o resultado de cada arquivo.

O sistema aceita `.xlsx`, `.xlsm`, `.xls` e `.csv`, com até 50 MB por arquivo.
Arquivos Excel grandes são processados em blocos para reduzir o uso de memória.
CSV com mais de 100 mil linhas deve ser convertido para `.xlsx` ou dividido.

Reenviar o mesmo registro não duplica a base: a carga atualiza a linha existente
usando a chave definida para cada conjunto de dados.

## 4. Resultado da importação

Cada arquivo recebe um estado:

- **SUCESSO**: todas as linhas aproveitáveis foram importadas.
- **ATENÇÃO**: o arquivo entrou, mas algumas linhas foram descartadas.
- **ERRO**: o arquivo não pôde ser importado.

Abra os detalhes para ver coluna ausente, data inválida, duplicidade ou regra de
negócio que descartou uma linha. Corrija o arquivo de origem e envie novamente.

## 5. Sincronização automática pelo OneDrive

No computador Windows:

1. Copie `scripts/pastas-monitoradas.exemplo.txt` para
   `scripts/pastas-monitoradas.txt`.
2. Preencha as pastas locais do OneDrive e o tipo de base de cada uma.
3. Copie `scripts/credenciais.exemplo.txt` para `scripts/credenciais.txt`.
4. Preencha a URL, o usuário e a senha do dashboard.
5. Execute `scripts/sincronizar_pastas.ps1` manualmente para testar.
6. Execute `scripts/instalar_agendamento.ps1` como usuário do Windows.

O agendamento verifica arquivos novos ou alterados a cada 15 minutos. Um arquivo
só é marcado como enviado depois que o servidor confirma o processamento.
Detalhes completos estão em [sincronizacao_pastas.md](sincronizacao_pastas.md).

## 6. Problemas comuns

### O upload parece parado

Não feche a página imediatamente. Arquivos grandes podem demorar no plano
gratuito. A tela consulta o progresso real do servidor. Se surgir erro de
comunicação, recarregue a página e confira **Histórico de importações**.

### Os dados desapareceram

No plano gratuito do Render, o banco SQLite não é persistente e pode ser
apagado quando a instância reinicia. Para uso operacional, configure disco
persistente ou PostgreSQL conforme [deploy.md](deploy.md).

### Os números não mudaram

Confira, nesta ordem:

1. o estado do arquivo no histórico;
2. o período e os filtros selecionados;
3. as linhas descartadas e seus motivos;
4. se a data do arquivo pertence ao período exibido;
5. se o tipo de base detectado está correto.

### Arquivo recusado por tamanho

Arquivos acima de 50 MB devem ser divididos. Para CSV acima de 100 mil linhas,
converta para Excel ou separe por mês/cidade. Não remova colunas obrigatórias.

### A sincronização não envia arquivos

Execute `sincronizar_pastas.ps1` manualmente e leia o log exibido. Confira a URL,
as credenciais, os caminhos do OneDrive e se o computador está ligado. Depois,
abra o Agendador de Tarefas do Windows e verifique a última execução.

## 7. Validação depois de atualizar

Após uma carga de produção, confirme:

- data e hora da última atualização;
- total de registros importados e descartados;
- mês selecionado;
- Venda Comercial, VCG e Outros Canais;
- Implantação faturada e não faturada;
- Termos e Faturamento;
- Programação por equipe;
- comparação dos principais totais com o Power BI.

Se houver divergência, não ajuste o número manualmente. Registre o arquivo, o
período, o filtro e os dois valores comparados para que a regra seja revisada.
