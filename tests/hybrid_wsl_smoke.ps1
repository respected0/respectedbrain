param(
    [Parameter(Mandatory = $true)][string]$LinuxPackage,
    [string]$PythonExecutable = $env:RESPECTED_TEST_PYTHON
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $Repo ".venv/Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
    }
}
$Package = (Resolve-Path -LiteralPath $LinuxPackage -ErrorAction Stop).Path
Push-Location -LiteralPath $Repo
try {
    # Native Linux payload and actual WSL are required; fixture registries are private.
    $Program = @'
from pathlib import Path
import json, subprocess, sys, tempfile, shlex
from respectedbrain.installation.payload import validate_package
from respectedbrain.core.paths import Roots
from respectedbrain.core.config import ConfigStore
from respectedbrain.vault.registry import VaultRegistry, build_context
from respectedbrain.integrations.backend import IntegrationProfile
from respectedbrain.integrations.rendering import validate_profile, bridge_argv, wsl_path
package = Path(sys.argv[1]).resolve()
document = validate_package(package)
if document["platform"] != "linux":
    raise ValueError("Hybrid acceptance requires a real Linux distribution")
with tempfile.TemporaryDirectory(prefix="respected-hybrid-") as temporary:
    root = Path(temporary).resolve()
    vault, home, windows_data, linux_data = [root / name for name in ("Vault", "home", "windows-data", "linux-data")]
    vault.mkdir(); home.mkdir()
    store = ConfigStore(windows_data)
    identity = VaultRegistry(store).register(vault)
    ctx = build_context(Roots(root / "windows-app", windows_data, vault), store, vault=vault, vault_id=None, env={})
    shim = root / "linux-fixture-launcher"
    source = "#!/bin/sh\nexport RESPECTED_APP_DIR=" + shlex.quote(wsl_path(package)) + "\nexport RESPECTED_DATA_DIR=" + shlex.quote(wsl_path(linux_data)) + "\nexec " + shlex.quote(wsl_path(package / document["launcher"])) + " \"$@\"\n"
    shim.write_text(source, encoding="utf-8", newline="\n")
    linux_launcher = wsl_path(shim)
    def run(argv, stdin=None):
        result = subprocess.run(argv, input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout
    run(["wsl.exe", "--", "chmod", "+x", linux_launcher])
    registered = run(["wsl.exe", "--", linux_launcher, "vault", "register", wsl_path(vault)]).strip()
    if registered != identity:
        raise AssertionError("Linux and Windows registry UUID differ")
    profile = IntegrationProfile("windows-wsl", (linux_launcher,), home)
    validate_profile(ctx, profile)
    payload = json.dumps({"session_id":"hybrid-native", "opaque":{"path":"C:\\unmodified\\payload"}})
    run(bridge_argv(ctx, profile, "cursor", "prompt"), payload)
    state = linux_data / "vaults" / identity / "state"
    counters = list(state.glob("prompt_count.*"))
    if not counters or not any(path.read_text().strip() == "1" for path in counters):
        raise AssertionError("Real WSL hook omitted selected UUID state")
    reply = json.loads(run(["wsl.exe", "--", linux_launcher, "mcp", "--vault-id", identity], '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'))
    if reply["id"] != 1:
        raise AssertionError("Real WSL MCP protocol failed")
print("Hybrid real Linux launcher/UUID registration/hook/MCP: VERIFIED")
'@
    & $PythonExecutable -c $Program $Package
    if ($LASTEXITCODE -ne 0) { throw "Hybrid WSL native acceptance failed: $LASTEXITCODE" }
}
finally { Pop-Location }
