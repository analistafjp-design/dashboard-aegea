<#
.SINOPSE
    Configura as pastas do OneDrive e cria o atalho manual na Area de Trabalho.

.DESCRICAO
    Grava a configuracao local das quatro pastas informadas pelo usuario,
    solicita a URL e as credenciais opcionais do dashboard e cria o atalho
    "Atualizar Dashboard AEGEA". Nao cria tarefas agendadas.
#>

param([string]$RaizOneDrive = "")

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$ArquivoPastas = Join-Path $PastaScript "pastas-monitoradas.txt"
$ArquivoCredenciais = Join-Path $PastaScript "credenciais.txt"
$Botao = Join-Path $PastaScript "ATUALIZAR_DASHBOARD.cmd"

Write-Host "Configuracao do botao Atualizar Dashboard AEGEA" -ForegroundColor Cyan
Write-Host ""

# Descobre a pasta pelo perfil do Windows. Isso evita depender do nome do
# usuario e tambem contorna a leitura incorreta de acentos no Windows
# PowerShell 5.1 quando um arquivo UTF-8 sem BOM vem do GitHub.
if (-not $RaizOneDrive) {
    $RaizOneDrive = Get-ChildItem -Path $env:USERPROFILE -Directory -Filter "OneDrive*" -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "DashBoard - Interior" } |
        Where-Object { Test-Path $_ -PathType Container } |
        Select-Object -First 1
}

if (-not (Test-Path $RaizOneDrive -PathType Container)) {
    Write-Host "A pasta padrao nao foi encontrada:" -ForegroundColor Yellow
    Write-Host $RaizOneDrive -ForegroundColor Yellow
    $Informada = Read-Host "Cole o caminho da pasta 'DashBoard - Interior'"
    if ($Informada) { $RaizOneDrive = $Informada.Trim().Trim('"') }
}

if (-not (Test-Path $RaizOneDrive -PathType Container)) {
    Write-Host "ERRO: a pasta informada nao existe: $RaizOneDrive" -ForegroundColor Red
    exit 1
}

$PastaProgramacao = Get-ChildItem -Path $RaizOneDrive -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "Programa*Di*ria" } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $PastaProgramacao) {
    # Monta "Programacao" com cedilha e til sem caracteres nao ASCII no
    # codigo-fonte, mantendo compatibilidade com o PowerShell antigo.
    $NomeProgramacao = "Programa{0}{1}o Diaria" -f [char]0x00E7, [char]0x00E3
    $PastaProgramacao = Join-Path $RaizOneDrive $NomeProgramacao
}

$Mapeamentos = @(
    "$(Join-Path $RaizOneDrive 'Atendimento') = atendimento",
    "$(Join-Path $RaizOneDrive 'Faturamento') = faturamento",
    "$(Join-Path $RaizOneDrive 'Interior') = vendas, implantacao, termos",
    "$PastaProgramacao = programacao"
)

$PastasAusentes = @($Mapeamentos | ForEach-Object {
    $Caminho = ($_ -split '\s+=\s+', 2)[0]
    if (-not (Test-Path $Caminho -PathType Container)) { $Caminho }
})
if ($PastasAusentes.Count -gt 0) {
    Write-Host "ERRO: estas subpastas nao foram encontradas:" -ForegroundColor Red
    $PastasAusentes | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}

$Mapeamentos | Set-Content -Path $ArquivoPastas -Encoding UTF8

$UrlPadrao = "https://dashboard-executivo.onrender.com"
$Url = Read-Host "URL publica do dashboard [$UrlPadrao]"
if (-not $Url) { $Url = $UrlPadrao }
$Url = $Url.Trim().TrimEnd("/")

$Usuario = Read-Host "Usuario do dashboard (Enter se nao houver login)"
$SenhaTexto = ""
if ($Usuario) {
    $SenhaSegura = Read-Host "Senha do dashboard" -AsSecureString
    $Ponteiro = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SenhaSegura)
    try {
        $SenhaTexto = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ponteiro)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ponteiro)
    }
}

@(
    "URL=$Url",
    "USUARIO=$Usuario",
    "SENHA=$SenhaTexto"
) | Set-Content -Path $ArquivoCredenciais -Encoding UTF8

$AreaDeTrabalho = [Environment]::GetFolderPath("Desktop")
$CaminhoAtalho = Join-Path $AreaDeTrabalho "Atualizar Dashboard AEGEA.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Atalho = $Shell.CreateShortcut($CaminhoAtalho)
$Atalho.TargetPath = $Botao
$Atalho.WorkingDirectory = $PastaScript
$Atalho.Description = "Envia arquivos novos ou alterados do OneDrive para o Dashboard AEGEA"
$Atalho.Save()

Write-Host ""
Write-Host "Configuracao concluida." -ForegroundColor Green
Write-Host "Atalho criado em: $CaminhoAtalho" -ForegroundColor Green
Write-Host "A atualizacao ocorrera somente quando voce clicar no atalho." -ForegroundColor Green
exit 0
