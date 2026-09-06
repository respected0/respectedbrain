param([string]$PythonExecutable = $env:RESPECTED_TEST_PYTHON)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonCommand = Get-Command py.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($PythonCommand) {
        $PythonExecutable = $PythonCommand.Source
        $PythonPrefix = @("-3")
    }
    else {
        $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
        if (-not (Test-Path -LiteralPath $BundledPython -PathType Leaf)) {
            throw "Python executable not found; pass -PythonExecutable explicitly"
        }
        $PythonExecutable = $BundledPython
        $PythonPrefix = @()
    }
}
else {
    $PythonPrefix = @()
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Invoke-Task([string[]]$Arguments) {
    $Stdout = [IO.Path]::GetTempFileName()
    $Stderr = [IO.Path]::GetTempFileName()
    try {
        $Process = Start-Process -FilePath "$env:SystemRoot\System32\schtasks.exe" -ArgumentList $Arguments -Wait -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
        return @{
            Code = $Process.ExitCode
            Output = [IO.File]::ReadAllText($Stdout) + [IO.File]::ReadAllText($Stderr)
        }
    }
    finally {
        Remove-Item -LiteralPath $Stdout, $Stderr -Force -ErrorAction SilentlyContinue
    }
}

$Repo = Split-Path -Parent $PSScriptRoot
$Scripts = Join-Path $Repo "scripts"
$Root = Join-Path ([IO.Path]::GetTempPath()) ("respected-schedule-" + [guid]::NewGuid().ToString("N"))
$Vault = Join-Path $Root "Ada Brain"
$Beyin = Join-Path $Vault ".beyin"
$CurrentTask = $null
$LegacyTask = $null

try {
    New-Item -ItemType Directory -Path $Beyin -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $Beyin "morning_briefing.py") -Value "# disposable worker" -Encoding UTF8

    $ResolvedVault = (Resolve-Path -LiteralPath $Vault).Path
    $HashBytes = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($ResolvedVault))
    $Digest = ([BitConverter]::ToString($HashBytes)).Replace("-", "").ToLowerInvariant().Substring(0, 12)
    $CurrentTask = "respected-morning-briefing-$Digest"
    $LegacyTask = ("res" + "pot-morning-briefing-" + $Digest)

    $TaskAction = '"' + "cmd.exe /c exit 0" + '"'
    $Created = Invoke-Task @("/Create", "/TN", $LegacyTask, "/SC", "ONCE", "/ST", "23:59", "/TR", $TaskAction, "/F")
    if ($Created.Code -ne 0) {
        Write-Host ("SKIP: Windows Task Scheduler test task could not be created: " + $Created.Output)
        exit 0
    }

    $Stdout = [IO.Path]::GetTempFileName()
    $Stderr = [IO.Path]::GetTempFileName()
    try {
        $Arguments = @($PythonPrefix) + @(
            '"' + (Join-Path $Scripts "install_briefing_schedule.py") + '"',
            '"' + $Vault + '"',
            "--home", '"' + $Root + '"',
            "--platform", "windows-native", "--apply"
        )
        $Process = Start-Process -FilePath $PythonExecutable -ArgumentList $Arguments -Wait -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
        $PythonOutput = [IO.File]::ReadAllText($Stdout) + [IO.File]::ReadAllText($Stderr)
        Assert-True ($Process.ExitCode -eq 0) ("Windows-native scheduler migration failed: " + $PythonOutput)
    }
    finally {
        Remove-Item -LiteralPath $Stdout, $Stderr -Force -ErrorAction SilentlyContinue
    }

    $CurrentQuery = Invoke-Task @("/Query", "/TN", $CurrentTask, "/XML")
    Assert-True ($CurrentQuery.Code -eq 0) "Current Respected briefing task is missing"
    Assert-True ($CurrentQuery.Output -match "conhost\.exe") "Current Respected briefing task must use conhost.exe"
    Assert-True ($CurrentQuery.Output -match "--headless") "Current Respected briefing task must use --headless"
    $LegacyQuery = Invoke-Task @("/Query", "/TN", $LegacyTask, "/XML")
    Assert-True ($LegacyQuery.Code -ne 0) "Legacy briefing task still exists after verified migration"
    Write-Host "ok - real Windows Task Scheduler legacy migration"
}
finally {
    foreach ($Task in @($CurrentTask, $LegacyTask)) {
        if ($Task) { $DeleteOutput = Invoke-Task @("/Delete", "/TN", $Task, "/F") }
    }
    Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
}
