param([string]$PythonExecutable = $env:RESPECTED_TEST_PYTHON)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $Repo ".venv/Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
    }
}
Push-Location -LiteralPath $Repo
try {
    if (-not (Test-Path -LiteralPath (Join-Path $Repo "dist/RespectedBrain/distribution.json"))) {
        throw "Required native payload missing: build with tools/build_installer.py --platform windows first"
    }
    & $PythonExecutable -m unittest -v tests.foundation_native_install_test
    if ($LASTEXITCODE -ne 0) { throw "Native acceptance failed: $LASTEXITCODE" }
}
finally { Pop-Location }
