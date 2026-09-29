[CmdletBinding()]
param(
    [string]$VaultPath,
    [string]$UserName,
    [string]$UserBio = "Geliştirici & Mühendis",
    [string]$Companion = "Jarvis",
    [string]$OsName = "RespectedOS",
    [string]$Provider = "auto",
    [string[]]$Priority,
    [string]$Environment,
    [switch]$DesktopShortcut,
    [switch]$NoDesktopShortcut,
    [switch]$InstallSchedule,
    [switch]$NoInstallSchedule,
    [string]$ScheduleTime = "08:00",
    [switch]$Defaults,
    [switch]$InstallGlobal,
    [switch]$InstallMcp,
    [switch]$NoInstallMcp,
    [switch]$Quiet
)

if ($Environment -and $Environment -notin @("native", "wsl", "hybrid")) {
    throw "Environment must be one of: native, wsl, hybrid"
}

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = (Get-Location).Path
}

Write-Host "Respected Brain v0.0.1 — Windows Kurulum Başlatıcı" -ForegroundColor Cyan

# 1. Python Tespiti ve Otomatik Yükleme Teklifi
function Find-RespectedPython {
    $Candidates = @()
    foreach ($Resolved in @(Get-Command python, py, python3 -All -ErrorAction SilentlyContinue)) {
        if ($Resolved.Source -and -not $Resolved.Source.ToLowerInvariant().Contains("\windowsapps\")) {
            $Prefix = if ($Resolved.Name -match '^py(\.exe)?$') { @("-3") } else { @() }
            $Candidates += ,@($Resolved.Source, $Prefix)
        }
    }
    if ($env:LOCALAPPDATA) {
        foreach ($Root in @((Join-Path $env:LOCALAPPDATA "Python"), (Join-Path $env:LOCALAPPDATA "Programs\Python"))) {
            foreach ($Candidate in @(Get-ChildItem -LiteralPath $Root -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue)) {
                $Candidates += ,@($Candidate.FullName, @())
            }
        }
    }
    foreach ($Candidate in $Candidates) {
        $Command = $Candidate[0]
        $Prefix = @($Candidate[1])
        try {
            $ProbeLines = @(& $Command @Prefix -c "import sys; print('RESPECTED_PYTHON_OK'); print(sys.executable)" 2>&1)
            $ProbeExit = $LASTEXITCODE
            $Probe = ($ProbeLines | ForEach-Object { "$_" }) -join "`n"
            if ($ProbeExit -eq 0 -and $Probe.Contains("RESPECTED_PYTHON_OK") -and -not $Probe.ToLowerInvariant().Contains("microsoft store")) {
                $RuntimeValue = $ProbeLines | ForEach-Object { "$_" } | Where-Object { $_ -and $_ -ne "RESPECTED_PYTHON_OK" } | Select-Object -Last 1
                $RuntimeCommand = if ($RuntimeValue) { ([string]$RuntimeValue).Trim() } else { $Command }
                if (-not $RuntimeCommand) { $RuntimeCommand = $Command }
                return @{ Command = $Command; Prefix = $Prefix; RuntimeCommand = $RuntimeCommand }
            }
        }
        catch { }
    }
    return $null
}

$Python = Find-RespectedPython

if (-not $Python) {
    Write-Host "UYARI: Sisteminizde Python 3 tespit edilemedi." -ForegroundColor Yellow
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($Winget) {
        $InstallChoice = Read-Host "Windows Paket Yöneticisi (winget) ile Python 3.13 otomatik yüklensin mi? [E/h]"
        if (-not $InstallChoice -or $InstallChoice -match '^(e|evet|y|yes)$') {
            Write-Host "Python 3.13 kuruluyor (winget)..." -ForegroundColor Cyan
            & $Winget.Source install --id Python.Python.3.13 -e --source winget --accept-package-agreements --accept-source-agreements
            $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
            $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
            $env:PATH = "$MachinePath;$UserPath"
            $Python = Find-RespectedPython
        }
    }
    if (-not $Python) {
        Write-Host "HATA: Python 3 bulunamadı. Lütfen Python yükleyin: winget install Python.Python.3.13" -ForegroundColor Red
        exit 1
    }
}

$PythonExe = $Python.Command
$PythonPrefix = @($Python.Prefix)
$PythonRuntime = $Python.RuntimeCommand

$TempClone = $null
$ExitCode = 1
try {
# 2. install.py konumu
$InstallScript = Join-Path $RepoRoot "install.py"
if (-not (Test-Path -LiteralPath $InstallScript)) {
    # Eğer web üzerinden tek satırla indiriliyorsa repoyu temp dizine klonla veya zip olarak çek
    $TempClone = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-install-" + [guid]::NewGuid().ToString("N"))
    Write-Host "Repo indiriliyor..." -ForegroundColor Gray
    $HasGit = Get-Command git -ErrorAction SilentlyContinue
    if ($HasGit) {
        git clone --depth 1 https://github.com/respected0/respectedbrain.git $TempClone | Out-Null
        $InstallScript = Join-Path $TempClone "install.py"
    }
    else {
        Write-Host "Git tespit edilemedi, GitHub arşivi indiriliyor..." -ForegroundColor Gray
        $ZipFile = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-" + [guid]::NewGuid().ToString("N") + ".zip")
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://github.com/respected0/respectedbrain/archive/refs/heads/main.zip" -OutFile $ZipFile
        Expand-Archive -LiteralPath $ZipFile -DestinationPath $TempClone -Force
        Remove-Item -LiteralPath $ZipFile -Force -ErrorAction SilentlyContinue
        $UnzippedSub = Join-Path $TempClone "respectedbrain-main"
        if (Test-Path -LiteralPath $UnzippedSub) {
            $InstallScript = Join-Path $UnzippedSub "install.py"
        } else {
            $InstallScript = Join-Path $TempClone "install.py"
        }
    }
}

# 3. Argümanları hazırla
$Arguments = @($PythonPrefix) + @($InstallScript)

if ($VaultPath) { $Arguments += @("--vault-path", $VaultPath) }
if ($UserName) { $Arguments += @("--user-name", $UserName) }
if ($UserBio) { $Arguments += @("--user-bio", $UserBio) }
if ($Companion) { $Arguments += @("--companion", $Companion) }
if ($OsName) { $Arguments += @("--os-name", $OsName) }
if ($Provider) { $Arguments += @("--provider", $Provider) }
if ($Priority) { $Arguments += @("--priority") + $Priority }
if ($Environment) { $Arguments += @("--environment", $Environment) }
$Arguments += @("--python-executable", $PythonRuntime)
if ($DesktopShortcut) { $Arguments += "--desktop-shortcut" }
if ($NoDesktopShortcut) { $Arguments += "--no-desktop-shortcut" }
if ($InstallSchedule) { $Arguments += "--install-schedule" }
if ($NoInstallSchedule) { $Arguments += "--no-install-schedule" }
if ($ScheduleTime) { $Arguments += @("--schedule-time", $ScheduleTime) }
if ($Defaults) { $Arguments += "--defaults" }
if ($InstallGlobal) { $Arguments += "--install-global" }
if ($InstallMcp) { $Arguments += "--install-mcp" }
if ($NoInstallMcp) { $Arguments += "--no-install-mcp" }
if ($Quiet) { $Arguments += "--quiet" }

# 4. Çalıştır
& $PythonExe @Arguments
$ExitCode = $LASTEXITCODE
}
finally {
    if ($TempClone -and (Test-Path -LiteralPath $TempClone)) {
        Remove-Item -LiteralPath $TempClone -Recurse -Force -ErrorAction SilentlyContinue
    }
}
exit $ExitCode
