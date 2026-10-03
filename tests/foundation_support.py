"""Filesystem probes shared by foundation tests; no product behavior here."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[name] = "link:" + os.readlink(path)
        elif path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            result[name] = "directory"
    return result


def note_hashes(vault: Path) -> dict[str, str]:
    result = {}
    for name in ("daily", "knowledge", "🔮 850-Companion", "🏰 300-Projects", "📋 Templates", ".obsidian"):
        result.update({name + "/" + key: value for key, value in snapshot(vault / name).items()})
    return result


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run_cli(argv: list[str], *, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "respectedbrain", *argv], cwd=cwd, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=30)


def make_context(root: Path, vault: Path | None = None):
    """A pure, isolated context with a registered test identity."""
    from respectedbrain.core.context import AppContext
    from respectedbrain.core.paths import AppPaths
    from respectedbrain.core.resources import ResourceCatalog
    from respectedbrain.core.config import ConfigStore
    from respectedbrain.vault.registry import VaultRegistry
    vault = vault or root / "Türkçe 🧠 Vault"
    vault.mkdir(parents=True, exist_ok=True)
    store = ConfigStore(root / "data")
    identity = VaultRegistry(store).register(vault)
    return AppContext(AppPaths(root / "app", root / "data", vault, identity), store.read(), ResourceCatalog())
