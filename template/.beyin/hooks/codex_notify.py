#!/usr/bin/env python3
"""Turn-ended notification hook for OpenAI Codex Desktop and CLI.

Codex Desktop does not emit clean OS-level process exit hooks or reliable
SessionEnd events. However, Codex's native `notify` configuration in
~/.codex/config.toml executes on every completed turn (`agent-turn-complete`):
  notify = ["py.exe", "-3", "<vault>/.beyin/hooks/codex_notify.py"]

This script:
1. Forwards turn completion to any chained / original handler (e.g. computer-use)
2. Parses the turn metadata (thread-id / session-id, cwd)
3. Dispatches a detached background flush to Respected Brain runtime so the daily log
   is updated automatically on every turn without requiring manual wrap-up commands.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def _parse_payload(argv: list[str]) -> dict:
    for arg in argv:
        if not arg:
            continue
        trimmed = arg.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                val = json.loads(trimmed)
                if isinstance(val, dict):
                    return val
            except (json.JSONDecodeError, ValueError):
                continue
    if argv:
        joined = " ".join(argv).strip()
        if joined.startswith("{") and joined.endswith("}"):
            try:
                val = json.loads(joined)
                if isinstance(val, dict):
                    return val
            except (json.JSONDecodeError, ValueError):
                pass
    return {}


def _forward_chained(argv: list[str]) -> None:
    chained_env = os.environ.get("CODEX_NOTIFY_CHAIN")
    candidates = []
    if chained_env:
        candidates.append(chained_env)

    appdata = os.environ.get("LOCALAPPDATA") or ""
    if appdata:
        default_cua = (
            Path(appdata)
            / "OpenAI"
            / "Codex"
            / "runtimes"
            / "cua_node"
            / "a708e72b10c27b59"
            / "bin"
            / "node_modules"
            / "@oai"
            / "sky"
            / "bin"
            / "windows"
            / "codex-computer-use.exe"
        )
        if default_cua.is_file():
            candidates.append(str(default_cua))

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
    for target in candidates:
        if os.path.isfile(target):
            try:
                subprocess.Popen(
                    [target, "turn-ended", *argv],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=flags,
                    close_fds=True,
                )
                break
            except Exception:
                pass


def main() -> int:
    if os.environ.get("BEYIN_INVOKED_BY"):
        return 0
    try:
        depth = int(os.environ.get("BEYIN_RECURSION_DEPTH", "0"))
        if depth >= 1:
            return 0
    except ValueError:
        return 0

    args = sys.argv[1:]
    _forward_chained(args)

    payload = _parse_payload(args)
    if payload.get("client") == "codex_exec":
        return 0

    thread_id = (
        payload.get("thread-id")
        or payload.get("thread_id")
        or payload.get("session_id")
    )
    if not thread_id:
        return 0

    hook_dir = Path(__file__).resolve().parent
    vault_root = hook_dir.parents[1]
    flush_script = vault_root / ".beyin" / "engine" / "flush.py"
    if not flush_script.is_file():
        return 0

    if str(hook_dir) not in sys.path:
        sys.path.insert(0, str(hook_dir))
    try:
        import bridge
        transcript_path = bridge.resolve_codex_transcript(str(thread_id))
    except Exception:
        transcript_path = ""

    if not transcript_path:
        return 0

    state_dir = vault_root / ".beyin" / "engine" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    hook_input_file = state_dir / f"hookin-{os.getpid()}-{uuid.uuid4().hex}.json"
    hook_data = {
        "session_id": str(thread_id),
        "transcript_path": str(transcript_path),
        "cwd": str(payload.get("cwd") or vault_root),
    }
    hook_input_file.write_text(json.dumps(hook_data, ensure_ascii=False) + "\n", encoding="utf-8")

    cmd = [
        sys.executable,
        str(flush_script),
        "--hook-input",
        str(hook_input_file),
    ]

    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["BEYIN_PROVIDER"] = "codex"

    try:
        subprocess.Popen(
            cmd,
            cwd=vault_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
            env=env,
        )
    except Exception:
        hook_input_file.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
