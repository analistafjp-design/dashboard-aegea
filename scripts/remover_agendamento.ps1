<#
.SINOPSE
    Remove a sincronizacao automatica criada por instalar_agendamento.ps1.
    Os arquivos ja enviados ao dashboard nao sao apagados — isso so para
    de enviar novas atualizacoes automaticamente.
#>

$NomeTarefa = "DashboardExecutivo-Sincronizacao"

$existente = Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue
if ($existente) {
    Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false
    Write-Host "Tarefa agendada '$NomeTarefa' removida. A sincronizacao automatica foi desligada." -ForegroundColor Green
} else {
    Write-Host "Nenhuma tarefa agendada '$NomeTarefa' encontrada — nada a remover." -ForegroundColor Yellow
}
