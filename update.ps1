[CmdletBinding()]
param(
    [string]$VaultPath,
    [ValidateSet("auto", "portable", "windows-wsl", "windows-native")]
    [string]$Platform = "auto",
    [switch]$Apply,
    [switch]$Force,
    [string]$SummaryProvider = "auto"
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = (Get-Location).Path
}

Write-Host "Respected Brain v0.0.1 — Windows Güncelleme Başlatıcı" -ForegroundColor Cyan

# 1. Python Tespiti
$Python = Get-Command python, py, python3 -All -ErrorAction SilentlyContinue | Where-Object {
    $_.Source -and -not $_.Source.ToLowerInvariant().Contains("\windowsapps\")
} | Select-Object -First 1

if (-not $Python) {
    Write-Host "HATA: Python 3 bulunamadı. Lütfen Python yükleyin: winget install Python.Python.3.13" -ForegroundColor Red
    exit 1
}

$PythonExe = $Python.Source
$PythonPrefix = @()
if ($Python.Name -match '^py(\.exe)?$') {
    $PythonPrefix = @("-3")
}

# 2. update.py tespiti veya indirme
$UpdateScript = Join-Path $RepoRoot "update.py"
if (-not (Test-Path -LiteralPath $UpdateScript)) {
    $TempClone = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-update-" + [guid]::NewGuid().ToString("N"))
    Write-Host "Güncelleme paketi indiriliyor..." -ForegroundColor Gray
    $HasGit = Get-Command git -ErrorAction SilentlyContinue
    if ($HasGit) {
        git clone --depth 1 https://github.com/respected0/secondbrain.git $TempClone | Out-Null
        $UpdateScript = Join-Path $TempClone "update.py"
    }
    else {
        $ZipFile = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-" + [guid]::NewGuid().ToString("N") + ".zip")
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://github.com/respected0/secondbrain/archive/refs/heads/main.zip" -OutFile $ZipFile
        Expand-Archive -LiteralPath $ZipFile -DestinationPath $TempClone -Force
        Remove-Item -LiteralPath $ZipFile -Force -ErrorAction SilentlyContinue
        $UnzippedSub = Join-Path $TempClone "secondbrain-main"
        if (Test-Path -LiteralPath $UnzippedSub) {
            $UpdateScript = Join-Path $UnzippedSub "update.py"
        } else {
            $UpdateScript = Join-Path $TempClone "update.py"
        }
    }
}

# 3. Argümanlar
$Arguments = @($PythonPrefix) + @('"' + $UpdateScript + '"')
if ($VaultPath) { $Arguments += @("--vault-path", '"' + $VaultPath + '"') }
if ($Platform) { $Arguments += @("--platform", $Platform) }
if ($Apply) { $Arguments += "--apply" }
if ($Force) { $Arguments += "--force" }
if ($SummaryProvider) { $Arguments += @("--summary-provider", $SummaryProvider) }

# 4. Çalıştır
$Process = Start-Process -FilePath $PythonExe -ArgumentList $Arguments -NoNewWindow -Wait -PassThru
exit $Process.ExitCode
