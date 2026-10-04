# Compatibility launcher. Native setup owns validation and transactions.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$ErrorActionPreference = "Stop"
$Launcher = Get-Command respectedbrain.exe -CommandType Application -ErrorAction Stop
& $Launcher.Source setup @Arguments
exit $LASTEXITCODE
