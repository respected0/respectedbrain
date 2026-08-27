#!/usr/bin/env python3
"""Provider-neutral local CLI runner for beyin flush and compile jobs."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Literal


Mode = Literal["text", "workspace"]
PROVIDERS = ("claude", "codex", "antigravity", "cursor")


def _configured_provider() -> str:
    environment = os.environ.get("BEYIN_MODEL_PROVIDER", "").strip().lower()
    if environment:
        return environment
    path = Path(__file__).with_name("config.json")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return "auto"
    value = document.get("summary_provider", "auto") if isinstance(document, dict) else "auto"
    return value if value in ("auto", *PROVIDERS) else "auto"


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
    configured = _configured_provider()
    if configured and configured != "auto":
        names.append(configured)
    if preferred:
        names.append(preferred)
    names.extend(PROVIDERS)
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
    if provider == "cursor":
        executable = shutil.which("cursor-agent") or shutil.which("cursor-agent.exe")
        if executable is None:
            return None
        argv = [executable, "-p", "--output-format", "text"]
        if mode == "workspace":
            argv.append("--force")
        argv.append(prompt)
        return (argv, None)
    return None


def _retryable_failure(stdout: str, stderr: str) -> bool:
    message = f"{stdout}\n{stderr}".casefold()
    signals = (
        "rate limit", "rate_limit", "usage limit", "quota", "too many requests", "429",
        "overloaded", "capacity", "temporarily unavailable", "service unavailable",
        "internal server error", "connection reset", "timed out", "timeout",
        "bad gateway", "gateway timeout", "502", "503", "504",
    )
    return any(signal in message for signal in signals)


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

    last_error: tuple[str, str] | None = None
    for provider in candidates:
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
            last_error = (f"{provider}-timeout", provider)
            continue
        except OSError:
            last_error = (f"{provider}-exec-error", provider)
            continue
        if result.returncode != 0:
            error = f"{provider}-exit-{result.returncode}"
            if _retryable_failure(result.stdout, result.stderr):
                last_error = (error, provider)
                continue
            return None, error, provider
        return result.stdout.strip(), None, provider
    if last_error is not None:
        error, provider = last_error
        return None, error, provider
    return None, "model-cli-missing", None
