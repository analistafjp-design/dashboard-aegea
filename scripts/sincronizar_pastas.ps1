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
    desde a ultima sincronizacao bem-sucedida - controlado por um
    "manifesto" local (logs\manifesto_sincronizacao.json), que guarda
    tamanho e data de modificacao de cada arquivo ja enviado. Pastas com
    centenas de planilhas historicas (uma por dia, por exemplo) nao
    precisam ser reenviadas inteiras a cada execucao.

    ENVIO COMPLETO (-Completo): ignora o manifesto e reenvia tudo. Como o
    dashboard identifica cada registro por uma chave unica, reenviar um
    arquivo que nao mudou apenas atualiza os mesmos registros (nunca
    duplica) - use isso na primeira execucao, ou de vez em quando, para
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
    3. Informe a URL do dashboard em credenciais.txt (linha URL=...).

.EXEMPLO
    .\sincronizar_pastas.ps1
    .\sincronizar_pastas.ps1 -Completo
    .\sincronizar_pastas.ps1 -Url "https://dashboard-executivo.onrender.com" -TimeoutProcessamentoSegundos 7200
#>

param(
    [string]$Url = "",
    [string]$PastasArquivo = "",
    [string]$CredenciaisArquivo = "",
    [int]$TimeoutSegundos = 300,
    [int]$TimeoutProcessamentoSegundos = 3600,
    [int]$ArquivosPorLote = 20,
    [double]$MegabytesPorLote = 40,
    [switch]$Completo
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---------------------------------------------------------------- config
$UrlPadrao = "https://dashboard-executivo.onrender.com"
$UrlInformadaPorParametro = -not [string]::IsNullOrWhiteSpace($Url)

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
# Compativel com PowerShell 5.1 (sem -AsHashtable, que so existe no PS 6+).
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
            Escrever-Log "Manifesto de sincronizacao corrompido ou ilegivel - sera recriado do zero." "AVISO"
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
# A chave inclui a base de destino: a MESMA planilha pode alimentar mais de
# uma base (a pasta Interior alimenta Venda, Implantacao e Termos), e cada
# destino precisa ser controlado em separado - senao, enviar para Venda
# marcaria o arquivo como "ja enviado" e Implantacao/Termos nunca o
# receberiam.
function Chave-Manifesto {
    param($Info, [string]$Tipo)
    if ($Tipo) { return "$($Info.FullName)|$Tipo" }
    return $Info.FullName
}

function Arquivo-Mudou {
    param($Info, [string]$Tipo, $Manifesto)
    $chave = Chave-Manifesto -Info $Info -Tipo $Tipo
    if (-not $Manifesto.ContainsKey($chave)) { return $true }
    $registrado = $Manifesto[$chave]
    $ticksAtual = $Info.LastWriteTimeUtc.Ticks
    return ($registrado.Tamanho -ne $Info.Length) -or ($registrado.Ticks -ne $ticksAtual)
}

function Marcar-Enviado {
    param($Info, [string]$Tipo, $Manifesto)
    $Manifesto[(Chave-Manifesto -Info $Info -Tipo $Tipo)] = @{
        Tamanho = $Info.Length
        Ticks   = $Info.LastWriteTimeUtc.Ticks
    }
}

# ------------------------------------------------------------ credenciais
$Usuario = ""
$Senha = ""
$UrlConfigurada = ""
if (Test-Path $CredenciaisArquivo) {
    $conteudo = Get-Content $CredenciaisArquivo -Encoding UTF8
    foreach ($linha in $conteudo) {
        if ($linha -match '^\s*USUARIO\s*=\s*(.*)$') { $Usuario = $Matches[1].Trim() }
        if ($linha -match '^\s*SENHA\s*=\s*(.*)$') { $Senha = $Matches[1].Trim() }
        if ($linha -match '^\s*URL\s*=\s*(.*)$') { $UrlConfigurada = $Matches[1].Trim() }
    }
}
if (-not $UrlInformadaPorParametro) {
    $Url = if ($UrlConfigurada) { $UrlConfigurada } else { $UrlPadrao }
}
$Url = $Url.TrimEnd("/")

# --------------------------------------------------------------- pastas
if (-not (Test-Path $PastasArquivo)) {
    Escrever-Log "Arquivo de configuracao nao encontrado: $PastasArquivo" "ERRO"
    Escrever-Log "Copie pastas-monitoradas.exemplo.txt para pastas-monitoradas.txt e edite com suas pastas." "ERRO"
    exit 1
}

# Cada linha pode ser so o caminho, ou "CAMINHO = tipo" para fixar a base
# daquela pasta (mesma ideia das abas na tela de Atualizacao de Dados).
# Tipos aceitos: termos, faturamento, vendas, implantacao, programacao,
# metas e atendimento.
# Sem "= tipo", o sistema identifica a base pelas colunas do arquivo.
$TiposValidos = @("termos", "faturamento", "vendas", "implantacao", "programacao", "metas", "atendimento")
$CaminhosMonitorados = New-Object System.Collections.Generic.List[object]

foreach ($linha in (Get-Content $PastasArquivo -Encoding UTF8)) {
    $texto = $linha.Trim()
    if (-not $texto -or $texto.StartsWith("#")) { continue }

    # Aceita "CAMINHO = tipo" e tambem "CAMINHO = tipo1, tipo2, tipo3" - a
    # mesma pasta pode alimentar varias bases (a pasta Interior tem os
    # mesmos arquivos usados por Venda, Implantacao e Termos).
    $tipos = @("")
    $caminho = $texto
    $separador = $texto.LastIndexOf("=")
    if ($separador -gt 0) {
        $lista = $texto.Substring($separador + 1).Trim().ToLower() -split "," |
            ForEach-Object { $_.Trim() } | Where-Object { $_ }
        $validos = @($lista | Where-Object { $TiposValidos -contains $_ })
        $invalidos = @($lista | Where-Object { $TiposValidos -notcontains $_ })
        foreach ($ruim in $invalidos) {
            Escrever-Log "Tipo '$ruim' desconhecido em '$texto'. Use: $($TiposValidos -join ', ')." "AVISO"
        }
        if ($validos.Count -gt 0) {
            $tipos = $validos
            $caminho = $texto.Substring(0, $separador).Trim()
        }
    }
    foreach ($t in $tipos) {
        $CaminhosMonitorados.Add([pscustomobject]@{ Caminho = $caminho; Tipo = $t })
    }
}

if ($CaminhosMonitorados.Count -eq 0) {
    Escrever-Log "Nenhuma pasta configurada em $PastasArquivo. Nada a fazer." "AVISO"
    exit 0
}

# ------------------------------------------------------- coletar arquivos
# Cada item e um par (arquivo, base de destino). O mesmo arquivo aparece
# mais de uma vez quando a pasta alimenta varias bases.
$Arquivos = New-Object System.Collections.Generic.List[object]
$SomenteNuvem = 0
$JaVistos = New-Object System.Collections.Generic.HashSet[string]

function Registrar-Arquivo {
    param($Info, [string]$Tipo)
    # Evita duplicar se a mesma pasta aparecer duas vezes com o mesmo tipo.
    if (-not $script:JaVistos.Add("$($Info.FullName)|$Tipo")) { return }
    # OneDrive/Drive com "Arquivos Sob Demanda": o arquivo aparece na pasta
    # mas o conteudo ainda esta na nuvem. Ler dispara o download automatico,
    # entao da certo - so pode demorar na primeira vez.
    $atributos = $Info.Attributes.ToString()
    if ($atributos -match "Offline" -or $atributos -match "RecallOn") {
        $script:SomenteNuvem++
    }
    $script:Arquivos.Add([pscustomobject]@{ Info = $Info; Tipo = $Tipo })
}

foreach ($entrada in $CaminhosMonitorados) {
    $caminho = $entrada.Caminho
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
        foreach ($f in $encontrados) { Registrar-Arquivo -Info $f -Tipo $entrada.Tipo }
    } elseif ($ExtensoesAceitas -contains $item.Extension.ToLower() -and -not $item.Name.StartsWith("~$")) {
        Registrar-Arquivo -Info $item -Tipo $entrada.Tipo
    }
}

if ($SomenteNuvem -gt 0) {
    Escrever-Log "$SomenteNuvem arquivo(s) estao apenas na nuvem (OneDrive/Drive Sob Demanda). Serao baixados automaticamente ao ler - a primeira sincronizacao pode demorar mais." "AVISO"
}

if ($Arquivos.Count -eq 0) {
    Escrever-Log "Nenhuma planilha encontrada nas pastas monitoradas." "AVISO"
    exit 0
}

Escrever-Log "Encontrados $($Arquivos.Count) arquivo(s) em $($CaminhosMonitorados.Count) local(is) monitorado(s)."

# ------------------------------------------------ pular arquivos travados
$ArquivosProntos = New-Object System.Collections.Generic.List[object]
$travadosAvisados = New-Object System.Collections.Generic.HashSet[string]
foreach ($par in $Arquivos) {
    try {
        $stream = [System.IO.File]::Open($par.Info.FullName, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        $stream.Close()
        $ArquivosProntos.Add($par)
    } catch {
        if ($travadosAvisados.Add($par.Info.FullName)) {
            Escrever-Log "Pulando '$($par.Info.Name)': arquivo aberto/travado agora. Sera reenviado na proxima execucao." "AVISO"
        }
    }
}

if ($ArquivosProntos.Count -eq 0) {
    Escrever-Log "Todos os arquivos estao abertos/travados no momento. Nada enviado." "AVISO"
    exit 0
}

$Manifesto = Carregar-Manifesto

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

# Acorda e consulta a instancia ANTES de aplicar o manifesto. Se o banco do
# servidor estiver vazio (por exemplo, depois de um redeploy do Render), o
# manifesto local nao pode fazer o script pular arquivos que o dashboard ja
# nao possui. Nesse caso, a recuperacao completa ocorre automaticamente.
try {
    Escrever-Log "Verificando o servidor ($Url)..."
    $resposta = $cliente.GetAsync("$Url/api/status").Result
    if (-not $resposta.IsSuccessStatusCode) {
        Escrever-Log "Servidor respondeu com status $($resposta.StatusCode). Tentando enviar mesmo assim." "AVISO"
    } else {
        try {
            $estadoServidor = $resposta.Content.ReadAsStringAsync().Result | ConvertFrom-Json
            $informaSeTemDados = $estadoServidor.PSObject.Properties.Name -contains "tem_dados"
            if ($informaSeTemDados -and -not [bool]$estadoServidor.tem_dados -and
                $Manifesto.Count -gt 0 -and -not $Completo) {
                $Completo = $true
                Escrever-Log "O servidor esta sem dados, mas existe historico local. Recuperacao completa ativada automaticamente." "AVISO"
            }
        } catch {
            Escrever-Log "Nao foi possivel interpretar o status do servidor. O envio incremental continuara normalmente." "AVISO"
        }
    }
} catch {
    $cliente.Dispose()
    Escrever-Log "Nao foi possivel contatar $Url. Verifique a URL e a internet. Detalhe: $($_.Exception.Message)" "ERRO"
    exit 1
}

# ---------------------------------------------------- filtrar por manifesto
if ($Completo) {
    $ArquivosParaEnviar = $ArquivosProntos
    Escrever-Log "Modo -Completo: reenviando todos os $($ArquivosProntos.Count) arquivo(s), ignorando o manifesto."
} else {
    $ArquivosParaEnviar = $ArquivosProntos |
        Where-Object { Arquivo-Mudou -Info $_.Info -Tipo $_.Tipo -Manifesto $Manifesto }
    $puladosPorManifesto = $ArquivosProntos.Count - $ArquivosParaEnviar.Count
    if ($puladosPorManifesto -gt 0) {
        Escrever-Log "$puladosPorManifesto arquivo(s) sem alteracao desde o ultimo envio - nao serao reenviados."
    }
}

if (-not $ArquivosParaEnviar -or $ArquivosParaEnviar.Count -eq 0) {
    Escrever-Log "Nada novo para enviar. Sincronizacao concluida (nenhuma alteracao)."
    $cliente.Dispose()
    exit 0
}

# ------------------------------------------------------------- montar lotes
# Os lotes sao montados POR BASE de destino: assim um lote nunca tem o
# mesmo nome de arquivo duas vezes (o que tornaria ambiguo o casamento
# entre o resultado devolvido pelo servidor e o arquivo local).
$Lotes = New-Object System.Collections.Generic.List[System.Object]

# Primeiro carrega as bases menores, que alimentam imediatamente as telas.
# Atendimento fica por ultimo porque sua planilha real e muito maior e pode
# levar varios minutos. Dentro de cada base, os arquivos mais recentes vao
# primeiro para o dashboard mostrar o periodo atual o quanto antes.
$PrioridadeBase = @{
    "programacao" = 10
    "faturamento" = 20
    "vendas" = 30
    "implantacao" = 40
    "termos" = 50
    "metas" = 60
    "" = 70
    "atendimento" = 90
}
$GruposOrdenados = $ArquivosParaEnviar | Group-Object -Property Tipo | Sort-Object {
    if ($PrioridadeBase.ContainsKey($_.Name)) { $PrioridadeBase[$_.Name] } else { 80 }
}

foreach ($grupo in $GruposOrdenados) {
    $loteAtual = New-Object System.Collections.Generic.List[object]
    $tamanhoLoteAtual = 0L
    foreach ($par in ($grupo.Group | Sort-Object { $_.Info.LastWriteTimeUtc } -Descending)) {
        $estouraQuantidade = $loteAtual.Count -ge $ArquivosPorLote
        $estouraTamanho = ($tamanhoLoteAtual + $par.Info.Length) -gt $LimiteBytesPorLote -and $loteAtual.Count -gt 0
        if ($estouraQuantidade -or $estouraTamanho) {
            $Lotes.Add($loteAtual)
            $loteAtual = New-Object System.Collections.Generic.List[object]
            $tamanhoLoteAtual = 0L
        }
        $loteAtual.Add($par)
        $tamanhoLoteAtual += $par.Info.Length
    }
    if ($loteAtual.Count -gt 0) { $Lotes.Add($loteAtual) }
}

Escrever-Log "Enviando $($ArquivosParaEnviar.Count) arquivo(s) novo(s)/alterado(s) em $($Lotes.Count) lote(s)."

$totalErros = 0
$totalOk = 0
$numeroLote = 0

foreach ($lote in $Lotes) {
    $numeroLote++
    $conteudoMultipart = New-Object System.Net.Http.MultipartFormDataContent
    $streamsAbertos = New-Object System.Collections.Generic.List[System.IO.FileStream]

    try {
        foreach ($par in $lote) {
            $fileStream = [System.IO.File]::OpenRead($par.Info.FullName)
            $streamsAbertos.Add($fileStream)
            $streamContent = New-Object System.Net.Http.StreamContent($fileStream)
            $streamContent.Headers.ContentType =
                New-Object System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream")
            $conteudoMultipart.Add($streamContent, "arquivos", $par.Info.Name)

            # O campo "tipo" vai na MESMA ordem dos arquivos: o servidor
            # casa tipo[i] com arquivos[i]. String vazia = identificar
            # automaticamente pelas colunas.
            $conteudoMultipart.Add(
                (New-Object System.Net.Http.StringContent($par.Tipo)), "tipo")
        }

        $baseDoLote = if ($lote[0].Tipo) { $lote[0].Tipo } else { "deteccao automatica" }
        Escrever-Log "Lote $numeroLote/$($Lotes.Count): enviando $($lote.Count) arquivo(s) [base: $baseDoLote] para $Url/api/upload ..."
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

        # O envio agora so AGENDA o processamento (o servidor responde na
        # hora com um trabalho_id e processa em segundo plano, para nao
        # travar). Aqui acompanhamos ate terminar, senao marcariamos como
        # enviado algo que ainda nem foi processado.
        if ($dados.trabalho_id -and -not $dados.concluido) {
            $espera = 0
            while ($true) {
                Start-Sleep -Seconds 3
                $espera += 3
                if ($espera -gt $TimeoutProcessamentoSegundos) {
                    Escrever-Log "Lote ${numeroLote}: o servidor ainda processava apos $TimeoutProcessamentoSegundos s. Sera conferido na proxima execucao." "AVISO"
                    $totalErros += $lote.Count
                    $dados = $null
                    break
                }
                try {
                    $rProg = $cliente.GetAsync("$Url/api/upload/$($dados.trabalho_id)").Result
                    $corpoProg = $rProg.Content.ReadAsStringAsync().Result
                    $estado = $corpoProg | ConvertFrom-Json
                } catch {
                    Escrever-Log "Falha ao consultar o progresso do lote $numeroLote; tentando de novo." "AVISO"
                    continue
                }
                if ($estado.concluido) { $dados = $estado; break }
                if (($espera % 15) -eq 0) {
                    Escrever-Log "  ... processando $($estado.concluidos)/$($estado.total) $($estado.arquivo_atual) (aguardando ha $espera s)"
                }
            }
            if ($null -eq $dados) { continue }
        }

        Escrever-Log "Lote $numeroLote resposta: $($dados.mensagem)"

        # Casa cada resultado do servidor (nome vem com prefixo de data/hora,
        # ex.: "20260822_003000_venda.xlsx") com o arquivo local pelo final
        # do nome. Em caso de nome ambiguo (dois arquivos iguais no mesmo
        # lote), o arquivo NAO e marcado como enviado - sera reenviado na
        # proxima execucao, o que e seguro (nunca duplica).
        foreach ($par in $lote) {
            $f = $par.Info
            $correspondencias = @($dados.resultados | Where-Object { $_.arquivo.EndsWith($f.Name) })
            if ($correspondencias.Count -eq 1) {
                $r = $correspondencias[0]
                $nivel = if ($r.status -eq "ERRO") { "ERRO" } elseif ($r.status -eq "ATENCAO") { "AVISO" } else { "INFO" }
                $detalhe = "$($f.Name) [$($r.status)]"
                if ($r.titulo_dataset) { $detalhe += " - $($r.titulo_dataset)" }
                $detalhe += ": $($r.mensagem)"
                Escrever-Log $detalhe $nivel

                if ($r.status -ne "ERRO") {
                    Marcar-Enviado -Info $f -Tipo $par.Tipo -Manifesto $Manifesto
                    $totalOk++
                } else {
                    $totalErros++
                }
            } else {
                Escrever-Log "$($f.Name): nao foi possivel confirmar o resultado individual (sera conferido na proxima execucao)." "AVISO"
                $totalErros++
            }
        }

        # Salva o manifesto apos cada lote - se um lote mais adiante falhar,
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
