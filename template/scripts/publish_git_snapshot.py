#!/usr/bin/env python3
"""Opt-in private Git snapshot publisher for Respected Brain vaults."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


FORBIDDEN_NAME_PATTERNS = (
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"^.*id_rsa.*$", re.IGNORECASE),
    re.compile(r"^.*\.(pem|key|pfx|pkcs12)$", re.IGNORECASE),
    re.compile(r"^.*settings\.local\.json$", re.IGNORECASE),
    re.compile(r"^.*credentials.*$", re.IGNORECASE),
)


def check_secret_guard(vault_root: Path) -> tuple[bool, list[str]]:
    """Scan vault candidate paths for potential secrets or forbidden files."""
    forbidden = []
    for current, _dirs, files in os.walk(vault_root, topdown=True, followlinks=False):
        if ".git" in Path(current).parts:
            continue
        for file_name in files:
            for pattern in FORBIDDEN_NAME_PATTERNS:
                if pattern.match(file_name):
                    rel = Path(current, file_name).relative_to(vault_root).as_posix()
                    forbidden.append(rel)
                    break
    return len(forbidden) == 0, forbidden


def _branch_divergence_status(vault_root: Path, remote: str, branch: str) -> str:
    """Determine if local branch has diverged from remote without pulling."""
    try:
        # Fetch remote updates cleanly
        subprocess.run(
            ["git", "fetch", remote, branch],
            cwd=vault_root,
            capture_output=True,
            check=False,
            timeout=30,
        )
        head_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        remote_proc = subprocess.run(
            ["git", "rev-parse", f"{remote}/{branch}"],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if head_proc.returncode != 0 or remote_proc.returncode != 0:
            return "unknown"
        head_hash = head_proc.stdout.strip()
        remote_hash = remote_proc.stdout.strip()
        if head_hash == remote_hash:
            return "clean"

        base_proc = subprocess.run(
            ["git", "merge-base", head_hash, remote_hash],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        base_hash = base_proc.stdout.strip()
        if base_hash == head_hash:
            return "behind"
        if base_hash == remote_hash:
            return "ahead"
        return "diverged"
    except (OSError, subprocess.SubprocessError):
        return "error"


def publish_if_due(
    vault_root: Path,
    remote: str = "origin",
    branch: str = "main",
    min_interval_seconds: int = 3600,
    apply: bool = False,
) -> dict[str, Any]:
    """Safely commit and push a snapshot if interval has elapsed and no divergence."""
    safe, forbidden = check_secret_guard(vault_root)
    if not safe:
        return {
            "status": "aborted:secret_found",
            "forbidden": forbidden,
        }

    div_status = _branch_divergence_status(vault_root, remote, branch)
    if div_status == "diverged":
        return {"status": "halted:diverged", "detail": "Uzak dal ile yerel commitler çatışıyor; fail-closed duruldu."}

    receipt_file = vault_root / ".beyin" / ".git-snapshot-receipt.json"
    now_epoch = time.time()
    if receipt_file.exists():
        try:
            data = json.loads(receipt_file.read_text(encoding="utf-8"))
            last_ts = float(data.get("ts", 0))
            if now_epoch - last_ts < min_interval_seconds:
                return {"status": "skipped:not_due", "seconds_remaining": int(min_interval_seconds - (now_epoch - last_ts))}
        except (OSError, ValueError):
            pass

    if not apply:
        return {
            "status": "preview",
            "vault": str(vault_root),
            "remote": remote,
            "branch": branch,
            "divergence": div_status,
        }

    # Execute safe commit and push
    try:
        subprocess.run(["git", "add", "."], cwd=vault_root, check=True, capture_output=True)
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"chore(snapshot): {stamp}"],
            cwd=vault_root,
            check=False,
            capture_output=True,
        )
        push_proc = subprocess.run(
            ["git", "push", remote, branch],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if push_proc.returncode != 0:
            return {"status": "push-failed", "error": push_proc.stderr}

        # Write atomic receipt
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        receipt_file.write_text(
            json.dumps({"ts": now_epoch, "stamp": stamp, "remote": remote, "branch": branch}, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"status": "ok", "stamp": stamp}
    except subprocess.SubprocessError as exc:
        return {"status": "error", "detail": str(exc)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, help="Vault kök dizini")
    parser.add_argument("--remote", default="origin", help="Uzak depo adı")
    parser.add_argument("--branch", default="main", help="Hedef dal")
    parser.add_argument("--apply", action="store_true", help="Snapshot'ı sahiden push et")
    args = parser.parse_args(argv)

    result = publish_if_due(
        vault_root=args.vault.resolve(),
        remote=args.remote,
        branch=args.branch,
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"ok", "preview", "skipped:not_due"} else 1


if __name__ == "__main__":
    sys.exit(main())
