<#
.SINOPSE
    Configura o Windows para rodar sincronizar_pastas.ps1 automaticamente,
    em segundo plano, a cada X minutos (Agendador de Tarefas do Windows).

.DESCRICAO
    Cria uma tarefa agendada por usuario (nao precisa ser administrador),
    que roda so enquanto voce esta logado no Windows. Rode este script UMA
    VEZ; depois disso a sincronizacao acontece sozinha.

.EXEMPLO
    .\instalar_agendamento.ps1
    .\instalar_agendamento.ps1 -IntervaloMinutos 30
#>

param(
    [int]$IntervaloMinutos = 15,
    [string]$Url = ""
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptSincronizacao = Join-Path $PastaScript "sincronizar_pastas.ps1"
$NomeTarefa = "DashboardExecutivo-Sincronizacao"

if ($IntervaloMinutos -lt 5) {
    Write-Host "Intervalo minimo recomendado e 5 minutos (evita sobrecarregar o servidor). Ajustando para 5." -ForegroundColor Yellow
    $IntervaloMinutos = 5
}

if (-not (Test-Path $ScriptSincronizacao)) {
    Write-Host "Nao encontrei sincronizar_pastas.ps1 na pasta $PastaScript" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $PastaScript "pastas-monitoradas.txt"))) {
    Write-Host "AVISO: pastas-monitoradas.txt ainda nao existe. Copie pastas-monitoradas.exemplo.txt" -ForegroundColor Yellow
    Write-Host "       para pastas-monitoradas.txt e edite com suas pastas antes de continuar." -ForegroundColor Yellow
}

$argumentos = '-NoProfile -ExecutionPolicy Bypass -File "' + $ScriptSincronizacao + '"'
if ($Url) { $argumentos += ' -Url "' + $Url + '"' }

$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argumentos -WorkingDirectory $PastaScript
$gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervaloMinutos) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$configuracoes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$existente = Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue
if ($existente) {
    Write-Host "Ja existe uma tarefa agendada '$NomeTarefa'. Removendo para recriar com as novas configuracoes..."
    Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false
}

Register-ScheduledTask -TaskName $NomeTarefa -Action $acao -Trigger $gatilho -Settings $configuracoes `
    -Description "Envia automaticamente as planilhas monitoradas para o Dashboard Executivo." | Out-Null

Write-Host ""
Write-Host "Pronto! A sincronizacao vai rodar a cada $IntervaloMinutos minutos, enquanto voce estiver logado no Windows." -ForegroundColor Green
Write-Host "Testar agora, sem esperar o agendamento:  .\sincronizar_pastas.ps1"
Write-Host "Ver os logs:                               pasta 'logs' dentro de $PastaScript"
Write-Host "Ver/editar a tarefa no Windows:            abra 'Agendador de Tarefas' e procure '$NomeTarefa'"
Write-Host "Remover o agendamento:                     .\remover_agendamento.ps1"
