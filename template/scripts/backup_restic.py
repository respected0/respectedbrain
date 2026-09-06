#!/usr/bin/env python3
"""Opt-in, verified Restic backup utility for Respected Brain vaults."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


def check_prerequisites() -> tuple[bool, str]:
    """Verify that restic CLI is installed on the host."""
    binary = shutil.which("restic") or shutil.which("restic.exe")
    if binary is None:
        return False, "Restic kurulu değil. Lütfen kurun (Windows: winget/scoop/choco install restic, macOS: brew install restic, Linux: apt install restic)."
    return True, binary


def check_target_safety(vault_root: Path, repo_target: str) -> None:
    """Ensure repo target is not inside the vault itself."""
    try:
        target_path = Path(repo_target).resolve()
        if target_path == vault_root or target_path.is_relative_to(vault_root):
            raise ValueError("Yedek deposu (repo target) vault içinde olamaz.")
    except (ValueError, OSError):
        pass


def run_backup(
    vault_root: Path,
    repo_target: str,
    password: str | None = None,
    verify_restore: bool = True,
    apply: bool = False,
) -> dict[str, Any]:
    """Execute restic backup and optionally verify snapshot integrity via dry restore."""
    ready, message = check_prerequisites()
    if not ready:
        return {"status": "error", "error": message}

    check_target_safety(vault_root, repo_target)

    env = os.environ.copy()
    if password:
        env["RESTIC_PASSWORD"] = password
    env["RESTIC_REPOSITORY"] = repo_target

    if not apply:
        return {
            "status": "preview",
            "vault": str(vault_root),
            "repo": repo_target,
            "verify_restore": verify_restore,
        }

    cmd = ["restic", "backup", str(vault_root), "--json"]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {"status": "failed", "error": proc.stderr or proc.stdout}

    snapshot_id = "latest"
    for line in reversed(proc.stdout.splitlines()):
        try:
            data = json.loads(line)
            if data.get("message_type") == "summary" and "snapshot_id" in data:
                snapshot_id = data["snapshot_id"]
                break
        except (json.JSONDecodeError, ValueError):
            continue

    if verify_restore:
        with tempfile.TemporaryDirectory() as verify_dir:
            restore_cmd = ["restic", "restore", snapshot_id, "--target", verify_dir]
            r_proc = subprocess.run(restore_cmd, env=env, capture_output=True, text=True, check=False)
            if r_proc.returncode != 0:
                return {"status": "verify-failed", "error": r_proc.stderr, "snapshot_id": snapshot_id}

    return {"status": "ok", "snapshot_id": snapshot_id}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, help="Vault kök dizini")
    parser.add_argument("--repo", required=True, help="Restic repository konumu")
    parser.add_argument("--apply", action="store_true", help="Yedeklemeyi gerçekten çalıştır")
    parser.add_argument("--skip-verify", action="store_true", help="Restore doğrulamasını atla")
    args = parser.parse_args(argv)

    result = run_backup(
        vault_root=args.vault.resolve(),
        repo_target=args.repo,
        verify_restore=not args.skip_verify,
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"ok", "preview"} else 1


if __name__ == "__main__":
    sys.exit(main())
