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
        if not arg or not (arg.startswith("{") and arg.endswith("}")):
            continue
        try:
            val = json.loads(arg)
            if isinstance(val, dict):
                return val
        except (json.JSONDecodeError, ValueError):
            continue
    try:
        if not sys.stdin.isatty():
            content = sys.stdin.read().strip()
            if content.startswith("{") and content.endswith("}"):
                val = json.loads(content)
                if isinstance(val, dict):
                    return val
    except Exception:
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

    for target in candidates:
        if os.path.isfile(target):
            try:
                subprocess.Popen(
                    [target, "turn-ended", *argv],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
                break
            except Exception:
                pass


def main() -> int:
    args = sys.argv[1:]
    _forward_chained(args)

    payload = _parse_payload(args)
    thread_id = (
        payload.get("thread-id")
        or payload.get("thread_id")
        or payload.get("session_id")
    )
    if not thread_id:
        return 0

    cwd = payload.get("cwd") or ""
    hook_dir = Path(__file__).resolve().parent
    bridge = hook_dir / "bridge.py"
    if not bridge.is_file():
        return 0

    hook_input = json.dumps({
        "session_id": str(thread_id),
        "cwd": str(cwd),
        "hook_event_name": "Stop",
    })

    cmd = [sys.executable, str(bridge), "--provider", "codex", "--event", "end"]
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            text=True,
            encoding="utf-8",
        )
        proc.communicate(input=hook_input, timeout=3)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
