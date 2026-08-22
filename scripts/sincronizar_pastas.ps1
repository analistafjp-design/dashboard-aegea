<#
.SINOPSE
    Envia automaticamente as planilhas das pastas monitoradas para o
    Dashboard Executivo, sem precisar abrir o navegador.

.DESCRICAO
    Le a lista de pastas em "pastas-monitoradas.txt" (uma por linha),
    procura arquivos .xlsx/.xlsm/.xls/.csv em cada uma (incluindo
    subpastas), ignora arquivos temporarios do Excel (que comecam com
    "~$") e arquivos abertos/travados no momento.

    ENVIO INCREMENTAL (padrao): so envia arquivos novos ou modificados
    desde a ultima sincronizacao bem-sucedida — controlado por um
    "manifesto" local (logs\manifesto_sincronizacao.json), que guarda
    tamanho e data de modificacao de cada arquivo ja enviado. Pastas com
    centenas de planilhas historicas (uma por dia, por exemplo) nao
    precisam ser reenviadas inteiras a cada execucao.

    ENVIO COMPLETO (-Completo): ignora o manifesto e reenvia tudo. Como o
    dashboard identifica cada registro por uma chave unica, reenviar um
    arquivo que nao mudou apenas atualiza os mesmos registros (nunca
    duplica) — use isso na primeira execucao, ou de vez em quando, para
    repor dados caso a instancia gratuita do Render tenha "dormido" e
    perdido o banco (ver docs/sincronizacao_pastas.md).

    Os arquivos sao enviados em lotes (nao tudo de uma vez numa unica
    requisicao gigante) para nao estourar tempo limite quando houver
    muitos arquivos.

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
    .\sincronizar_pastas.ps1 -Completo
    .\sincronizar_pastas.ps1 -Url "https://dashboard-executivo.onrender.com" -TimeoutSegundos 600
#>

param(
    [string]$Url = "",
    [string]$PastasArquivo = "",
    [string]$CredenciaisArquivo = "",
    [int]$TimeoutSegundos = 180,
    [int]$ArquivosPorLote = 20,
    [double]$MegabytesPorLote = 40,
    [switch]$Completo
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
$ArquivoManifesto = Join-Path $PastaLogs "manifesto_sincronizacao.json"

$ExtensoesAceitas = @(".xlsx", ".xlsm", ".xls", ".csv")
$LimiteBytesPorLote = [long]($MegabytesPorLote * 1MB)

function Escrever-Log {
    param([string]$Mensagem, [string]$Nivel = "INFO")
    $linha = "{0} | {1,-7} | {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Nivel, $Mensagem
    Write-Host $linha
    Add-Content -Path $ArquivoLog -Value $linha -Encoding UTF8
}

# ------------------------------------------------------------- manifesto
# Compatível com PowerShell 5.1 (sem -AsHashtable, que só existe no PS 6+).
function Carregar-Manifesto {
    $tabela = @{}
    if (Test-Path $ArquivoManifesto) {
        try {
            $bruto = Get-Content $ArquivoManifesto -Raw -Encoding UTF8
            if ($bruto) {
                $objeto = $bruto | ConvertFrom-Json
                foreach ($prop in $objeto.PSObject.Properties) {
                    $tabela[$prop.Name] = @{
                        Tamanho = [int64]$prop.Value.Tamanho
                        Ticks   = [int64]$prop.Value.Ticks
                    }
                }
            }
        } catch {
            Escrever-Log "Manifesto de sincronizacao corrompido ou ilegivel — sera recriado do zero." "AVISO"
        }
    }
    return $tabela
}

function Salvar-Manifesto {
    param($Manifesto)
    $Manifesto | ConvertTo-Json -Depth 4 | Set-Content -Path $ArquivoManifesto -Encoding UTF8
}

# Data de modificacao guardada como "Ticks" (inteiro, 100ns desde
# 01/01/0001) em vez de texto ISO: o PowerShell 7 detecta automaticamente
# strings no formato de data dentro de JSON e as converte para DateTime ao
# reler o manifesto, o que troca o formato (perde os digitos de fracao de
# segundo) e faz a comparacao falhar sempre. Um numero nao sofre esse
# problema.
function Arquivo-Mudou {
    param($Info, $Manifesto)
    $chave = $Info.FullName
    if (-not $Manifesto.ContainsKey($chave)) { return $true }
    $registrado = $Manifesto[$chave]
    $ticksAtual = $Info.LastWriteTimeUtc.Ticks
    return ($registrado.Tamanho -ne $Info.Length) -or ($registrado.Ticks -ne $ticksAtual)
}

function Marcar-Enviado {
    param($Info, $Manifesto)
    $Manifesto[$Info.FullName] = @{
        Tamanho = $Info.Length
        Ticks   = $Info.LastWriteTimeUtc.Ticks
    }
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

# ---------------------------------------------------- filtrar por manifesto
$Manifesto = Carregar-Manifesto
if ($Completo) {
    $ArquivosParaEnviar = $ArquivosProntos
    Escrever-Log "Modo -Completo: reenviando todos os $($ArquivosProntos.Count) arquivo(s), ignorando o manifesto."
} else {
    $ArquivosParaEnviar = $ArquivosProntos | Where-Object { Arquivo-Mudou -Info $_ -Manifesto $Manifesto }
    $puladosPorManifesto = $ArquivosProntos.Count - $ArquivosParaEnviar.Count
    if ($puladosPorManifesto -gt 0) {
        Escrever-Log "$puladosPorManifesto arquivo(s) sem alteracao desde o ultimo envio — nao serao reenviados."
    }
}

if (-not $ArquivosParaEnviar -or $ArquivosParaEnviar.Count -eq 0) {
    Escrever-Log "Nada novo para enviar. Sincronizacao concluida (nenhuma alteracao)."
    exit 0
}

# ------------------------------------------------------------- montar lotes
$Lotes = New-Object System.Collections.Generic.List[System.Object]
$loteAtual = New-Object System.Collections.Generic.List[System.IO.FileInfo]
$tamanhoLoteAtual = 0L

foreach ($f in $ArquivosParaEnviar) {
    $estouraQuantidade = $loteAtual.Count -ge $ArquivosPorLote
    $estouraTamanho = ($tamanhoLoteAtual + $f.Length) -gt $LimiteBytesPorLote -and $loteAtual.Count -gt 0
    if ($estouraQuantidade -or $estouraTamanho) {
        $Lotes.Add($loteAtual)
        $loteAtual = New-Object System.Collections.Generic.List[System.IO.FileInfo]
        $tamanhoLoteAtual = 0L
    }
    $loteAtual.Add($f)
    $tamanhoLoteAtual += $f.Length
}
if ($loteAtual.Count -gt 0) { $Lotes.Add($loteAtual) }

Escrever-Log "Enviando $($ArquivosParaEnviar.Count) arquivo(s) novo(s)/alterado(s) em $($Lotes.Count) lote(s)."

# --------------------------------------------------------- cliente HTTP
Add-Type -AssemblyName System.Net.Http

$handler = New-Object System.Net.Http.HttpClientHandler
$cliente = New-Object System.Net.Http.HttpClient($handler)
$cliente.Timeout = [TimeSpan]::FromSeconds($TimeoutSegundos)

if ($Usuario -and $Senha) {
    $credencial = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("$($Usuario):$($Senha)"))
    $cliente.DefaultRequestHeaders.Authorization =
        New-Object System.Net.Http.Headers.AuthenticationHeaderValue("Basic", $credencial)
}

# Acorda a instancia antes do primeiro lote (plano gratuito do Render
# "dorme" apos ~15 min sem acesso; o primeiro request depois disso pode
# levar ate 50s ou mais).
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

$totalErros = 0
$totalOk = 0
$numeroLote = 0

foreach ($lote in $Lotes) {
    $numeroLote++
    $conteudoMultipart = New-Object System.Net.Http.MultipartFormDataContent
    $streamsAbertos = New-Object System.Collections.Generic.List[System.IO.FileStream]

    try {
        foreach ($f in $lote) {
            $fileStream = [System.IO.File]::OpenRead($f.FullName)
            $streamsAbertos.Add($fileStream)
            $streamContent = New-Object System.Net.Http.StreamContent($fileStream)
            $streamContent.Headers.ContentType =
                New-Object System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream")
            $conteudoMultipart.Add($streamContent, "arquivos", $f.Name)
        }

        Escrever-Log "Lote $numeroLote/$($Lotes.Count): enviando $($lote.Count) arquivo(s) para $Url/api/upload ..."
        $respostaUpload = $cliente.PostAsync("$Url/api/upload", $conteudoMultipart).Result
        $corpo = $respostaUpload.Content.ReadAsStringAsync().Result

        if ($respostaUpload.StatusCode -eq 401) {
            Escrever-Log "O dashboard exige login e as credenciais em credenciais.txt estao erradas (ou o arquivo nao existe)." "ERRO"
            Salvar-Manifesto $Manifesto
            exit 1
        }

        try {
            $dados = $corpo | ConvertFrom-Json
        } catch {
            Escrever-Log "Resposta do servidor nao veio em JSON (status $($respostaUpload.StatusCode)). Corpo: $($corpo.Substring(0, [Math]::Min(300, $corpo.Length)))" "ERRO"
            $totalErros += $lote.Count
            continue
        }

        Escrever-Log "Lote $numeroLote resposta: $($dados.mensagem)"

        # Casa cada resultado do servidor (nome vem com prefixo de data/hora,
        # ex.: "20260822_003000_venda.xlsx") com o arquivo local pelo final
        # do nome. Em caso de nome ambiguo (dois arquivos iguais no mesmo
        # lote), o arquivo NAO e marcado como enviado — sera reenviado na
        # proxima execucao, o que e seguro (nunca duplica).
        foreach ($f in $lote) {
            $correspondencias = @($dados.resultados | Where-Object { $_.arquivo.EndsWith($f.Name) })
            if ($correspondencias.Count -eq 1) {
                $r = $correspondencias[0]
                $nivel = if ($r.status -eq "ERRO") { "ERRO" } elseif ($r.status -eq "ATENCAO") { "AVISO" } else { "INFO" }
                $detalhe = "$($f.Name) [$($r.status)]"
                if ($r.titulo_dataset) { $detalhe += " - $($r.titulo_dataset)" }
                $detalhe += ": $($r.mensagem)"
                Escrever-Log $detalhe $nivel

                if ($r.status -ne "ERRO") {
                    Marcar-Enviado -Info $f -Manifesto $Manifesto
                    $totalOk++
                } else {
                    $totalErros++
                }
            } else {
                Escrever-Log "$($f.Name): nao foi possivel confirmar o resultado individual (sera conferido na proxima execucao)." "AVISO"
                $totalErros++
            }
        }

        # Salva o manifesto apos cada lote — se um lote mais adiante falhar,
        # o progresso dos lotes anteriores nao se perde.
        Salvar-Manifesto $Manifesto
    } finally {
        foreach ($s in $streamsAbertos) { $s.Dispose() }
        $conteudoMultipart.Dispose()
    }
}

$cliente.Dispose()

Escrever-Log "Sincronizacao finalizada: $totalOk arquivo(s) processado(s) com sucesso, $totalErros com problema."
if ($totalErros -eq 0) {
    exit 0
} else {
    exit 2
}
