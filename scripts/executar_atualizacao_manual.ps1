<#
.SINOPSE
    Executa a sincronizacao somente quando o usuario clica no atalho.

.DESCRICAO
    Chama sincronizar_pastas.ps1, preserva o codigo de saida e abre o
    dashboard no navegador apenas quando a atualizacao termina sem erros.
    Este script nao cria nem executa tarefas agendadas.
#>

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sincronizador = Join-Path $PastaScript "sincronizar_pastas.ps1"
$Credenciais = Join-Path $PastaScript "credenciais.txt"
$Pastas = Join-Path $PastaScript "pastas-monitoradas.txt"

if (-not (Test-Path $Sincronizador)) {
    Write-Host "ERRO: sincronizar_pastas.ps1 nao foi encontrado." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $Pastas) -or -not (Test-Path $Credenciais)) {
    Write-Host "Configuracao inicial ainda nao realizada." -ForegroundColor Yellow
    Write-Host "Execute primeiro CONFIGURAR_ATALHO.cmd nesta mesma pasta." -ForegroundColor Yellow
    exit 1
}

& $Sincronizador
$Codigo = $LASTEXITCODE

if ($Codigo -eq 0) {
    $Url = "https://dashboard-executivo.onrender.com"
    foreach ($Linha in (Get-Content $Credenciais -Encoding UTF8)) {
        if ($Linha -match '^\s*URL\s*=\s*(.+)$') {
            $Url = $Matches[1].Trim().TrimEnd("/")
        }
    }
    Write-Host "Abrindo o dashboard atualizado..." -ForegroundColor Green
    Start-Process $Url
}

exit $Codigo
