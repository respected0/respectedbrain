#!/usr/bin/env python3
"""Provider-neutral Respected session lifecycle and relational-memory context."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from typing import Any, Sequence
import uuid


BEYIN_DIR = Path(__file__).resolve().parents[1]
if str(BEYIN_DIR) not in sys.path:
    sys.path.insert(0, str(BEYIN_DIR))

import runtime_platform

try:
    from map_builder import refresh_maps
except ImportError:  # Compatibility while an older vault is being updated.
    refresh_maps = None


MAX_CONTEXT = 16_000
CLOSING = (
    "[Hafıza] Süreklilik senin sorumluluğun. Bu kullanıcı için kim olduğunu anlamak üzere "
    "🔮 850-Companion/Core.md dosyasını oku.\nHafıza protokolü zorunludur."
)
TRUNCATION_NOTE = "[not: indeks kırpıldı, beyin-doktor çalıştır]"
CAP_DIAGNOSTIC = (
    "Beyin uyarısı: Oturum başlangıç bağlamı 16.000 karakter sınırına sığmadı. "
    "Bölüm limitlerini kontrol etmek için beyin-doktor çalıştır."
)


def session_key(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _state_dir(vault_root: Path) -> Path:
    return vault_root / ".claude" / "scripts" / ".state"


def _atomic_write(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.chmod(temporary, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def _read_lines(path: Path, limit: int | None = None) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    return lines if limit is None else lines[:limit]


def _read_integer(path: Path) -> int:
    try:
        value = path.read_text(encoding="utf-8").splitlines()[0]
        return int(value) if value.isdigit() else 0
    except (OSError, IndexError, UnicodeError):
        return 0


def _cleanup_session_state(state_dir: Path, now: datetime) -> None:
    cutoff = now.timestamp() - timedelta(days=7).total_seconds()
    patterns = (
        "session_start_time.*",
        "prompt_count.*",
        "needs_reflection.*",
        "hookin-*.json",
        "morning-briefing-*.lock",
    )
    for pattern in patterns:
        for candidate in state_dir.glob(pattern):
            try:
                if candidate.is_file() and candidate.stat().st_mtime < cutoff:
                    candidate.unlink(missing_ok=True)
            except OSError:
                continue


def _last_session(memory_dir: Path) -> str:
    lines = _read_lines(memory_dir / "Last-Session.md")
    selected: list[str] = []
    active = False
    for line in lines:
        if line.startswith("## Session:"):
            active = True
        if active and line.startswith("## Previous"):
            break
        if active:
            selected.append(line)
        if len(selected) == 50:
            break
    return "\n".join(selected)


def _active_threads(memory_dir: Path) -> str:
    lines = _read_lines(memory_dir / "Threads.md")
    selected: list[str] = []
    active = False
    for line in lines:
        if line.startswith("## Active"):
            active = True
            continue
        if active and line.startswith("## Closed"):
            break
        if active and (line.startswith("### ") or line.startswith("**Status:**")):
            selected.append(line)
        if len(selected) == 12:
            break
    return "\n".join(selected)


def _latest_journal(memory_dir: Path) -> str:
    lines = _read_lines(memory_dir / "Journal.md")
    headings = [index for index, line in enumerate(lines) if line.startswith("## ")]
    if not headings:
        return ""
    start = headings[-1]
    return "\n".join(lines[start : start + 10])


def _daily(vault_root: Path, now: datetime) -> str:
    daily_dir = vault_root / "daily"
    today = daily_dir / f"{now:%Y-%m-%d}.md"
    yesterday = daily_dir / f"{now - timedelta(days=1):%Y-%m-%d}.md"
    path = today if today.is_file() else yesterday
    lines = _read_lines(path)
    return "\n".join(lines[-25:])


def _reflection_debt(state_dir: Path) -> str:
    paths = [state_dir / "needs_reflection", *sorted(state_dir.glob("needs_reflection.*"))]
    messages: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        lines = _read_lines(path, 1)
        if lines and lines[0]:
            messages.append(
                "⚠️ Önceki oturum hafıza güncellemeden bitti: "
                f"{lines[0]}. Anlamlı bir şey olduysa 🔮 850-Companion dosyalarını güncelle."
            )
        path.unlink(missing_ok=True)
    return "\n".join(messages)


def _cap(value: str, limit: int, note: str) -> str:
    if len(value) <= limit:
        return value
    keep = max(limit - len(note) - 1, 0)
    return f"{value[:keep]}\n{note}"


def _build_context(sections: dict[str, str], reflection: str, truncated: bool) -> str:
    chunks: list[str] = []
    if reflection:
        chunks.append(reflection)
    for heading, value in sections.items():
        if value:
            chunks.append(f"{heading}\n{value}")
    if truncated:
        chunks.append(TRUNCATION_NOTE)
    chunks.append(CLOSING)
    return "\n\n".join(chunks)


def _fit_context(sections: dict[str, str], reflection: str) -> str:
    context = _build_context(sections, reflection, False)
    if len(context) <= MAX_CONTEXT:
        return context

    truncated = True
    context = _build_context(sections, reflection, truncated)
    shrink_order = (
        ("[Bilgi Tabanı: İndeks]", "front"),
        ("[Bugünün Logu]", "back"),
        ("[Hafıza: Son Journal]", "front"),
    )
    for heading, side in shrink_order:
        over = len(context) - MAX_CONTEXT
        value = sections[heading]
        if over > 0 and value:
            if over >= len(value):
                sections[heading] = ""
            elif side == "front":
                sections[heading] = value[: len(value) - over]
            else:
                sections[heading] = value[over:]
            context = _build_context(sections, reflection, truncated)

    over = len(context) - MAX_CONTEXT
    if over > 0 and reflection:
        reflection = "" if over >= len(reflection) else reflection[: len(reflection) - over]
        context = _build_context(sections, reflection, truncated)
    return context if len(context) <= MAX_CONTEXT else CAP_DIAGNOSTIC


def _record_health(state_dir: Path, event: str, error: str, now: datetime) -> None:
    payload = {
        "status": "degraded",
        "event": event,
        "error": error,
        "updated_at": now.isoformat(timespec="seconds"),
    }
    try:
        _atomic_write(state_dir / "health.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        pass


def _launch_flush(
    vault_root: Path,
    state_dir: Path,
    provider: str,
    *,
    payload: dict[str, Any] | None = None,
    reason: str | None = None,
    maybe_compile: bool = False,
) -> bool:
    script = vault_root / ".claude" / "scripts" / "flush.py"
    command = [sys.executable, str(script)]
    hook_input: Path | None = None
    if maybe_compile:
        command.append("--maybe-compile")
    if payload is not None:
        hook_input = state_dir / f"hookin-{os.getpid()}-{uuid.uuid4().hex}.json"
        _atomic_write(hook_input, json.dumps(payload, ensure_ascii=False) + "\n")
        command.extend(("--hook-input", str(hook_input)))
    if reason:
        command.extend(("--reason", reason))

    environment = os.environ.copy()
    environment["BEYIN_PROVIDER"] = provider
    try:
        process = subprocess.Popen(
            command,
            cwd=vault_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            **runtime_platform.detached_process_options(),
        )
    except OSError:
        if hook_input is not None:
            hook_input.unlink(missing_ok=True)
        return False
    threading.Thread(target=process.wait, name="respected-flush-reaper", daemon=True).start()
    return True


def start_context(vault_root: Path, state_dir: Path, session_id: str, now: datetime) -> str:
    state_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_session_state(state_dir, now)
    key = session_key(session_id)
    _atomic_write(state_dir / f"session_start_time.{key}", f"{int(now.timestamp())}\n")
    _atomic_write(state_dir / f"prompt_count.{key}", "0\n")

    memory_dir = vault_root / "🔮 850-Companion"
    if refresh_maps is not None:
        try:
            vault_map_path, skills_map_path = refresh_maps(vault_root)
        except (OSError, UnicodeError, ValueError):
            vault_map_path = vault_root / "🎯 100-Command-Center/Vault-Map.md"
            skills_map_path = vault_root / "🎯 100-Command-Center/Skills-Map.md"
    else:
        vault_map_path = vault_root / "🎯 100-Command-Center/Vault-Map.md"
        skills_map_path = vault_root / "🎯 100-Command-Center/Skills-Map.md"
    sections = {
        "[Hafıza: Son Oturum]": _cap(
            _last_session(memory_dir),
            4_000,
            "[not: son oturum 4.000 karakterde kırpıldı, beyin-doktor çalıştır]",
        ),
        "[Hafıza: Aktif Konular]": _cap(
            _active_threads(memory_dir),
            2_000,
            "[not: aktif konular 2.000 karakterde kırpıldı, beyin-doktor çalıştır]",
        ),
        "[Hafıza: Kurallar]": _cap(
            "\n".join(_read_lines(memory_dir / "Kurallar.md", 60)),
            4_000,
            "[not: kurallar 4.000 karakterde kırpıldı, beyin-doktor çalıştır]",
        ),
        "[Hafıza: Son Journal]": _cap(
            _latest_journal(memory_dir),
            1_500,
            "[not: son Journal 1.500 karakterde kırpıldı, beyin-doktor çalıştır]",
        ),
        "[Beyin Haritası]": _cap(
            "\n".join(_read_lines(vault_map_path, 120)),
            2_500,
            "[not: Vault Map 2.500 karakterde kırpıldı]",
        ),
        "[Skills Haritası]": _cap(
            "\n".join(_read_lines(skills_map_path, 80)),
            1_500,
            "[not: Skills Map 1.500 karakterde kırpıldı]",
        ),
        "[Bilgi Tabanı: İndeks]": "\n".join(
            _read_lines(vault_root / "knowledge" / "index.md", 150)
        ),
        "[Bugünün Logu]": _daily(vault_root, now),
    }
    reflection = _cap(
        _reflection_debt(state_dir),
        1_000,
        "[not: hafıza uyarıları 1.000 karakterde kırpıldı, beyin-doktor çalıştır]",
    )
    return _fit_context(sections, reflection)


def count_prompt(state_dir: Path, session_id: str) -> str:
    state_dir.mkdir(parents=True, exist_ok=True)
    key = session_key(session_id)
    counter = state_dir / f"prompt_count.{key}"
    lock_path = state_dir / f"prompt_count.{key}.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        with runtime_platform.exclusive_lock(lock_handle, blocking=True) as held:
            if not held:
                return ""
            count = _read_integer(counter) + 1
            _atomic_write(counter, f"{count}\n")
    if count % 15:
        return ""
    return (
        f"[Hafıza] {count}. mesaj. Oturum sonunda 🔮 850-Companion/Last-Session.md "
        "ve Threads.md güncellemeyi unutma."
    )


def _finish_session(
    vault_root: Path,
    state_dir: Path,
    payload: dict[str, Any],
    reason: str,
    now: datetime,
    provider: str,
) -> str:
    key = session_key(payload["session_id"])
    start_file = state_dir / f"session_start_time.{key}"
    prompt_file = state_dir / f"prompt_count.{key}"
    reflection_file = state_dir / f"needs_reflection.{key}"
    start = _read_integer(start_file)
    prompts = _read_integer(prompt_file)
    last_session = vault_root / "🔮 850-Companion" / "Last-Session.md"
    try:
        modified = last_session.stat().st_mtime > start
    except OSError:
        modified = False
    if reason == "end" and prompts >= 5 and not modified:
        detail = f"Oturum hafıza güncellemeden bitti. Prompt: {prompts}. {now:%Y-%m-%d %H:%M}\n"
        _atomic_write(reflection_file, detail)

    launched = _launch_flush(
        vault_root,
        state_dir,
        provider,
        payload=payload,
        reason="precompact" if reason == "precompact" else None,
    )
    if not launched:
        _record_health(state_dir, reason, "flush-launch-failed", now)
    if reason == "end":
        start_file.unlink(missing_ok=True)
        prompt_file.unlink(missing_ok=True)
    return ""


def handle(
    event: str,
    payload: dict[str, Any],
    vault_root: Path,
    provider: str,
    now: datetime | None = None,
) -> str:
    current = now or datetime.now()
    vault = Path(vault_root)
    state_dir = _state_dir(vault)
    state_dir.mkdir(parents=True, exist_ok=True)
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not isinstance(session_id, str) or not session_id:
        _record_health(state_dir, event, "missing-session-id", current)
        return ""
    try:
        if event == "start":
            context = start_context(vault, state_dir, session_id, current)
            if not _launch_flush(vault, state_dir, provider, maybe_compile=True):
                _record_health(state_dir, event, "catch-up-launch-failed", current)
            return context
        if event == "prompt":
            return count_prompt(state_dir, session_id)
        if event in ("end", "precompact"):
            return _finish_session(vault, state_dir, payload, event, current, provider)
        _record_health(state_dir, event, "unknown-event", current)
    except (OSError, UnicodeError, ValueError) as error:
        _record_health(state_dir, event, f"{type(error).__name__}: {error}", current)
    return ""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", choices=("start", "prompt", "end", "precompact"), required=True)
    parser.add_argument("--provider", default=os.environ.get("BEYIN_PROVIDER", "claude"))
    parser.add_argument("--vault-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        value = {}
    context = handle(args.event, value if isinstance(value, dict) else {}, args.vault_root, args.provider)
    if context:
        print(context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
