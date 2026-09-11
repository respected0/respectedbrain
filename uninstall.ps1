[CmdletBinding()]
param(
    [string]$VaultPath,
    [switch]$PurgeVault,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = (Get-Location).Path
}

Write-Host "Respected Brain v0.0.1 — Windows Kaldırma Başlatıcı (Uninstaller)" -ForegroundColor Cyan

# 1. Python Tespiti
$Python = Get-Command python, py, python3 -All -ErrorAction SilentlyContinue | Where-Object {
    $_.Source -and -not $_.Source.ToLowerInvariant().Contains("\windowsapps\")
} | Select-Object -First 1

if (-not $Python) {
    Write-Host "HATA: Python 3 bulunamadı." -ForegroundColor Red
    exit 1
}

$PythonExe = $Python.Source
$PythonPrefix = @()
if ($Python.Name -match '^py(\.exe)?$') {
    $PythonPrefix = @("-3")
}

# 2. uninstall.py tespiti veya indirme
$UninstallScript = Join-Path $RepoRoot "uninstall.py"
if (-not (Test-Path -LiteralPath $UninstallScript)) {
    $TempClone = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-uninstall-" + [guid]::NewGuid().ToString("N"))
    Write-Host "Kaldırma aracı indiriliyor..." -ForegroundColor Gray
    $HasGit = Get-Command git -ErrorAction SilentlyContinue
    if ($HasGit) {
        git clone --depth 1 https://github.com/respected0/secondbrain.git $TempClone | Out-Null
        $UninstallScript = Join-Path $TempClone "uninstall.py"
    }
    else {
        $ZipFile = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-" + [guid]::NewGuid().ToString("N") + ".zip")
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://github.com/respected0/secondbrain/archive/refs/heads/main.zip" -OutFile $ZipFile
        Expand-Archive -LiteralPath $ZipFile -DestinationPath $TempClone -Force
        Remove-Item -LiteralPath $ZipFile -Force -ErrorAction SilentlyContinue
        $UnzippedSub = Join-Path $TempClone "secondbrain-main"
        if (Test-Path -LiteralPath $UnzippedSub) {
            $UninstallScript = Join-Path $UnzippedSub "uninstall.py"
        } else {
            $UninstallScript = Join-Path $TempClone "uninstall.py"
        }
    }
}

# 3. Argümanlar
$Arguments = @($PythonPrefix) + @('"' + $UninstallScript + '"')
if ($VaultPath) { $Arguments += @("--vault-path", '"' + $VaultPath + '"') }
if ($PurgeVault) { $Arguments += "--purge-vault" }
if ($NonInteractive) { $Arguments += "--non-interactive" }

# 4. Çalıştır
$Process = Start-Process -FilePath $PythonExe -ArgumentList $Arguments -NoNewWindow -Wait -PassThru
exit $Process.ExitCode
