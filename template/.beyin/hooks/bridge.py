#!/usr/bin/env python3
"""Normalize provider-native hook payloads into the shared Respot Brain runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = Path(__file__).resolve().parent
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))

import lifecycle as LIFECYCLE


EVENTS = ("start", "prompt", "end", "precompact")


def load_input() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def first_string(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def wsl_path(value: str) -> str:
    """Translate a Windows hook path when this bridge is running inside WSL."""
    if not value or not (len(value) >= 3 and value[1] == ":" and value[2] in "\\/"):
        return value
    try:
        result = subprocess.run(
            ["wslpath", "-u", value],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return value
    translated = result.stdout.strip()
    return translated if result.returncode == 0 and translated else value


def normalize(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace_paths = payload.get("workspacePaths") or payload.get("workspace_roots") or []
    cwd = first_string(payload, "cwd")
    if not cwd and isinstance(workspace_paths, list) and workspace_paths:
        cwd = str(workspace_paths[0])
    session_id = first_string(payload, "session_id", "conversation_id", "conversationId")
    if not session_id:
        session_id = f"{provider}-unknown"
    return {
        **payload,
        "session_id": session_id,
        "transcript_path": wsl_path(first_string(payload, "transcript_path", "transcriptPath")),
        "cwd": wsl_path(cwd) or str(ROOT),
        "model": first_string(payload, "model", "modelName"),
        "beyin_provider": provider,
    }


def extract_context(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        specific = value.get("hookSpecificOutput")
        if isinstance(specific, dict):
            context = specific.get("additionalContext")
            if isinstance(context, str):
                return context
    return ""


def output(provider: str, event: str, context: str) -> None:
    if provider == "cursor":
        if event == "start" and context:
            print(json.dumps({"additional_context": context}, ensure_ascii=False))
        elif event == "precompact" and context:
            print(json.dumps({"user_message": context}, ensure_ascii=False))
        else:
            print("{}")
    elif provider == "antigravity":
        if event == "start":
            steps = [{"ephemeralMessage": context}] if context else []
            print(json.dumps({"injectSteps": steps}, ensure_ascii=False))
        else:
            print(json.dumps({"decision": "stop"}, ensure_ascii=False))
    elif context:
        event_name = {"start": "SessionStart", "prompt": "UserPromptSubmit", "end": "SessionEnd", "precompact": "PreCompact"}[event]
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": context}}, ensure_ascii=False))


def dispatch(provider: str, event: str, payload: dict[str, Any]) -> str:
    if os.environ.get("BEYIN_INVOKED_BY"):
        return ""
    normalized = normalize(provider, payload)
    return LIFECYCLE.handle(event, normalized, ROOT, provider)


def inside_vault(active: str) -> bool:
    """Compare native Windows and POSIX workspace paths without treating C:\\... as relative in WSL."""
    normalized = active.replace("\\", "/").rstrip("/")
    if re.match(r"^[A-Za-z]:/", normalized):
        parts = ROOT.parts
        if len(parts) < 4 or parts[1] != "mnt" or len(parts[2]) != 1:
            return False
        root_native = f"{parts[2]}:/" + "/".join(parts[3:])
        candidate = normalized.casefold()
        root_folded = root_native.rstrip("/").casefold()
        return candidate == root_folded or candidate.startswith(root_folded + "/")
    path = Path(active)
    if not path.is_absolute():
        return False
    try:
        path.resolve().relative_to(ROOT)
    except (OSError, ValueError):
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("claude", "codex", "cursor", "antigravity"), required=True)
    parser.add_argument("--event", choices=EVENTS, required=True)
    parser.add_argument("--global-hook", action="store_true", help="vault dışındaki repolar için kullanıcı düzeyi hook")
    args = parser.parse_args()
    payload = normalize(args.provider, load_input())

    if args.global_hook:
        active = payload.get("cwd")
        if isinstance(active, str) and inside_vault(active):
            output(args.provider, args.event, "")
            return 0

    # Antigravity invokes PreInvocation before every model call. Initialize only once.
    if args.provider == "antigravity" and args.event == "start" and payload.get("invocationNum") not in (None, 0):
        output(args.provider, args.event, "")
        return 0

    context = dispatch(args.provider, args.event, payload)
    output(args.provider, args.event, context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
