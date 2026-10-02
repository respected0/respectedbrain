#!/usr/bin/env python3
"""Launch the Respected Brain Local Gateway & Web Dashboard."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[2] if Path(__file__).resolve().parent.parent.name == "runtime" else Path(__file__).resolve().parent.parent
SERVER_SCRIPT = REPO_ROOT / "runtime" / "gateway" / "server.py"


def _detect_default_vault() -> Path | None:
    try:
        from runtime_hub import resolve_vault_path
        vp = resolve_vault_path()
        if vp and vp.is_dir():
            return vp
    except Exception:
        pass
    home = Path.home()
    candidates = [
        home / "Documents" / "RespectedOS",
        home / "RespectedOS",
        Path("/mnt/c/Users") / home.name / "Documents" / "RespectedOS",
    ]
    for c in candidates:
        if c.is_dir() and (c / ".respected.json" or c / ".respectedbrain-version" or c / ".beyin-version" or c / "🔮 850-Companion").exists():
            return c
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Respected Brain Gateway & Dashboard Launcher")
    parser.add_argument("vault", nargs="?", default=None, help="Hedef vault dizini")
    parser.add_argument("--port", type=int, default=8520, help="Web portu (varsayılan: 8520)")
    parser.add_argument("--open", action="store_true", default=True, help="Tarayıcıda otomatik aç (varsayılan)")
    parser.add_argument("--no-browser", action="store_true", help="Tarayıcıyı otomatik açma")
    args = parser.parse_args()

    vault_path = Path(args.vault) if args.vault else _detect_default_vault()
    if not vault_path or not vault_path.is_dir():
        vault_path = REPO_ROOT

    # Run the gateway server from runtime
    server_file = SERVER_SCRIPT
    if not server_file.is_file():
        try:
            from runtime_hub import get_runtime_dir
            rdir = get_runtime_dir()
            for cand in [rdir / "runtime" / "gateway" / "server.py", rdir / "gateway" / "server.py"]:
                if cand.is_file():
                    server_file = cand
                    break
        except Exception:
            pass

    cmd = [sys.executable, str(server_file), "--vault", str(vault_path), "--port", str(args.port)]
    if args.open and not args.no_browser:
        cmd.append("--open")

    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
