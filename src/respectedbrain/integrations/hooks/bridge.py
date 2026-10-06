"""Explicit-context provider hooks; return native protocol output to the caller."""
from __future__ import annotations
import contextlib
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from respectedbrain.memory import lifecycle as LIFECYCLE
from respectedbrain.core.coordination import guarded_writer
from respectedbrain.core.platform import path_within_vault
EVENTS = ("start", "prompt", "turn", "end", "precompact", "postcompact")
SESSION_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
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
    profile = home or Path.home()
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
    profile = home or Path.home()
    codex_home = profile / ".codex"
    if not codex_home.is_dir():
        return ""
    for folder_name in ("sessions", "archived_sessions"):
        root = codex_home / folder_name
        if not root.is_dir() or not path_within_vault(root, codex_home):
            continue
        matches = []
        for directory, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if path_within_vault(Path(directory) / d, codex_home)]
            for filename in files:
                if not (filename == session_id + '.jsonl' or filename.endswith('-' + session_id + '.jsonl')):
                    continue
                match = Path(directory) / filename
                try:
                    if path_within_vault(match, codex_home) and match.is_file():
                        matches.append((match.stat().st_mtime, str(match)))
                except (OSError, RuntimeError, ValueError):
                    continue
        if matches:
            return max(matches)[1]
    return ""


def normalize(provider: str, payload: dict[str, Any], *, vault_root: Path, home: Path | None = None) -> dict[str, Any]:
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
            transcript_path = resolve_antigravity_transcript(session_id, home)
        elif provider == "codex":
            transcript_path = resolve_codex_transcript(session_id, home)
    transcript_path = wsl_path(transcript_path)
    if provider == "antigravity":
        stable_session_id = antigravity_session_from_transcript(transcript_path)
        if stable_session_id:
            session_id = stable_session_id
    return {
        **payload,
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": wsl_path(cwd) or str(vault_root),
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


def inside_vault(active: str, vault_root: Path | None = None) -> bool:
    r"""Compare native Windows and POSIX workspace paths without treating C:\... as relative in WSL."""
    target_root = vault_root
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


@guarded_writer(busy_result="")
def _dispatch_event(ctx, *, provider, event, argv, stdin):
    if event == "notify" and provider == "codex":
        from .codex_notify import dispatch as notify
        return notify(ctx, argv=argv, stdin=stdin)
    if event not in EVENTS or provider not in {"claude", "codex", "cursor", "antigravity", "gemini"}:
        raise ValueError("Unsupported hook provider/event")
    if LIFECYCLE._is_reentrant():
        return ""
    try:
        payload = json.loads(stdin) if stdin.strip() else {}
    except (ValueError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload = normalize(provider, payload, vault_root=ctx.paths.vault_root)
    payload["provider"] = provider
    context = ""
    skip = "--global-hook" in argv and inside_vault(payload["cwd"], ctx.paths.vault_root)
    now = datetime.now().astimezone()
    if provider == "antigravity" and event == "start":
        inv = payload.get("invocationNum")
        if isinstance(inv, int):
            ctx.paths.state_dir.mkdir(parents=True, exist_ok=True)
            LIFECYCLE._atomic_write(ctx.paths.state_dir / f"prompt_count.{LIFECYCLE.session_key(payload['session_id'])}", f"{inv + 1}\n")
        skip = skip or inv not in (None, 0)
    if not skip:
        try:
            transcript = Path(payload["transcript_path"]) if payload["transcript_path"] else None
            context = LIFECYCLE.handle_event(ctx, event=event, session_id=payload["session_id"], transcript=transcript, payload=payload, now=now)
        except Exception as error:
            ctx.paths.state_dir.mkdir(parents=True, exist_ok=True)
            LIFECYCLE._record_health(ctx.paths.state_dir, event, f"bridge-error:{type(error).__name__}:{error}", now)
    result = io.StringIO()
    with contextlib.redirect_stdout(result):
        output(provider, event, context)
    return result.getvalue()


def dispatch(ctx, *, provider, event, argv, stdin):
    if LIFECYCLE._is_reentrant():
        return ""
    return _dispatch_event(ctx, provider=provider, event=event, argv=argv, stdin=stdin)
