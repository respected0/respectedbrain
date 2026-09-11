[CmdletBinding()]
param(
    [string]$VaultPath,
    [string]$UserName,
    [string]$UserBio = "Geliştirici & Mühendis",
    [string]$Companion = "Jarvis",
    [string]$OsName = "RespectedOS",
    [string]$Provider = "auto",
    [string[]]$Priority,
    [ValidateSet("native", "wsl", "hybrid")]
    [string]$Environment,
    [switch]$DesktopShortcut,
    [switch]$NoDesktopShortcut,
    [switch]$InstallSchedule,
    [switch]$NoInstallSchedule,
    [string]$ScheduleTime = "08:00",
    [switch]$Defaults,
    [switch]$InstallGlobal,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = (Get-Location).Path
}

Write-Host "Respected Brain v0.0.1 — Windows Kurulum Başlatıcı" -ForegroundColor Cyan

# 1. Python Tespiti ve Otomatik Yükleme Teklifi
$Python = Get-Command python, py, python3 -All -ErrorAction SilentlyContinue | Where-Object {
    $_.Source -and -not $_.Source.ToLowerInvariant().Contains("\windowsapps\")
} | Select-Object -First 1

if (-not $Python) {
    Write-Host "UYARI: Sisteminizde Python 3 tespit edilemedi." -ForegroundColor Yellow
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($Winget) {
        $InstallChoice = Read-Host "Windows Paket Yöneticisi (winget) ile Python 3.13 otomatik yüklensin mi? [E/h]"
        if (-not $InstallChoice -or $InstallChoice -match '^(e|evet|y|yes)$') {
            Write-Host "Python 3.13 kuruluyor (winget)..." -ForegroundColor Cyan
            winget install --id Python.Python.3.13 -e --source winget --accept-package-agreements --accept-source-agreements
            # Yeniden tara
            $Python = Get-Command python, py, python3 -All -ErrorAction SilentlyContinue | Where-Object {
                $_.Source -and -not $_.Source.ToLowerInvariant().Contains("\windowsapps\")
            } | Select-Object -First 1
        }
    }
    if (-not $Python) {
        Write-Host "HATA: Python 3 bulunamadı. Lütfen Python yükleyin: winget install Python.Python.3.13" -ForegroundColor Red
        exit 1
    }
}

$PythonExe = $Python.Source
$PythonPrefix = @()
if ($Python.Name -match '^py(\.exe)?$') {
    $PythonPrefix = @("-3")
}

# 2. install.py konumu
$InstallScript = Join-Path $RepoRoot "install.py"
if (-not (Test-Path -LiteralPath $InstallScript)) {
    # Eğer web üzerinden tek satırla indiriliyorsa repoyu temp dizine klonla veya zip olarak çek
    $TempClone = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-install-" + [guid]::NewGuid().ToString("N"))
    Write-Host "Repo indiriliyor..." -ForegroundColor Gray
    $HasGit = Get-Command git -ErrorAction SilentlyContinue
    if ($HasGit) {
        git clone --depth 1 https://github.com/respected0/secondbrain.git $TempClone | Out-Null
        $InstallScript = Join-Path $TempClone "install.py"
    }
    else {
        Write-Host "Git tespit edilemedi, GitHub arşivi indiriliyor..." -ForegroundColor Gray
        $ZipFile = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-" + [guid]::NewGuid().ToString("N") + ".zip")
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://github.com/respected0/secondbrain/archive/refs/heads/main.zip" -OutFile $ZipFile
        Expand-Archive -LiteralPath $ZipFile -DestinationPath $TempClone -Force
        Remove-Item -LiteralPath $ZipFile -Force -ErrorAction SilentlyContinue
        $UnzippedSub = Join-Path $TempClone "secondbrain-main"
        if (Test-Path -LiteralPath $UnzippedSub) {
            $InstallScript = Join-Path $UnzippedSub "install.py"
        } else {
            $InstallScript = Join-Path $TempClone "install.py"
        }
    }
}

# 3. Argümanları hazırla
$Arguments = @($PythonPrefix) + @('"' + $InstallScript + '"')

if ($VaultPath) { $Arguments += @("--vault-path", '"' + $VaultPath + '"') }
if ($UserName) { $Arguments += @("--user-name", '"' + $UserName + '"') }
if ($UserBio) { $Arguments += @("--user-bio", '"' + $UserBio + '"') }
if ($Companion) { $Arguments += @("--companion", '"' + $Companion + '"') }
if ($OsName) { $Arguments += @("--os-name", '"' + $OsName + '"') }
if ($Provider) { $Arguments += @("--provider", $Provider) }
if ($Priority) { $Arguments += @("--priority") + $Priority }
if ($Environment) { $Arguments += @("--environment", $Environment) }
if ($DesktopShortcut) { $Arguments += "--desktop-shortcut" }
if ($NoDesktopShortcut) { $Arguments += "--no-desktop-shortcut" }
if ($InstallSchedule) { $Arguments += "--install-schedule" }
if ($NoInstallSchedule) { $Arguments += "--no-install-schedule" }
if ($ScheduleTime) { $Arguments += @("--schedule-time", $ScheduleTime) }
if ($Defaults) { $Arguments += "--defaults" }
if ($InstallGlobal) { $Arguments += "--install-global" }
if ($Quiet) { $Arguments += "--quiet" }

# 4. Çalıştır
$Process = Start-Process -FilePath $PythonExe -ArgumentList $Arguments -NoNewWindow -Wait -PassThru
exit $Process.ExitCode
