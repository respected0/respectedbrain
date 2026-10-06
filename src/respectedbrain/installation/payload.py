"""Validate a staged distribution before activating its launcher."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path, PurePosixPath
import subprocess

from respectedbrain.core.errors import OwnershipConflict
from .ownership import safe_path, digest


def validate_package(package: Path) -> dict:
    safe_path(package)
    document = json.loads(safe_path(package / "distribution.json").read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 3 or not isinstance(document.get("version"), str) or not document["version"]:
        raise OwnershipConflict("Unsupported distribution manifest")
    files = document.get("files")
    if not isinstance(files, dict) or not files or not isinstance(document.get("launcher"), str) or document["launcher"] not in files:
        raise OwnershipConflict("Missing launcher or application manifest")
    if not any(name.endswith("respectedbrain/resources/defaults.json") for name in files):
        raise OwnershipConflict("Distribution resources are missing")
    folded_names = set()
    for name, expected in files.items():
        relative = PurePosixPath(name)
        if not name or name != relative.as_posix() or relative.is_absolute() or any(part in (".", "..") or part.endswith((".", " ")) for part in relative.parts) or "\\" in name or ":" in name:
            raise OwnershipConflict("Unsafe distribution member")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise OwnershipConflict("Invalid distribution hash")
        if os.name == "nt" and name.casefold() in folded_names:
            raise OwnershipConflict("Duplicate distribution member")
        folded_names.add(name.casefold())
        member = safe_path(package / name)
        if not member.is_file() or digest(member) != expected:
            raise OwnershipConflict(f"Distribution hash mismatch: {name}")
    return document


def validate_installed_health(app_root: Path, document: dict, data_root: Path) -> None:
    launcher = safe_path(app_root / document["launcher"])
    try:
        result = subprocess.run([str(launcher), "--version"], cwd=app_root.parent,
                                env={**os.environ, "RESPECTED_APP_DIR": str(app_root), "RESPECTED_DATA_DIR": str(data_root), "PYTHONUTF8": "1"},
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise OwnershipConflict(f"Installed launcher health check failed: {error}") from error
    if result.returncode != 0 or result.stdout.strip() != document["version"]:
        raise OwnershipConflict("Installed launcher failed its version health check")
