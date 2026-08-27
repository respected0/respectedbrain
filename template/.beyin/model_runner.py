#!/usr/bin/env python3
"""Provider-neutral local CLI runner for beyin flush and compile jobs."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Literal


Mode = Literal["text", "workspace"]


def _windows_vault_binary(name: str) -> str | None:
    """Find a Windows user-local CLI from a vault stored under /mnt/<drive>/Users/<user>."""
    module = Path(__file__).resolve()
    parts = module.parts
    if len(parts) < 5 or parts[1] != "mnt" or parts[3].casefold() != "users":
        return None
    user_root = Path(*parts[:5])
    candidates = {
        "agy": user_root / "AppData" / "Local" / "agy" / "bin" / "agy.exe",
    }
    candidate = candidates.get(name)
    return str(candidate) if candidate is not None and candidate.is_file() else None


def _available(preferred: str | None) -> list[str]:
    names = []
    if preferred:
        names.append(preferred)
    configured = os.environ.get("BEYIN_MODEL_PROVIDER", "auto").strip().lower()
    if configured and configured != "auto":
        names.append(configured)
    names.extend(("claude", "codex", "antigravity"))
    return list(dict.fromkeys(names))


def _command(provider: str, prompt: str, mode: Mode) -> tuple[list[str], str | None] | None:
    sandbox = "workspace-write" if mode == "workspace" else "read-only"
    if provider == "claude":
        executable = shutil.which("claude") or shutil.which("claude.exe")
        if executable is None:
            return None
        if mode == "workspace":
            return ([executable, "-p", "--model", "sonnet", "--output-format", "text", "--safe-mode", "--tools", "Read,Write,Edit,Glob,Grep", "--permission-mode", "acceptEdits", "--allowedTools", "Read,Write,Edit,Glob,Grep"], prompt)
        return ([executable, "-p", "--model", "haiku", "--output-format", "text", "--safe-mode", "--tools", ""], prompt)
    if provider == "codex":
        executable = shutil.which("codex") or shutil.which("codex.exe")
        if executable is None:
            return None
        return ([executable, "exec", "--ephemeral", "--sandbox", sandbox, prompt], None)
    if provider in {"antigravity", "agy"}:
        executable = shutil.which("agy") or shutil.which("agy.exe") or _windows_vault_binary("agy")
        if executable is None:
            return None
        return ([executable, "-p", prompt, "--output-format", "text", "--sandbox"], None)
    return None


def run_model(
    prompt: str,
    cwd: Path,
    mode: Mode,
    timeout: int,
    preferred: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (stdout, error, provider); never invoke through a shell."""
    custom = os.environ.get("BEYIN_LLM_COMMAND")
    candidates = ["custom"] if custom else _available(preferred)
    environment = os.environ.copy()
    environment["BEYIN_INVOKED_BY"] = "beyin-scripts"

    for provider in candidates:
        if provider == "cursor":
            # Cursor has hooks but no stable local headless runner contract. Fall through.
            continue
        if provider == "custom":
            try:
                argv = shlex.split(custom or "")
            except ValueError:
                return None, "custom-command-invalid", provider
            if not argv:
                return None, "custom-command-empty", provider
            stdin = prompt
        else:
            command = _command(provider, prompt, mode)
            if command is None:
                continue
            argv, stdin = command
        try:
            result = subprocess.run(
                argv,
                input=stdin,
                text=True,
                capture_output=True,
                cwd=cwd,
                env=environment,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None, f"{provider}-timeout", provider
        except OSError:
            return None, f"{provider}-exec-error", provider
        if result.returncode != 0:
            return None, f"{provider}-exit-{result.returncode}", provider
        return result.stdout.strip(), None, provider
    return None, "model-cli-missing", None
