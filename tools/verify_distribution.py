"""Run native version, resource, isolated-vault, hook and MCP smoke checks."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from respectedbrain.installation.payload import validate_package


def _annotation(stage: str, code: str) -> None:
    # Only fixed labels are public. Never place exception text, paths, UUIDs,
    # subprocess output or environment values in an Actions annotation.
    stages = {"manifest", "version", "register", "list", "maps", "search", "hook", "mcp"}
    codes = {"manifest-invalid", "platform-mismatch", "launch-os-error", "launch-timeout",
             "unsafe-path", "frozen-library", "child-terminated", "child-failed"}
    if stage not in stages or code not in codes:
        raise ValueError("Unknown verification diagnostic label")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error title=Native distribution verification::stage={stage}; code={code}", flush=True)


def verify(distribution: Path, *, platform: str) -> int:
    distribution = distribution.resolve()
    try:
        document = validate_package(distribution)
    except Exception:
        _annotation("manifest", "manifest-invalid")
        raise
    if document["platform"] != platform:
        _annotation("manifest", "platform-mismatch")
        raise ValueError("Distribution platform mismatch")
    with tempfile.TemporaryDirectory(prefix="Respected Türkçe 🧠 ") as temporary:
        root = Path(temporary)
        env = {**os.environ, "PATH": str(Path(os.environ["SystemRoot"]) / "System32") if os.name == "nt" else "/usr/bin:/bin", "RESPECTED_APP_DIR": str(distribution), "RESPECTED_DATA_DIR": str(root / "data"), "PYTHONPATH": ""}
        def run(*args, stdin=None):
            stage = ("register" if args[1] == "register" else "list") if args[0] == "vault" else {
                "--version": "version", "maps": "maps", "search": "search", "hook": "hook", "mcp": "mcp"}[args[0]]
            try:
                result = subprocess.run([str(distribution / document["launcher"]), *map(str, args)], cwd=root, env=env, input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=45)
            except subprocess.TimeoutExpired:
                _annotation(stage, "launch-timeout")
                raise
            except OSError:
                _annotation(stage, "launch-os-error")
                raise
            if result.returncode:
                code = "unsafe-path" if "Link or reparse target:" in result.stderr else "frozen-library" if "Failed to load Python shared library" in result.stderr else "child-terminated" if result.returncode < 0 else "child-failed"
                _annotation(stage, code)
                raise RuntimeError(result.stderr + result.stdout)
            return result.stdout
        if run("--version").strip() != document["version"]:
            raise RuntimeError("Frozen version differs from manifest")
        vault = root / "Kasa 🧠"
        vault.mkdir()
        (vault / "keep.md").write_text("# Notum\n", encoding="utf-8")
        identity = run("vault", "register", vault).strip()
        listing = json.loads(run("vault", "list"))
        if identity not in listing:
            raise RuntimeError("Frozen registry omitted its vault")
        run("maps", "--vault-id", identity)
        run("search", "--vault-id", identity, "--json", "Notum")
        run("hook", "--vault-id", identity, "--provider", "claude", "--event", "precompact", stdin="{}")
        reply = run("mcp", "--vault-id", identity, stdin='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
        if json.loads(reply)["id"] != 1:
            raise RuntimeError("Frozen MCP protocol failed")
        if (vault / "keep.md").read_text(encoding="utf-8") != "# Notum\n":
            raise RuntimeError("Frozen smoke altered a user note")
    print("Native frozen version/registry/maps/search/hook/MCP: OK")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--distribution", type=Path, required=True)
    parser.add_argument("--platform", choices=("windows", "macos", "linux"), required=True)
    args = parser.parse_args()
    raise SystemExit(verify(args.distribution, platform=args.platform))
