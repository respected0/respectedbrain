#!/usr/bin/env python3
"""Provider-neutral local CLI runner for beyin flush and compile jobs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Literal


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import runtime_platform


Mode = Literal["text", "workspace"]
PROVIDERS = ("claude", "codex", "antigravity", "cursor")


@dataclass(frozen=True)
class Invocation:
    argv: list[str]
    stdin: str | None
    windows_executable: bool = False


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


def _windows_executable(executable: str) -> bool:
    return os.name == "nt" or executable.casefold().endswith(".exe")


def _command(provider: str, prompt: str, mode: Mode) -> Invocation | None:
    sandbox = "workspace-write" if mode == "workspace" else "read-only"
    if provider == "claude":
        executable = shutil.which("claude") or shutil.which("claude.exe")
        if executable is None:
            return None
        if mode == "workspace":
            return Invocation(
                [executable, "-p", "--model", "sonnet", "--output-format", "text", "--safe-mode", "--tools", "Read,Write,Edit,Glob,Grep", "--permission-mode", "acceptEdits", "--allowedTools", "Read,Write,Edit,Glob,Grep"],
                prompt,
                _windows_executable(executable),
            )
        return Invocation(
            [executable, "-p", "--model", "haiku", "--output-format", "text", "--safe-mode", "--tools", ""],
            prompt,
            _windows_executable(executable),
        )
    if provider == "codex":
        executable = shutil.which("codex") or shutil.which("codex.exe")
        if executable is None:
            return None
        return Invocation(
            [executable, "exec", "--ephemeral", "--sandbox", sandbox, "-"],
            prompt,
            _windows_executable(executable),
        )
    if provider in {"antigravity", "agy"}:
        executable = shutil.which("agy") or shutil.which("agy.exe") or _windows_vault_binary("agy")
        if executable is None:
            return None
        argv = [
            executable,
            "--disable-slash-commands",
        ]
        if mode == "workspace":
            argv.extend([
                "--add-dir",
                ".",
                "--mode",
                "accept-edits",
            ])
        else:
            argv.append("--sandbox")
        argv.extend([
            "--dangerously-skip-permissions",
            "--print-timeout",
            "20m",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
        ])
        stdin_payload = json.dumps({"event": "user", "message": {"content": prompt}}) + "\n"
        return Invocation(argv, stdin_payload, _windows_executable(executable))
    if provider == "cursor":
        executable = shutil.which("cursor-agent") or shutil.which("cursor-agent.exe")
        if executable is None:
            return None
        argv = [executable, "-p", "--output-format", "text"]
        if mode == "workspace":
            argv.append("--force")
        argv.append(prompt)
        return Invocation(argv, None, _windows_executable(executable))
    return None


def _merge_wslenv(
    value: str,
    path_names: tuple[str, ...],
    scalar_names: tuple[str, ...] = (),
) -> str:
    targeted = {name.casefold() for name in path_names + scalar_names}
    kept = []
    for entry in value.split(":"):
        if not entry:
            continue
        base = entry.split("/", 1)[0].casefold()
        if base not in targeted:
            kept.append(entry)
    kept.extend(f"{name}/p" for name in path_names)
    kept.extend(scalar_names)
    return ":".join(kept)


def _windows_user_environment(environment: dict[str, str], cwd: Path) -> None:
    if os.name == "nt" or not environment.get("WSL_INTEROP"):
        return
    user_root = runtime_platform.windows_user_root(cwd)
    if user_root is None:
        user_root = runtime_platform.windows_user_root(Path(__file__).resolve())
    if user_root is None:
        return
    environment["USERPROFILE"] = str(user_root)
    environment["LOCALAPPDATA"] = str(user_root / "AppData" / "Local")
    environment["APPDATA"] = str(user_root / "AppData" / "Roaming")
    environment["BEYIN_INVOKED_BY"] = environment.get("BEYIN_INVOKED_BY", "beyin-scripts")
    environment["BEYIN_RECURSION_DEPTH"] = environment.get("BEYIN_RECURSION_DEPTH", "1")
    path_names = ("USERPROFILE", "LOCALAPPDATA", "APPDATA")
    scalar_names = ("BEYIN_INVOKED_BY", "BEYIN_RECURSION_DEPTH")
    environment["WSLENV"] = _merge_wslenv(
        environment.get("WSLENV", ""),
        path_names,
        scalar_names,
    )


def _retryable_failure(stdout: str, stderr: str) -> bool:
    message = f"{stdout}\n{stderr}".casefold()
    signals = (
        "rate limit", "rate_limit", "usage limit", "quota", "too many requests", "429",
        "overloaded", "capacity", "temporarily unavailable", "service unavailable",
        "internal server error", "connection reset", "timed out", "timeout",
        "bad gateway", "gateway timeout", "502", "503", "504",
    )
    return any(signal in message for signal in signals)


def _extract_response(stdout: str, provider: str) -> tuple[str, str | None]:
    """Extract response text and potential provider-level error from stdout."""
    if provider in {"antigravity", "agy"}:
        for line in reversed(stdout.splitlines()):
            try:
                data = json.loads(line)
                if data.get("event") == "result":
                    result_obj = data.get("result", {})
                    if result_obj.get("status") == "ERROR":
                        return "", result_obj.get("error", "antigravity-stream-error")
                    return result_obj.get("response", "").strip(), None
            except (json.JSONDecodeError, AttributeError):
                continue
    return stdout.strip(), None


def run_model(
    prompt: str,
    cwd: Path,
    mode: Mode,
    timeout: int,
    preferred: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (stdout, error, provider); never invoke through a shell."""
    try:
        depth = int(os.environ.get("BEYIN_RECURSION_DEPTH", "0"))
    except ValueError:
        depth = 0
    if depth >= 2:
        return None, "recursion-depth-exceeded", None
    custom = os.environ.get("BEYIN_LLM_COMMAND")
    candidates = ["custom"] if custom else _available(preferred)
    environment = os.environ.copy()
    environment["BEYIN_INVOKED_BY"] = "beyin-scripts"
    environment["BEYIN_RECURSION_DEPTH"] = str(depth + 1)

    last_error: tuple[str, str] | None = None
    for provider in candidates:
        if provider == "custom":
            try:
                argv = shlex.split(custom or "")
            except ValueError:
                return None, "custom-command-invalid", provider
            if not argv:
                return None, "custom-command-empty", provider
            invocation = Invocation(
                argv,
                prompt,
                _windows_executable(argv[0]),
            )
        else:
            invocation = _command(provider, prompt, mode)
            if invocation is None:
                continue
        process_environment = environment.copy()
        run_cwd = cwd
        if invocation.windows_executable:
            _windows_user_environment(process_environment, cwd)
            if runtime_platform.windows_user_root(cwd) is None:
                fallback_parent = runtime_platform.external_temp_parent(Path(__file__).resolve())
                if fallback_parent is not None and fallback_parent.is_dir():
                    run_cwd = fallback_parent
        try:
            result = subprocess.run(
                invocation.argv,
                input=invocation.stdin,
                text=True,
                capture_output=True,
                cwd=run_cwd,
                env=process_environment,
                timeout=timeout,
                check=False,
                **runtime_platform.hidden_process_options(),
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
        output_text, stream_error = _extract_response(result.stdout, provider)
        if stream_error is not None:
            return None, stream_error, provider
        return output_text, None, provider
    if last_error is not None:
        error, provider = last_error
        return None, error, provider
    return None, "model-cli-missing", None
