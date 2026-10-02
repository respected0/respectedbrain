#!/usr/bin/env python3
"""Normalize provider-native hook payloads into the shared Respected Brain runtime."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence


for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


HOOK_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = HOOK_DIR.parent
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import lifecycle as LIFECYCLE
import runtime_platform
try:
    import runtime_hub
except ImportError:
    runtime_hub = None

ROOT = Path(__file__).resolve().parents[2]


EVENTS = ("start", "prompt", "turn", "end", "precompact", "postcompact")
SESSION_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


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


def resolve_antigravity_transcript(
    session_id: str,
    home: Path | None = None,
) -> str:
    """Resolve a known Antigravity transcript without scanning user data."""

    if (
        SESSION_COMPONENT.fullmatch(session_id) is None
        or session_id in {".", ".."}
    ):
        return ""
    profile = home or runtime_platform.windows_user_root(ROOT) or Path.home()
    for product in ("antigravity-ide", "antigravity-cli", "antigravity"):
        brain = profile / ".gemini" / product / "brain"
        candidate = (
            brain
            / session_id
            / ".system_generated"
            / "logs"
            / "transcript.jsonl"
        )
        try:
            candidate.resolve(strict=True).relative_to(brain.resolve(strict=True))
        except (OSError, RuntimeError, ValueError):
            continue
        if candidate.is_file():
            return str(candidate)
    return ""


def antigravity_session_from_transcript(transcript_path: str) -> str:
    """Derive the stable CLI conversation key from a validated transcript path."""

    if not transcript_path:
        return ""
    try:
        resolved = Path(transcript_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return ""
    parts = resolved.parts
    products = {"antigravity-ide", "antigravity-cli", "antigravity"}
    for index in range(len(parts) - 6):
        if (
            parts[index].casefold() == ".gemini"
            and parts[index + 1].casefold() in products
            and parts[index + 2].casefold() == "brain"
            and parts[index + 4].casefold() == ".system_generated"
            and parts[index + 5].casefold() == "logs"
            and parts[index + 6].casefold() == "transcript.jsonl"
        ):
            session_id = parts[index + 3]
            if SESSION_COMPONENT.fullmatch(session_id) and session_id not in {".", ".."}:
                return session_id
    return ""


def resolve_codex_transcript(
    session_id: str,
    home: Path | None = None,
) -> str:
    """Resolve a known Codex rollout transcript without scanning entire user data."""

    if (
        SESSION_COMPONENT.fullmatch(session_id) is None
        or session_id in {".", ".."}
        or session_id.endswith("-unknown")
    ):
        return ""
    profile = home or runtime_platform.windows_user_root(ROOT) or Path.home()
    codex_home = profile / ".codex"
    if not codex_home.is_dir():
        return ""
    for folder_name in ("sessions", "archived_sessions"):
        root = codex_home / folder_name
        if not root.is_dir():
            continue
        try:
            matches = list(root.glob(f"**/*{session_id}*.jsonl"))
        except OSError:
            continue
        if matches:
            for match in sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    match.resolve(strict=True).relative_to(codex_home.resolve(strict=True))
                    if match.is_file():
                        return str(match)
                except (OSError, RuntimeError, ValueError):
                    continue
    return ""


def normalize(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace_paths = payload.get("workspacePaths") or payload.get("workspace_roots") or []
    cwd = first_string(payload, "cwd")
    if not cwd and isinstance(workspace_paths, list) and workspace_paths:
        cwd = str(workspace_paths[0])
    session_id = first_string(payload, "session_id", "conversation_id", "conversationId")
    if not session_id:
        session_id = f"{provider}-unknown"
    transcript_path = wsl_path(
        first_string(payload, "transcript_path", "transcriptPath")
    )
    if not transcript_path:
        if provider == "antigravity":
            transcript_path = resolve_antigravity_transcript(session_id)
        elif provider == "codex":
            transcript_path = resolve_codex_transcript(session_id)
    transcript_path = wsl_path(transcript_path)
    if provider == "antigravity":
        stable_session_id = antigravity_session_from_transcript(transcript_path)
        if stable_session_id:
            session_id = stable_session_id
    return {
        **payload,
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": wsl_path(cwd) or str(ROOT),
        "model": first_string(payload, "model", "modelName"),
        "beyin_provider": provider,
    }


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
    elif provider == "gemini":
        if context:
            event_name = {
                "start": "SessionStart",
                "prompt": "BeforeAgent",
                "turn": "AfterAgent",
                "end": "SessionEnd",
                "precompact": "PreCompress",
                "postcompact": "PostCompact",
            }[event]
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": event_name,
                            "additionalContext": context,
                        }
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print("{}")
    elif context:
        event_name = {
            "start": "SessionStart",
            "prompt": "UserPromptSubmit",
            "turn": "Stop" if provider == "claude" else "AfterAgent",
            "end": "SessionEnd",
            "precompact": "PreCompact" if provider == "claude" else "PreCompress",
            "postcompact": "PostCompact",
        }[event]
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": context}}, ensure_ascii=False))


def dispatch(provider: str, event: str, payload: dict[str, Any], vault_root: Path | None = None) -> str:
    if os.environ.get("BEYIN_INVOKED_BY"):
        return ""
    normalized = normalize(provider, payload)
    target_vault = vault_root
    if not target_vault:
        if ROOT != Path(__file__).resolve().parents[2]:
            target_vault = ROOT
        elif runtime_hub:
            target_vault = runtime_hub.resolve_vault_path(runtime_dir=RUNTIME_DIR)
        else:
            target_vault = ROOT
    return LIFECYCLE.handle(event, normalized, target_vault, provider)


def inside_vault(active: str, vault_root: Path | None = None) -> bool:
    r"""Compare native Windows and POSIX workspace paths without treating C:\... as relative in WSL."""
    target_root = vault_root
    if not target_root:
        if ROOT != Path(__file__).resolve().parents[2]:
            target_root = ROOT
        elif runtime_hub:
            target_root = runtime_hub.resolve_vault_path(runtime_dir=RUNTIME_DIR)
        else:
            target_root = ROOT
    normalized = active.replace("\\", "/").rstrip("/")
    if re.match(r"^[A-Za-z]:/", normalized):
        candidate = os.path.normpath(normalized).replace("\\", "/").casefold()
        if target_root.drive or re.match(r"^[A-Za-z]:/", str(target_root).replace("\\", "/")):
            root_folded = os.path.normpath(str(target_root).replace("\\", "/")).replace("\\", "/").rstrip("/").casefold()
            return candidate == root_folded or candidate.startswith(root_folded + "/")
        parts = target_root.parts
        if len(parts) < 4 or parts[1] != "mnt" or len(parts[2]) != 1:
            return False
        root_native = f"{parts[2]}:/" + "/".join(parts[3:])
        root_folded = os.path.normpath(root_native).replace("\\", "/").rstrip("/").casefold()
        return candidate == root_folded or candidate.startswith(root_folded + "/")
    path = Path(active)
    if not path.is_absolute():
        return False
    try:
        path.resolve().relative_to(target_root.resolve())
    except (OSError, ValueError):
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    if LIFECYCLE._is_reentrant():
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=("claude", "codex", "cursor", "antigravity", "gemini"),
        required=True,
    )
    parser.add_argument("--event", choices=EVENTS, required=True)
    parser.add_argument("--global-hook", action="store_true", help="vault dışındaki repolar için kullanıcı düzeyi hook")
    parser.add_argument("--vault", type=Path, default=None, help="Target vault root directory")
    args = parser.parse_args(argv)
    payload = normalize(args.provider, load_input())

    target_vault = args.vault.resolve() if args.vault else (runtime_hub.resolve_vault_path(runtime_dir=RUNTIME_DIR) if runtime_hub else ROOT) or ROOT

    if args.global_hook:
        active = payload.get("cwd")
        if isinstance(active, str) and inside_vault(active, target_vault):
            output(args.provider, args.event, "")
            return 0

    # Antigravity invokes PreInvocation before every model call. Initialize only once.
    if args.provider == "antigravity" and args.event == "start":
        inv = payload.get("invocationNum")
        if inv is not None and isinstance(inv, int):
            state_dir = LIFECYCLE._state_dir(target_vault)
            key = LIFECYCLE.session_key(payload["session_id"])
            LIFECYCLE._atomic_write(state_dir / f"prompt_count.{key}", f"{inv + 1}\n")
        if inv not in (None, 0):
            output(args.provider, args.event, "")
            return 0

    try:
        context = dispatch(args.provider, args.event, payload, target_vault)
        output(args.provider, args.event, context)
    except Exception as error:
        state_dir = LIFECYCLE._state_dir(target_vault)
        LIFECYCLE._record_health(state_dir, args.event, f"bridge-error:{type(error).__name__}:{error}", datetime.now())
        output(args.provider, args.event, "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
