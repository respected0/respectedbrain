[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$VaultPath,
    [Parameter(Mandatory = $true)][string]$UserName,
    [Parameter(Mandatory = $true)][string]$UserBio,
    [Parameter(Mandatory = $true)][string]$Companion,
    [Parameter(Mandatory = $true)][string]$OsName,
    [Parameter(Mandatory = $true)][string[]]$Providers,
    [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TemplateRoot = Join-Path $RepoRoot "template"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$SupportedProviders = @("antigravity", "codex", "cursor", "claude")
$ProviderCommands = @{
    antigravity = "agy"
    codex = "codex"
    cursor = "cursor-agent"
    claude = "claude"
}

function Stop-Install([string]$Message, [int]$Code = 2) {
    [Console]::Error.WriteLine("HATA: $Message")
    exit $Code
}

function Resolve-TestableCommand([string]$Name, [bool]$ProviderOnly = $false) {
    $TestRoot = $env:RESPECTED_TEST_COMMAND_ROOT
    if ($TestRoot) {
        foreach ($Extension in @(".exe", ".cmd", ".bat", "")) {
            $Candidate = Join-Path $TestRoot ($Name + $Extension)
            if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
                return $Candidate
            }
        }
        if ($ProviderOnly) {
            return $null
        }
    }
    $Resolved = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $Resolved) {
        return $null
    }
    return $Resolved.Source
}

function Invoke-ExternalProbe([string]$Command, [string[]]$Arguments) {
    $stdout = [IO.Path]::GetTempFileName()
    $stderr = [IO.Path]::GetTempFileName()
    $TimeoutMs = 15000
    if ($env:RESPECTED_PROBE_TIMEOUT_MS) {
        $ParsedTimeout = 0
        if ([int]::TryParse($env:RESPECTED_PROBE_TIMEOUT_MS, [ref]$ParsedTimeout) -and $ParsedTimeout -gt 0) {
            $TimeoutMs = $ParsedTimeout
        }
    }
    try {
        $ArgumentList = @($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' })
        $ProbeCommand = $Command
        $ProbeArguments = $ArgumentList
        $Extension = [IO.Path]::GetExtension($Command).ToLowerInvariant()
        if ($Extension -eq ".cmd" -or $Extension -eq ".bat") {
            $ProbeCommand = $env:ComSpec
            $QuotedCommand = '"' + $Command.Replace('"', '\"') + '"'
            $ProbeArguments = @(
                "/d",
                "/s",
                "/c",
                ("call " + $QuotedCommand + " " + ($ArgumentList -join " "))
            )
        }
        $Process = Start-Process -FilePath $ProbeCommand -ArgumentList $ProbeArguments -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        # PowerShell 5.1 can lose ExitCode for a short-lived child unless its
        # process handle is materialized before the child exits.
        $null = $Process.Handle
        $Completed = $Process.WaitForExit($TimeoutMs)
        if (-not $Completed) {
            $TaskKill = Join-Path $env:SystemRoot "System32\taskkill.exe"
            if (Test-Path -LiteralPath $TaskKill -PathType Leaf) {
                # Killing only cmd.exe leaves its CLI child alive with the
                # redirected handles open. Terminate the complete probe tree.
                & $TaskKill /PID $Process.Id /T /F *> $null
            }
            else {
                try {
                    $Process.Kill()
                }
                catch {
                    # The process may have exited between the timeout and Kill().
                }
            }
            $null = $Process.WaitForExit(2000)
            return @{
                Code = 124
                Output = ([IO.File]::ReadAllText($stdout) + [IO.File]::ReadAllText($stderr) + "probe-timeout")
            }
        }
        return @{
            Code = $Process.ExitCode
            Output = ([IO.File]::ReadAllText($stdout) + [IO.File]::ReadAllText($stderr))
        }
    }
    finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Find-Python {
    $Candidates = @()
    if ($env:RESPECTED_TEST_PYTHON) {
        $Candidates += ,@($env:RESPECTED_TEST_PYTHON, @())
    }
    else {
        $Candidates += ,@((Resolve-TestableCommand "py"), @("-3"))
        $Candidates += ,@((Resolve-TestableCommand "python"), @())
        $Candidates += ,@((Resolve-TestableCommand "python3"), @())
    }
    foreach ($Candidate in $Candidates) {
        $Command = $Candidate[0]
        $Prefix = @($Candidate[1])
        if (-not $Command) {
            continue
        }
        if ($Command.ToLowerInvariant().Contains("\windowsapps\")) {
            continue
        }
        $ProbeArguments = @($Prefix) + @(
            "-c",
            "import sys; print('RESPECTED_PYTHON_OK'); print(sys.executable); print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"
        )
        $Probe = Invoke-ExternalProbe $Command $ProbeArguments
        $ProbeOutput = $Probe.Output
        if ($Probe.Code -ne 0) {
            continue
        }
        $Lower = $ProbeOutput.ToLowerInvariant()
        if (-not $ProbeOutput.Contains("RESPECTED_PYTHON_OK") -or $Lower.Contains("microsoft store") -or $Lower.Contains("python was not found")) {
            continue
        }
        return @{ Command = $Command; Prefix = $Prefix; Probe = $ProbeOutput.Trim() }
    }
    return $null
}

function Invoke-Python([hashtable]$Python, [string[]]$Arguments) {
    $AllArguments = @($Python.Prefix) + $Arguments
    $Result = Invoke-ExternalProbe $Python.Command $AllArguments
    if ($Result.Output) {
        Write-Host $Result.Output.Trim()
    }
    if ($Result.Code -ne 0) {
        throw "Python komutu başarısız (exit $($Result.Code)): $($Arguments -join ' ')"
    }
}

function Test-Provider([string]$Provider) {
    $Name = $ProviderCommands[$Provider]
    $Command = Resolve-TestableCommand $Name $true
    if (-not $Command -and $Name -eq "agy" -and $env:LOCALAPPDATA) {
        $AgyRoot = Join-Path $env:LOCALAPPDATA "agy\bin"
        foreach ($Extension in @(".exe", ".cmd", ".bat", "")) {
            $Candidate = Join-Path $AgyRoot ("agy" + $Extension)
            if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
                $Command = $Candidate
                break
            }
        }
    }
    if (-not $Command) {
        return $false
    }
    $Probe = Invoke-ExternalProbe $Command @("--version")
    return $Probe.Code -eq 0
}

if (-not (Test-Path -LiteralPath $TemplateRoot -PathType Container)) {
    Stop-Install "template klasörü bulunamadı: $TemplateRoot"
}

$NormalizedProviders = @()
foreach ($Item in $Providers) {
    foreach ($Part in $Item.Split(',')) {
        $Value = $Part.Trim().ToLowerInvariant()
        if ($Value -and -not $NormalizedProviders.Contains($Value)) {
            $NormalizedProviders += $Value
        }
    }
}
if ($NormalizedProviders.Count -eq 0) {
    Stop-Install "en az bir provider seçilmeli: antigravity, codex, cursor, claude"
}
foreach ($Provider in $NormalizedProviders) {
    if (-not $SupportedProviders.Contains($Provider)) {
        Stop-Install "bilinmeyen provider: $Provider"
    }
}

$Git = Resolve-TestableCommand "git"
if (-not $Git) {
    Stop-Install "Git bulunamadı. Kur: https://git-scm.com/download/win"
}
$GitProbe = Invoke-ExternalProbe $Git @("--version")
if ($GitProbe.Code -ne 0) {
    Stop-Install "Git sürüm kontrolü başarısız. Kur: https://git-scm.com/download/win"
}

$Python = Find-Python
if ($null -eq $Python) {
    Stop-Install "Gerçek Python 3 bulunamadı; Microsoft Store aliası yeterli değildir. Kur: winget install Python.Python.3.13"
}

$MissingProviders = @()
foreach ($Provider in $NormalizedProviders) {
    if (-not (Test-Provider $Provider)) {
        $MissingProviders += "$Provider ($($ProviderCommands[$Provider]))"
    }
}
if ($MissingProviders.Count -gt 0) {
    Stop-Install ("Seçili provider CLI bulunamadı veya çalışmıyor: " + ($MissingProviders -join ", "))
}

Write-Host "Python: $($Python.Probe.Split([Environment]::NewLine)[0])"
Write-Host "Provider: $($NormalizedProviders -join ', ')"
Write-Host "Platform: windows-native"
if ($PreflightOnly) {
    Write-Host "ÖN KONTROL TAMAM: hiçbir dosya değişmedi."
    exit 0
}

$ResolvedVault = [IO.Path]::GetFullPath($VaultPath)
$TargetExisted = Test-Path -LiteralPath $ResolvedVault
if ($TargetExisted) {
    if (-not (Test-Path -LiteralPath $ResolvedVault -PathType Container)) {
        Stop-Install "hedef bir klasör değil: $ResolvedVault" 3
    }
    if (@(Get-ChildItem -LiteralPath $ResolvedVault -Force).Count -gt 0) {
        Stop-Install "hedef klasör boş değil; hiçbir dosya değiştirilmedi: $ResolvedVault" 3
    }
}

$CreatedTarget = $false
try {
    if (-not $TargetExisted) {
        New-Item -ItemType Directory -Path $ResolvedVault | Out-Null
        $CreatedTarget = $true
    }
    foreach ($Item in Get-ChildItem -LiteralPath $TemplateRoot -Force) {
        Copy-Item -LiteralPath $Item.FullName -Destination $ResolvedVault -Recurse -Force
    }

    $Replacements = @{
        "{{OS_NAME}}" = $OsName
        "{{USER_NAME}}" = $UserName
        "{{USER_BIO}}" = $UserBio
        "{{COMPANION}}" = $Companion
        "{{VAULT_PATH}}" = $ResolvedVault
        "{{TODAY}}" = (Get-Date -Format "yyyy-MM-dd")
    }
    foreach ($File in Get-ChildItem -LiteralPath $ResolvedVault -File -Recurse -Force) {
        $Content = [IO.File]::ReadAllText($File.FullName)
        $Updated = $Content
        foreach ($Placeholder in $Replacements.Keys) {
            $Updated = $Updated.Replace($Placeholder, $Replacements[$Placeholder])
        }
        if ($Updated -ne $Content) {
            [IO.File]::WriteAllText($File.FullName, $Updated, $Utf8NoBom)
        }
    }

    Invoke-Python $Python @(
        (Join-Path $ResolvedVault "scripts\render_integrations.py"),
        "--root", $ResolvedVault,
        "--platform", "windows-native"
    )
    Invoke-Python $Python @(
        (Join-Path $ResolvedVault "scripts\render_integrations.py"),
        "--root", $ResolvedVault,
        "--check"
    )

    $Remaining = Get-ChildItem -LiteralPath $ResolvedVault -File -Recurse -Force | Where-Object {
        [regex]::IsMatch([IO.File]::ReadAllText($_.FullName), '\{\{[A-Z][A-Z0-9_]*\}\}')
    }
    if (@($Remaining).Count -gt 0) {
        throw "çözülmemiş placeholder: $($Remaining[0].FullName)"
    }
    if (([IO.File]::ReadAllText((Join-Path $ResolvedVault ".beyin-version"))).Trim() -ne "2.0.0") {
        throw ".beyin-version gate başarısız"
    }
    if (([IO.File]::ReadAllText((Join-Path $ResolvedVault ".beyin-multi-version"))).Trim() -ne "1.3.0") {
        throw ".beyin-multi-version gate başarısız"
    }
    $AdapterPaths = @(
        (Join-Path $ResolvedVault ".claude\settings.json"),
        (Join-Path $ResolvedVault ".codex\hooks.json"),
        (Join-Path $ResolvedVault ".cursor\hooks.json"),
        (Join-Path $ResolvedVault ".agents\hooks.json")
    )
    $AdapterText = ($AdapterPaths | ForEach-Object { [IO.File]::ReadAllText($_) }) -join "`n"
    $LowerAdapters = $AdapterText.ToLowerInvariant()
    if (-not $AdapterText.Contains("py.exe") -or $LowerAdapters.Contains("wsl.exe") -or $LowerAdapters.Contains("bash") -or $LowerAdapters.Contains(".sh")) {
        throw "windows-native adapter gate başarısız"
    }
}
catch {
    if ($CreatedTarget -and (Test-Path -LiteralPath $ResolvedVault)) {
        Remove-Item -LiteralPath $ResolvedVault -Recurse -Force
    }
    elseif ($TargetExisted -and (Test-Path -LiteralPath $ResolvedVault)) {
        Get-ChildItem -LiteralPath $ResolvedVault -Force | Remove-Item -Recurse -Force
    }
    Stop-Install ("kurulum geri alındı: " + $_.Exception.Message)
}

Write-Host "Respected Brain kuruldu: $ResolvedVault"
Write-Host "Sürüm: core 2.0.0 / multi-AI 1.3.0"
Write-Host "Global bağlantı ayrı ve seçicidir; SETUP-WINDOWS.md içindeki install_global.py adımını kullan."
exit 0
