<#
.SINOPSE
    Envia automaticamente as planilhas das pastas monitoradas para o
    Dashboard Executivo, sem precisar abrir o navegador.

.DESCRICAO
    Le a lista de pastas em "pastas-monitoradas.txt" (uma por linha),
    procura arquivos .xlsx/.xlsm/.xls/.csv em cada uma (incluindo
    subpastas), ignora arquivos temporarios do Excel (que comecam com
    "~$") e arquivos abertos/travados no momento, e envia todos de uma vez
    para a API de upload do dashboard.

    Reenvia TODOS os arquivos a cada execucao (nao so os que mudaram) de
    proposito: como o dashboard identifica cada registro por uma chave
    unica, reenviar um arquivo que nao mudou apenas atualiza os mesmos
    registros (nunca duplica) - e isso protege contra o plano gratuito do
    Render, que perde os dados quando a instancia "dorme" e acorda de novo.

.CONFIGURACAO
    1. Copie "pastas-monitoradas.exemplo.txt" para "pastas-monitoradas.txt"
       e edite com os caminhos reais das suas pastas.
    2. Copie "credenciais.exemplo.txt" para "credenciais.txt" e preencha
       usuario/senha (as mesmas configuradas no Render em AUTH_USUARIO e
       AUTH_SENHA). Se o dashboard nao tiver login configurado, deixe os
       dois valores em branco.
    3. Edite a variavel $UrlPadrao abaixo com a URL do seu dashboard.

.EXEMPLO
    .\sincronizar_pastas.ps1
    .\sincronizar_pastas.ps1 -Url "https://dashboard-executivo.onrender.com"
#>

param(
    [string]$Url = "",
    [string]$PastasArquivo = "",
    [string]$CredenciaisArquivo = "",
    [int]$TimeoutSegundos = 180
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---------------------------------------------------------------- config
$UrlPadrao = "https://dashboard-executivo.onrender.com"
if ([string]::IsNullOrWhiteSpace($Url)) { $Url = $UrlPadrao }
$Url = $Url.TrimEnd("/")

if ([string]::IsNullOrWhiteSpace($PastasArquivo)) {
    $PastasArquivo = Join-Path $PastaScript "pastas-monitoradas.txt"
}
if ([string]::IsNullOrWhiteSpace($CredenciaisArquivo)) {
    $CredenciaisArquivo = Join-Path $PastaScript "credenciais.txt"
}

$PastaLogs = Join-Path $PastaScript "logs"
if (-not (Test-Path $PastaLogs)) { New-Item -ItemType Directory -Path $PastaLogs | Out-Null }
$ArquivoLog = Join-Path $PastaLogs ("sincronizacao_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

$ExtensoesAceitas = @(".xlsx", ".xlsm", ".xls", ".csv")

function Escrever-Log {
    param([string]$Mensagem, [string]$Nivel = "INFO")
    $linha = "{0} | {1,-7} | {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Nivel, $Mensagem
    Write-Host $linha
    Add-Content -Path $ArquivoLog -Value $linha -Encoding UTF8
}

# ------------------------------------------------------------ credenciais
$Usuario = ""
$Senha = ""
if (Test-Path $CredenciaisArquivo) {
    $conteudo = Get-Content $CredenciaisArquivo -Encoding UTF8
    foreach ($linha in $conteudo) {
        if ($linha -match '^\s*USUARIO\s*=\s*(.*)$') { $Usuario = $Matches[1].Trim() }
        if ($linha -match '^\s*SENHA\s*=\s*(.*)$') { $Senha = $Matches[1].Trim() }
    }
}

# --------------------------------------------------------------- pastas
if (-not (Test-Path $PastasArquivo)) {
    Escrever-Log "Arquivo de configuracao nao encontrado: $PastasArquivo" "ERRO"
    Escrever-Log "Copie pastas-monitoradas.exemplo.txt para pastas-monitoradas.txt e edite com suas pastas." "ERRO"
    exit 1
}

$CaminhosMonitorados = Get-Content $PastasArquivo -Encoding UTF8 |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }

if (-not $CaminhosMonitorados) {
    Escrever-Log "Nenhuma pasta configurada em $PastasArquivo. Nada a fazer." "AVISO"
    exit 0
}

# ------------------------------------------------------- coletar arquivos
$Arquivos = New-Object System.Collections.Generic.List[System.IO.FileInfo]

foreach ($caminho in $CaminhosMonitorados) {
    if (-not (Test-Path $caminho)) {
        Escrever-Log "Caminho nao encontrado (verifique pastas-monitoradas.txt): $caminho" "AVISO"
        continue
    }
    $item = Get-Item $caminho
    if ($item.PSIsContainer) {
        $encontrados = Get-ChildItem -Path $caminho -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object {
                $ExtensoesAceitas -contains $_.Extension.ToLower() -and
                -not $_.Name.StartsWith("~$")
            }
        foreach ($f in $encontrados) { $Arquivos.Add($f) }
    } elseif ($ExtensoesAceitas -contains $item.Extension.ToLower() -and -not $item.Name.StartsWith("~$")) {
        $Arquivos.Add($item)
    }
}

if ($Arquivos.Count -eq 0) {
    Escrever-Log "Nenhuma planilha encontrada nas pastas monitoradas." "AVISO"
    exit 0
}

Escrever-Log "Encontrados $($Arquivos.Count) arquivo(s) em $($CaminhosMonitorados.Count) local(is) monitorado(s)."

# ------------------------------------------------ pular arquivos travados
$ArquivosProntos = New-Object System.Collections.Generic.List[System.IO.FileInfo]
foreach ($f in $Arquivos) {
    try {
        $stream = [System.IO.File]::Open($f.FullName, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        $stream.Close()
        $ArquivosProntos.Add($f)
    } catch {
        Escrever-Log "Pulando '$($f.Name)': arquivo aberto/travado agora. Sera reenviado na proxima execucao." "AVISO"
    }
}

if ($ArquivosProntos.Count -eq 0) {
    Escrever-Log "Todos os arquivos estao abertos/travados no momento. Nada enviado." "AVISO"
    exit 0
}

# --------------------------------------------------------- montar upload
Add-Type -AssemblyName System.Net.Http

$handler = New-Object System.Net.Http.HttpClientHandler
$cliente = New-Object System.Net.Http.HttpClient($handler)
$cliente.Timeout = [TimeSpan]::FromSeconds($TimeoutSegundos)

if ($Usuario -and $Senha) {
    $credencial = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("$($Usuario):$($Senha)"))
    $cliente.DefaultRequestHeaders.Authorization =
        New-Object System.Net.Http.Headers.AuthenticationHeaderValue("Basic", $credencial)
}

# Acorda a instancia (plano gratuito do Render "dorme" apos ~15 min sem
# acesso; o primeiro request depois disso pode levar ate 50s ou mais).
try {
    Escrever-Log "Verificando o servidor ($Url)..."
    $resposta = $cliente.GetAsync("$Url/api/status").Result
    if (-not $resposta.IsSuccessStatusCode) {
        Escrever-Log "Servidor respondeu com status $($resposta.StatusCode). Tentando enviar mesmo assim." "AVISO"
    }
} catch {
    Escrever-Log "Nao foi possivel contatar $Url. Verifique a URL e a internet. Detalhe: $($_.Exception.Message)" "ERRO"
    exit 1
}

$conteudoMultipart = New-Object System.Net.Http.MultipartFormDataContent
$streamsAbertos = New-Object System.Collections.Generic.List[System.IO.FileStream]

try {
    foreach ($f in $ArquivosProntos) {
        $fileStream = [System.IO.File]::OpenRead($f.FullName)
        $streamsAbertos.Add($fileStream)
        $streamContent = New-Object System.Net.Http.StreamContent($fileStream)
        $streamContent.Headers.ContentType =
            New-Object System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream")
        $conteudoMultipart.Add($streamContent, "arquivos", $f.Name)
    }

    Escrever-Log "Enviando $($ArquivosProntos.Count) arquivo(s) para $Url/api/upload ..."
    $respostaUpload = $cliente.PostAsync("$Url/api/upload", $conteudoMultipart).Result
    $corpo = $respostaUpload.Content.ReadAsStringAsync().Result

    if ($respostaUpload.StatusCode -eq 401) {
        Escrever-Log "O dashboard exige login e as credenciais em credenciais.txt estao erradas (ou o arquivo nao existe)." "ERRO"
        exit 1
    }

    try {
        $dados = $corpo | ConvertFrom-Json
    } catch {
        Escrever-Log "Resposta do servidor nao veio em JSON (status $($respostaUpload.StatusCode)). Corpo: $($corpo.Substring(0, [Math]::Min(300, $corpo.Length)))" "ERRO"
        exit 1
    }

    Escrever-Log "Resposta do servidor: $($dados.mensagem)"
    foreach ($r in $dados.resultados) {
        $nivel = if ($r.status -eq "ERRO") { "ERRO" } elseif ($r.status -eq "ATENCAO") { "AVISO" } else { "INFO" }
        $detalhe = "$($r.arquivo) [$($r.status)]"
        if ($r.titulo_dataset) { $detalhe += " - $($r.titulo_dataset)" }
        $detalhe += ": $($r.mensagem)"
        Escrever-Log $detalhe $nivel
    }

    if ($dados.ok) {
        Escrever-Log "Sincronizacao concluida com sucesso."
        exit 0
    } else {
        Escrever-Log "Sincronizacao concluida com problemas — veja as linhas ERRO acima." "AVISO"
        exit 2
    }
} finally {
    foreach ($s in $streamsAbertos) { $s.Dispose() }
    $conteudoMultipart.Dispose()
    $cliente.Dispose()
}
