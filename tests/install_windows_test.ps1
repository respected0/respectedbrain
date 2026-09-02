$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $PSScriptRoot
$Installer = Join-Path $Repo "scripts\install-windows.ps1"
$Failures = 0
$PowerShellHost = (Get-Process -Id $PID).Path
$OriginalUserProfile = $env:USERPROFILE
$WorkingPythonOverride = $null
if (-not (Get-Command py, python, python3 -ErrorAction SilentlyContinue | Select-Object -First 1)) {
    $BundledPython = Join-Path $OriginalUserProfile ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $BundledPython -PathType Leaf) {
        $WorkingPythonOverride = $BundledPython
    }
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        Write-Host "FAIL: $Message" -ForegroundColor Red
        $script:Failures++
    }
}

function Invoke-Installer([string[]]$Arguments) {
    $stdout = [IO.Path]::GetTempFileName()
    $stderr = [IO.Path]::GetTempFileName()
    try {
        $QuotedInstaller = '"' + $Installer.Replace('"', '\"') + '"'
        $QuotedArguments = @($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' })
        $process = Start-Process -FilePath $PowerShellHost -ArgumentList (@("-NoProfile", "-File", $QuotedInstaller) + $QuotedArguments) -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $output = ([IO.File]::ReadAllText($stdout) + [IO.File]::ReadAllText($stderr))
        return @{ Code = $process.ExitCode; Output = $output }
    }
    finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function New-ProviderStub([string]$Root, [string]$Name) {
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    $path = Join-Path $Root "$Name.cmd"
    [IO.File]::WriteAllText($path, "@echo off`r`necho $Name test-cli 1.0`r`nexit /b 0`r`n", [Text.UTF8Encoding]::new($false))
}

if (-not (Test-Path -LiteralPath $Installer)) {
    Write-Error "Windows installer bulunamadı: $Installer"
}

$Root = Join-Path ([IO.Path]::GetTempPath()) ("respected-win-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Root | Out-Null
try {
    $Commands = Join-Path $Root "commands"
    New-ProviderStub $Commands "codex"
    New-ProviderStub $Commands "git"
    $env:RESPECTED_TEST_COMMAND_ROOT = $Commands
    $LegacyCommands = Join-Path $Root "ignored-legacy-commands"
    New-Item -ItemType Directory -Path $LegacyCommands | Out-Null
    $env:RESPOT_TEST_COMMAND_ROOT = $LegacyCommands
    $env:USERPROFILE = Join-Path $Root "profile"
    New-Item -ItemType Directory -Path $env:USERPROFILE | Out-Null
    if ($WorkingPythonOverride) {
        $env:RESPECTED_TEST_PYTHON = $WorkingPythonOverride
    }
    $null = Start-Process -FilePath $PowerShellHost -ArgumentList @("-NoProfile", "-Command", "exit 0") -Wait -PassThru

    $PreflightVault = Join-Path $Root "preflight-vault"
    $Before = @(Get-ChildItem -LiteralPath $env:USERPROFILE -Force -Recurse | ForEach-Object FullName | Sort-Object)
    $preflight = Invoke-Installer @(
        "-VaultPath", $PreflightVault, "-UserName", "Ada", "-UserBio", "Geliştirici",
        "-Companion", "Echo", "-OsName", "AdaOS", "-Providers", "codex", "-PreflightOnly"
    )
    $After = @(Get-ChildItem -LiteralPath $env:USERPROFILE -Force -Recurse | ForEach-Object FullName | Sort-Object)
    $SnapshotDifference = (Compare-Object $Before $After | Out-String).Trim()
    Assert-True ($preflight.Code -eq 0) "Codex-only preflight Claude olmadan geçmeli: $($preflight.Output)"
    Assert-True (-not (Test-Path -LiteralPath $PreflightVault)) "Preflight hedef oluşturmamalı"
    Assert-True (($Before -join "|") -eq ($After -join "|")) "Preflight dosya sistemini değiştirmemeli: $SnapshotDifference"

    $StoreStub = Join-Path $Root "store-python.cmd"
    [IO.File]::WriteAllText($StoreStub, "@echo off`r`necho Python was not found; run without arguments to install from the Microsoft Store.`r`nexit /b 0`r`n", [Text.UTF8Encoding]::new($false))
    $env:RESPECTED_TEST_PYTHON = $StoreStub
    $store = Invoke-Installer @(
        "-VaultPath", (Join-Path $Root "store-vault"), "-UserName", "Ada", "-UserBio", "Geliştirici",
        "-Companion", "Echo", "-OsName", "AdaOS", "-Providers", "codex", "-PreflightOnly"
    )
    Assert-True ($store.Code -ne 0) "Microsoft Store Python alias reddedilmeli"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root "store-vault"))) "Başarısız preflight hedef oluşturmamalı"
    if ($WorkingPythonOverride) {
        $env:RESPECTED_TEST_PYTHON = $WorkingPythonOverride
    }
    else {
        Remove-Item Env:RESPECTED_TEST_PYTHON
    }

    $env:RESPECTED_TEST_COMMAND_ROOT = $Commands
    $env:LOCALAPPDATA = Join-Path $Root "local-app-data"
    New-ProviderStub (Join-Path $env:LOCALAPPDATA "agy\bin") "agy"
    $localAgy = Invoke-Installer @(
        "-VaultPath", (Join-Path $Root "agy-preflight"), "-UserName", "Ada", "-UserBio", "Geliştirici",
        "-Companion", "Echo", "-OsName", "AdaOS", "-Providers", "antigravity", "-PreflightOnly"
    )
    Assert-True ($localAgy.Code -eq 0) "Antigravity kullanıcı-yerel agy CLI keşfedilmeli: $($localAgy.Output)"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root "agy-preflight"))) "Agy preflight hedef oluşturmamalı"

    $EmptyCommands = Join-Path $Root "empty-commands"
    New-Item -ItemType Directory -Path $EmptyCommands | Out-Null
    $env:RESPECTED_TEST_COMMAND_ROOT = $EmptyCommands
    $missing = Invoke-Installer @(
        "-VaultPath", (Join-Path $Root "missing-vault"), "-UserName", "Ada", "-UserBio", "Geliştirici",
        "-Companion", "Echo", "-OsName", "AdaOS", "-Providers", "cursor", "-PreflightOnly"
    )
    Assert-True ($missing.Code -ne 0) "Seçili provider CLI yoksa preflight durmalı"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root "missing-vault"))) "Eksik provider hedef oluşturmamalı"

    $env:RESPECTED_TEST_COMMAND_ROOT = $Commands
    $Vault = Join-Path $Root "Ada Brain"
    $install = Invoke-Installer @(
        "-VaultPath", $Vault, "-UserName", "Ada", "-UserBio", "Geliştirici ve tasarımcı",
        "-Companion", "Echo", "-OsName", "AdaOS", "-Providers", "codex"
    )
    Assert-True ($install.Code -eq 0) "Native temiz kurulum geçmeli: $($install.Output)"
    Assert-True ((Get-Content -Raw -LiteralPath (Join-Path $Vault ".beyin-version")).Trim() -eq "2.0.0") "Çekirdek damgası 2.0.0 olmalı"
    Assert-True ((Get-Content -Raw -LiteralPath (Join-Path $Vault ".beyin-multi-version")).Trim() -eq "1.3.0") "Multi damgası 1.3.0 olmalı"
    Assert-True ((Test-Path -LiteralPath (Join-Path $Vault "scripts\update_respected.py") -PathType Leaf)) "Güncel updater kurulmalı"
    Assert-True ((Test-Path -LiteralPath (Join-Path $Vault "scripts\respected_manifest.py") -PathType Leaf)) "Güncel manifest kurulmalı"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Vault "scripts\update_respot.py"))) "Eski updater temiz kurulumda olmamalı"
    $Managed = @(
        Join-Path $Vault ".claude\settings.json"
        Join-Path $Vault ".codex\hooks.json"
        Join-Path $Vault ".cursor\hooks.json"
        Join-Path $Vault ".agents\hooks.json"
        Join-Path $Vault "AGENTS.md"
        Join-Path $Vault "CLAUDE.md"
    )
    $Combined = ($Managed | ForEach-Object { Get-Content -Raw -LiteralPath $_ }) -join "`n"
    Assert-True (-not $Combined.Contains("{{")) "Üretilmiş dosyalarda placeholder kalmamalı"
    Assert-True (-not $Combined.Contains("wsl.exe")) "Native hook WSL içermemeli"
    Assert-True (-not $Combined.Contains(".sh")) "Native hook POSIX launcher içermemeli"
    Assert-True (-not $Combined.ToLowerInvariant().Contains("bash")) "Native hook Bash içermemeli"
    Assert-True ($Combined.Contains("py.exe")) "Native hook py.exe kullanmalı"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".claude"))) "Temiz kurulum kullanıcı profilini değiştirmemeli"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".codex"))) "Global kurulum açıkça ayrıca uygulanmalı"

    $Vault2 = Join-Path $Root "Ada Brain 2"
    $install2 = Invoke-Installer @(
        "-VaultPath", $Vault2, "-UserName", "Ada", "-UserBio", "Geliştirici ve tasarımcı",
        "-Companion", "Echo", "-OsName", "AdaOS", "-Providers", "codex"
    )
    Assert-True ($install2.Code -eq 0) "İkinci temiz kurulum geçmeli: $($install2.Output)"
    $RelativeManaged = @(
        ".claude\settings.json", ".codex\hooks.json", ".cursor\hooks.json",
        ".agents\hooks.json", "AGENTS.md", "CLAUDE.md"
    )
    $EscapedVault = $Vault.Replace('\', '\\')
    $EscapedVault2 = $Vault2.Replace('\', '\\')
    $FirstNormalized = ($RelativeManaged | ForEach-Object {
        (Get-Content -Raw -LiteralPath (Join-Path $Vault $_)).Replace($EscapedVault, "<VAULT>").Replace($Vault, "<VAULT>")
    }) -join "`n"
    $SecondNormalized = ($RelativeManaged | ForEach-Object {
        (Get-Content -Raw -LiteralPath (Join-Path $Vault2 $_)).Replace($EscapedVault2, "<VAULT>").Replace($Vault2, "<VAULT>")
    }) -join "`n"
    Assert-True ($FirstNormalized -eq $SecondNormalized) "Aynı girdiler deterministik adaptör ve kural üretmeli"

    $SentinelVault = Join-Path $Root "non-empty"
    New-Item -ItemType Directory -Path $SentinelVault | Out-Null
    [IO.File]::WriteAllText((Join-Path $SentinelVault "keep.txt"), "keep", [Text.UTF8Encoding]::new($false))
    $existing = Invoke-Installer @(
        "-VaultPath", $SentinelVault, "-UserName", "Ada", "-UserBio", "Geliştirici",
        "-Companion", "Echo", "-OsName", "AdaOS", "-Providers", "codex"
    )
    Assert-True ($existing.Code -eq 3) "Dolu hedef exit 3 dönmeli"
    Assert-True ((Get-Content -Raw -LiteralPath (Join-Path $SentinelVault "keep.txt")) -eq "keep") "Dolu hedef değişmemeli"
}
finally {
    Remove-Item Env:RESPECTED_TEST_COMMAND_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:RESPECTED_TEST_PYTHON -ErrorAction SilentlyContinue
    Remove-Item Env:RESPOT_TEST_COMMAND_ROOT -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
}

if ($Failures -ne 0) {
    Write-Error "$Failures Windows installer testi başarısız"
}
Write-Host "Windows installer tests: OK"
