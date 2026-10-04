param([string]$PythonExecutable = $env:RESPECTED_TEST_PYTHON)
$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$Repo = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $Repo ".venv/Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
    }
}
Push-Location -LiteralPath $Repo
try {
    # These tests register unique temporary native tasks/shortcuts/registry values;
    # Python finally clauses remove every test-owned record even on a failed assertion.
    & $PythonExecutable -m unittest -v tests.foundation_integrations_test.FoundationIntegrationsTest.test_native_task_and_shortcut_roundtrip_canonical_ownership tests.foundation_integrations_test.FoundationIntegrationsTest.test_native_registry_preserves_unknown_typed_values_and_children tests.briefing_schedule_test
    if ($LASTEXITCODE -ne 0) { throw "Native schedule integration regressions failed: $LASTEXITCODE" }
}
finally { Pop-Location }
