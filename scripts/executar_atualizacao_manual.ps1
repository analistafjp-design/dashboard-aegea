<#
.SINOPSE
    Atualiza o banco local e abre o dashboard no navegador.

.DESCRICAO
    Le somente planilhas novas ou alteradas nas pastas do OneDrive. Os dados
    ficam neste computador; nenhum arquivo e enviado para o Render.
#>

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$RaizProjeto = Split-Path -Parent $PastaScript
$Pastas = Join-Path $PastaScript "pastas-monitoradas.txt"
$Atualizador = Join-Path $PastaScript "atualizar_dashboard_local.py"
$PythonLocal = Join-Path $RaizProjeto ".venv\Scripts\python.exe"
$Requisitos = Join-Path $RaizProjeto "requirements.txt"
$PastaLocal = Join-Path $RaizProjeto "data\local"
$MarcaRequisitos = Join-Path $PastaLocal "requisitos.sha256"
$UrlLocal = "http://127.0.0.1:8000"
$VersaoEsperada = "1.2.0"

if (-not (Test-Path $Pastas)) {
    Write-Host "Configuracao inicial ainda nao realizada." -ForegroundColor Yellow
    Write-Host "Execute primeiro CONFIGURAR_ATALHO.cmd nesta mesma pasta." -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path $Atualizador)) {
    Write-Host "ERRO: atualizar_dashboard_local.py nao foi encontrado." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PythonLocal)) {
    $Lancador = Get-Command py.exe -ErrorAction SilentlyContinue
    $ArgumentosPython = @("-3")
    if (-not $Lancador) {
        $Lancador = Get-Command python.exe -ErrorAction SilentlyContinue
        $ArgumentosPython = @()
    }
    if (-not $Lancador) {
        Write-Host "ERRO: Python 3 nao foi encontrado neste computador." -ForegroundColor Red
        Write-Host "Instale o Python 3.11 ou mais recente em https://www.python.org/downloads/windows/" -ForegroundColor Yellow
        Write-Host "Durante a instalacao, marque a opcao 'Add Python to PATH'." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Preparando o dashboard local pela primeira vez..." -ForegroundColor Cyan
    & $Lancador.Source @ArgumentosPython -m venv (Join-Path $RaizProjeto ".venv")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-Path $PastaLocal)) {
    New-Item -ItemType Directory -Path $PastaLocal -Force | Out-Null
}
$HashAtual = (Get-FileHash -Path $Requisitos -Algorithm SHA256).Hash
$HashInstalado = if (Test-Path $MarcaRequisitos) {
    (Get-Content $MarcaRequisitos -Raw).Trim()
} else { "" }
if ($HashAtual -ne $HashInstalado) {
    Write-Host "Instalando componentes locais (somente na primeira vez)..." -ForegroundColor Cyan
    & $PythonLocal -m pip install --disable-pip-version-check -r $Requisitos
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Set-Content -Path $MarcaRequisitos -Value $HashAtual -Encoding ASCII
}

Write-Host "Verificando somente arquivos novos ou alterados..." -ForegroundColor Cyan
& $PythonLocal $Atualizador --pastas $Pastas
$Codigo = $LASTEXITCODE
if ($Codigo -ne 0) { exit $Codigo }

$ServidorAtivo = $false
$VersaoServidor = ""
try {
    $Resposta = Invoke-WebRequest -Uri "$UrlLocal/api/status" -UseBasicParsing -TimeoutSec 2
    $ServidorAtivo = $Resposta.StatusCode -eq 200
    if ($ServidorAtivo) {
        $StatusServidor = $Resposta.Content | ConvertFrom-Json
        $VersaoServidor = [string]$StatusServidor.versao
    }
} catch { $ServidorAtivo = $false }

# O ZIP atualiza os arquivos no disco, mas um Uvicorn que ja estava aberto
# continua executando o codigo antigo em memoria. Isso fazia os cartoes novos
# aparecerem junto com respostas antigas da API e deixava os graficos vazios.
# Ao detectar uma versao diferente, reiniciamos somente o processo que esta
# ouvindo a porta local do dashboard.
if ($ServidorAtivo -and $VersaoServidor -ne $VersaoEsperada) {
    Write-Host "Atualizando o painel que ja estava aberto..." -ForegroundColor Cyan
    $Conexao = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $Conexao) {
        $ServidorAtivo = $false
    } else {
        $ProcessoServidor = Get-CimInstance Win32_Process `
            -Filter "ProcessId = $($Conexao.OwningProcess)" -ErrorAction SilentlyContinue
        $ComandoServidor = if ($ProcessoServidor) { [string]$ProcessoServidor.CommandLine } else { "" }
        if ($ComandoServidor -match "uvicorn" -and $ComandoServidor -match "app\.main:app") {
            Stop-Process -Id $Conexao.OwningProcess -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 700
            $ServidorAtivo = $false
        } else {
            Write-Host "ERRO: a porta 8000 esta sendo usada por outro programa." -ForegroundColor Red
            Write-Host "Feche esse programa e clique novamente no atalho." -ForegroundColor Yellow
            exit 1
        }
    }
}

if (-not $ServidorAtivo) {
    Write-Host "Iniciando o painel local..." -ForegroundColor Cyan
    Start-Process -FilePath $PythonLocal `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $RaizProjeto -WindowStyle Hidden
    for ($Tentativa = 0; $Tentativa -lt 30; $Tentativa++) {
        Start-Sleep -Seconds 1
        try {
            $Resposta = Invoke-WebRequest -Uri "$UrlLocal/api/status" -UseBasicParsing -TimeoutSec 2
            if ($Resposta.StatusCode -eq 200) {
                $StatusServidor = $Resposta.Content | ConvertFrom-Json
                if ([string]$StatusServidor.versao -eq $VersaoEsperada) {
                    $ServidorAtivo = $true
                    break
                }
            }
        } catch { }
    }
}

if (-not $ServidorAtivo) {
    Write-Host "ERRO: o painel local nao iniciou. Consulte data\logs." -ForegroundColor Red
    exit 1
}

Write-Host "Abrindo o dashboard atualizado..." -ForegroundColor Green
Start-Process "$UrlLocal/"
exit 0
