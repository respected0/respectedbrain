"""Codex notifier preserving original handlers and opaque JSON arguments."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from respectedbrain.memory import lifecycle
from respectedbrain.core.coordination import writer_lease
from respectedbrain.core.errors import BusyError
from respectedbrain.core.platform import path_within_vault
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


def _chain_file_and_payload(argv: list[str]) -> tuple[Path | None, list[str]]:
    payload_args = list(argv)
    try:
        index = payload_args.index("--chain-file")
    except ValueError:
        return None, payload_args
    if index + 1 >= len(payload_args):
        return None, payload_args
    chain_file = Path(payload_args[index + 1])
    del payload_args[index:index + 2]
    return chain_file, payload_args


def _wsl_executable(value: str) -> str:
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", value):
        drive = value[0].lower()
        tail = value[2:].lstrip('\\/').replace('\\', '/')
        return f"/mnt/{drive}/{tail}"
    return value


def _read_persisted_chain(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        argv = document.get("argv") if isinstance(document, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        return None
    command = list(argv)
    command[0] = _wsl_executable(command[0])
    return command


def _forward_chained(argv: list[str]) -> None:
    chain_file, payload_args = _chain_file_and_payload(argv)
    persisted = _read_persisted_chain(chain_file)
    if persisted:
        try:
            subprocess.Popen(
                [*persisted, *payload_args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0),
                close_fds=True,
            )
            return
        except Exception:
            pass

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
        if os.path.isfile(target) or shutil.which(target):
            try:
                subprocess.Popen(
                    [target, "turn-ended", *payload_args],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=flags,
                    close_fds=True,
                )
                break
            except Exception:
                pass


def dispatch(ctx, *, argv, stdin):
    if lifecycle._is_reentrant():
        return ""
    args = list(argv)
    chain, payload_args = _chain_file_and_payload(args)
    if chain is not None and (chain.absolute() != (ctx.paths.state_dir / "codex-notify-chain.json").absolute()
                              or not path_within_vault(chain, ctx.paths.data_root)):
        raise ValueError("Notify chain must belong to the selected vault UUID")
    _forward_chained(args)
    payload = _parse_payload(payload_args or ([stdin] if stdin.strip() else []))
    if payload.get("client") == "codex_exec":
        return ""
    thread_id = payload.get("thread-id") or payload.get("thread_id") or payload.get("session_id")
    if not thread_id:
        return ""
    from .bridge import resolve_codex_transcript
    transcript = resolve_codex_transcript(str(thread_id))
    if not transcript:
        return ""
    normalized = dict(payload, session_id=str(thread_id), transcript_path=transcript, provider="codex", cwd=payload.get("cwd") or str(ctx.paths.vault_root))
    try:
        with writer_lease(ctx):
            lifecycle._launch_flush(ctx, "codex", payload=normalized, reason="turn")
    except BusyError:
        pass
    return ""
