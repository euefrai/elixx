<#
.SYNOPSIS
  Instala o ELiXX no Windows (modo editavel, comando global `elixx`).

.EXAMPLE
  .\instalar.ps1

  Idempotente: pode rodar quantas vezes quiser. Nao duplica PATH,
  nao remove nada, nao baixa dependencias de runtime (ELiXX usa stdlib).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Dizer($msg) { Write-Host "[ELiXX] $msg" }

# 1. Pasta do projeto = pasta deste script
$Projeto = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $Projeto "pyproject.toml"))) {
    throw "pyproject.toml nao encontrado em $Projeto."
}

# 2. Detectar Python
$Python = $null
foreach ($cand in @("python", "py")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) {
        if ($cand -eq "py") {
            & py -3 --version 2>$null
            if ($LASTEXITCODE -eq 0) { $Python = "py -3"; break }
        } else { $Python = "python"; break }
    }
}
if (-not $Python) { throw "Python nao encontrado no PATH. Instale Python >= 3.10." }
$PyParts = $Python -split " "

# 3. Versao minima 3.10
$ver = & $PyParts --version 2>&1
Dizer "Python: $ver"
$num = [regex]::Match("$ver", "(\d+)\.(\d+)")
if (-not $num.Success -or [int]$num.Groups[1].Value -lt 3 -or
    ([int]$num.Groups[1].Value -eq 3 -and [int]$num.Groups[2].Value -lt 10)) {
    throw "ELiXX exige Python >= 3.10 (encontrado: $ver)."
}

# 4. Ferramentas locais (sem baixar nada se ja existirem)
& $PyParts -m pip --version >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Dizer "pip ausente - ativando via ensurepip (local, sem internet)..."
    & $PyParts -m ensurepip --upgrade
}
$temSetuptools = $true
& $PyParts -c "import setuptools" 2>$null
if ($LASTEXITCODE -ne 0) { $temSetuptools = $false }
if (-not $temSetuptools) {
    Dizer "setuptools ausente - instalando ferramenta de empacotamento..."
    & $PyParts -m pip install setuptools wheel
} else {
    Dizer "Ferramentas OK (pip + setuptools locais, nada a baixar)."
}

# 5. Instalar ELiXX em modo editavel
Dizer "Instalando ELiXX (pip install -e . em $Projeto)..."
Push-Location $Projeto
try {
    & $PyParts -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw "pip install -e . falhou." }
} finally {
    Pop-Location
}

# 6. Localizar diretorio de Scripts do Python
$ScriptsDir = (& $PyParts -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
Dizer "Scripts do Python: $ScriptsDir"

# 7. Verificar comando elixx na sessao atual
$elixx = Get-Command elixx -ErrorAction SilentlyContinue
if ($elixx) {
    Dizer "Comando encontrado: $($elixx.Source)"
} else {
    Dizer "Comando 'elixx' ainda nao visivel nesta sessao."
}

# 8. PATH (somente adiciona se faltar; nunca remove nem duplica)
$pathSessao = $env:Path -split ";" | Where-Object { $_ -ne "" }
$noPath = -not ($pathSessao | Where-Object {
    $_.TrimEnd("\") -ieq $ScriptsDir.TrimEnd("\") })
if ($noPath) {
    Dizer "Adicionando Scripts ao PATH do usuario (seguro: so anexa)..."
    $atual = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $atual) { $atual = "" }
    $jaTem = ($atual -split ";" | Where-Object { $_ -ne "" } | Where-Object {
        $_.TrimEnd("\") -ieq $ScriptsDir.TrimEnd("\") }).Count -gt 0
    if (-not $jaTem) {
        $novo = $atual.TrimEnd(";") + ";" + $ScriptsDir
        [Environment]::SetEnvironmentVariable("Path", $novo, "User")
        Dizer "PATH do usuario atualizado."
    }
    if ($env:Path -notlike "*$ScriptsDir*") {
        $env:Path = $env:Path.TrimEnd(";") + ";" + $ScriptsDir
    }
    Dizer "ATENCAO: PowerShells JA ABERTOS nao enxergam a mudanca. Abra um novo PowerShell."
} else {
    Dizer "PATH ja contem o Scripts. Nada a alterar."
}

# 9. Validar em NOVO processo (ambiente fresco)
Dizer "Validando em novo processo PowerShell..."
$saida = powershell -NoProfile -Command "elixx versao" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Validacao falhou: $saida"
    Write-Warning "Abra um NOVO PowerShell e rode: elixx versao"
} else {
    Dizer "OK: $saida"
    Dizer "Instalacao concluida. Use: elixx executar exemplos/interface.elixx"
}
