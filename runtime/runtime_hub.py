#!/usr/bin/env python3
"""Respected Brain Runtime Hub — Unified Engine & Vault path resolver."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_WINDOWS_RUNTIME = Path.home() / "AppData" / "Local" / "RespectedBrain"
DEFAULT_POSIX_RUNTIME = Path.home() / ".local" / "share" / "respectedbrain"


def get_runtime_dir(override: Path | str | None = None) -> Path:
    """Return the absolute path to the active Respected Brain runtime directory."""
    if override:
        return Path(override).resolve()
    env_dir = os.environ.get("RESPECTED_RUNTIME_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "RespectedBrain").resolve()
        return DEFAULT_WINDOWS_RUNTIME.resolve()
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return (Path(xdg_data) / "respectedbrain").resolve()
    return DEFAULT_POSIX_RUNTIME.resolve()


def get_runtime_config(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Read configuration from the runtime directory."""
    rdir = runtime_dir or get_runtime_dir()
    config_file = rdir / "config.json"
    if config_file.is_file():
        try:
            val = json.loads(config_file.read_text(encoding="utf-8"))
            if isinstance(val, dict):
                return val
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def resolve_vault_path(
    candidate: Path | str | None = None,
    runtime_dir: Path | None = None,
) -> Path | None:
    """Resolve the active vault directory with graceful priority cascades."""
    if candidate:
        cand_path = Path(candidate).resolve()
        if cand_path.is_dir():
            return cand_path

    env_vault = os.environ.get("RESPECTED_VAULT_PATH")
    if env_vault:
        env_path = Path(env_vault).resolve()
        if env_path.is_dir():
            return env_path

    # Check cwd and parent directories for .respected.json or markers
    cwd = Path.cwd().resolve()
    current = cwd
    while True:
        if (current / ".respected.json").is_file() or (current / ".respected").is_file():
            return current
        if (current / "🔮 850-Companion").is_dir() and (current / "🎯 100-Command-Center").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent

    # Check runtime config
    cfg = get_runtime_config(runtime_dir)
    configured_vault = cfg.get("vault_path")
    if configured_vault:
        vp = Path(configured_vault).resolve()
        if vp.is_dir():
            return vp

    return None
