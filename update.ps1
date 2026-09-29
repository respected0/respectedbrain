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
        try {
            $Probe = (& $Candidate[0] @($Candidate[1]) -c "import sys; print('RESPECTED_PYTHON_OK'); print(sys.executable)" 2>&1 | Out-String)
            if ($LASTEXITCODE -eq 0 -and $Probe.Contains("RESPECTED_PYTHON_OK") -and -not $Probe.ToLowerInvariant().Contains("microsoft store")) {
                return @{ Command = $Candidate[0]; Prefix = @($Candidate[1]) }
            }
        }
        catch { }
    }
    return $null
}

$Python = Find-RespectedPython

if (-not $Python) {
    Write-Host "HATA: Python 3 bulunamadı. Lütfen Python yükleyin: winget install Python.Python.3.13" -ForegroundColor Red
    exit 1
}

$PythonExe = $Python.Command
$PythonPrefix = @($Python.Prefix)

$TempClone = $null
$ExitCode = 1
try {
# 2. update.py tespiti veya indirme
$UpdateScript = Join-Path $RepoRoot "update.py"
if (-not (Test-Path -LiteralPath $UpdateScript)) {
    $TempClone = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-update-" + [guid]::NewGuid().ToString("N"))
    Write-Host "Güncelleme paketi indiriliyor..." -ForegroundColor Gray
    $HasGit = Get-Command git -ErrorAction SilentlyContinue
    if ($HasGit) {
        git clone --depth 1 https://github.com/respected0/respectedbrain.git $TempClone | Out-Null
        $UpdateScript = Join-Path $TempClone "update.py"
    }
    else {
        $ZipFile = Join-Path ([IO.Path]::GetTempPath()) ("respected-brain-" + [guid]::NewGuid().ToString("N") + ".zip")
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://github.com/respected0/respectedbrain/archive/refs/heads/main.zip" -OutFile $ZipFile
        Expand-Archive -LiteralPath $ZipFile -DestinationPath $TempClone -Force
        Remove-Item -LiteralPath $ZipFile -Force -ErrorAction SilentlyContinue
        $UnzippedSub = Join-Path $TempClone "respectedbrain-main"
        if (Test-Path -LiteralPath $UnzippedSub) {
            $UpdateScript = Join-Path $UnzippedSub "update.py"
        } else {
            $UpdateScript = Join-Path $TempClone "update.py"
        }
    }
}

# 3. Argümanlar
$Arguments = @($PythonPrefix) + @($UpdateScript)
if ($VaultPath) { $Arguments += @("--vault-path", $VaultPath) }
if ($Platform) { $Arguments += @("--platform", $Platform) }
if ($Apply) { $Arguments += "--apply" }
if ($Force) { $Arguments += "--force" }
if ($SummaryProvider) { $Arguments += @("--summary-provider", $SummaryProvider) }

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
