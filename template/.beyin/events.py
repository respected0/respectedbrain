#!/usr/bin/env python3
"""Provider-neutral immutable handoff event log and projection engine."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid


def get_companion_dir(vault_root: Path) -> Path:
    """Find the 850-Companion folder within the vault root."""
    for item in vault_root.iterdir():
        if item.is_dir() and "850-Companion" in item.name:
            return item
    companion = vault_root / "🔮 850-Companion"
    companion.mkdir(parents=True, exist_ok=True)
    return companion


def get_events_dir(vault_root: Path) -> Path:
    """Return the append-only events directory."""
    events_dir = get_companion_dir(vault_root) / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    return events_dir


def _atomic_write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def record_event(
    vault_root: Path,
    provider: str,
    event_type: str,
    session_id: str,
    context: str = "",
    decisions: list[str] | None = None,
    learnings: list[str] | None = None,
    todos: list[str] | None = None,
    threads: list[dict[str, Any]] | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Record an immutable, append-only JSON event."""
    current_time = now or dt.datetime.now().astimezone()
    compact_ts = current_time.strftime("%Y%m%dT%H%M%SZ")
    iso_ts = current_time.isoformat()
    short_uid = uuid.uuid4().hex[:8]
    clean_provider = re.sub(r"[^a-zA-Z0-9_-]", "", provider) or "unknown"
    clean_type = re.sub(r"[^a-zA-Z0-9_-]", "", event_type) or "event"

    event_id = f"{compact_ts}-{clean_provider}-{clean_type}-{short_uid}"
    event_payload: dict[str, Any] = {
        "id": event_id,
        "ts": iso_ts,
        "provider": provider,
        "event_type": event_type,
        "session_id": session_id,
        "context": context,
        "decisions": decisions or [],
        "learnings": learnings or [],
        "todos": todos or [],
        "threads": threads or [],
    }

    events_dir = get_events_dir(vault_root)
    file_path = events_dir / f"{event_id}.json"
    _atomic_write_file(file_path, json.dumps(event_payload, ensure_ascii=False, indent=2) + "\n")
    return event_payload


def list_events(vault_root: Path) -> list[dict[str, Any]]:
    """Return all valid events sorted chronologically."""
    events_dir = get_events_dir(vault_root)
    if not events_dir.exists():
        return []
    records = []
    for file_path in sorted(events_dir.glob("*.json")):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                records.append(data)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return records


def project_companion(vault_root: Path) -> None:
    """Atomically project Last-Session.md and Threads.md from recorded events."""
    events = list_events(vault_root)
    if not events:
        return

    companion = get_companion_dir(vault_root)
    latest_session_event = None
    for event in reversed(events):
        if event.get("event_type") in {"session_end", "migration", "manual_note"}:
            latest_session_event = event
            break
    if latest_session_event is None:
        latest_session_event = events[-1]

    # 1. Project Last-Session.md
    ls_provider = latest_session_event.get("provider", "system")
    ls_ts = latest_session_event.get("ts", "")[:16].replace("T", " ")
    ls_context = latest_session_event.get("context", "").strip() or "Bağlam belirtilmedi."

    decisions_list = "\n".join(f"- {d}" for d in latest_session_event.get("decisions", [])) or "- Belirtilmedi."
    learnings_list = "\n".join(f"- {l}" for l in latest_session_event.get("learnings", [])) or "- Belirtilmedi."
    todos_list = "\n".join(f"- {t}" for t in latest_session_event.get("todos", [])) or "- Belirtilmedi."

    last_session_content = f"""---
title: Son Oturum
updated: {ls_ts}
provider: {ls_provider}
event_id: {latest_session_event.get('id', '')}
type: memory
tags: [companion, last-session]
---

# Son Oturum: {ls_context.splitlines()[0] if ls_context else 'Oturum'}

**Tarih:** {ls_ts} | **Provider:** {ls_provider}

## Bağlam
{ls_context}

## Alınan Kararlar
{decisions_list}

## Öğrenilenler
{learnings_list}

## Yapılacaklar
{todos_list}
"""
    _atomic_write_file(companion / "Last-Session.md", last_session_content)

    # 2. Project Threads.md
    thread_map: dict[str, dict[str, Any]] = {}
    for event in events:
        for thread in event.get("threads", []):
            if isinstance(thread, dict) and "title" in thread:
                title = thread["title"].strip()
                if title:
                    thread_map[title] = thread

    active_threads = []
    completed_threads = []
    pending_decisions = []

    for title, th in thread_map.items():
        status = th.get("status", "active")
        summary = th.get("summary", "")
        formatted = f"### Thread: {title}\n**Status:** {status}\n{summary}\n"
        if status == "completed":
            completed_threads.append(formatted)
        elif status == "pending_decision":
            pending_decisions.append(formatted)
        else:
            active_threads.append(formatted)

    threads_doc = f"""---
title: Aktif Konular
updated: {ls_ts}
type: memory
tags: [companion, threads]
---

# Aktif Konular (Threads)

## Açık Konular
{chr(10).join(active_threads) if active_threads else 'Aktif konu bulunmuyor.'}

## Karar Bekleyenler
{chr(10).join(pending_decisions) if pending_decisions else 'Karar bekleyen konu yok.'}

## Tamamlananlar
{chr(10).join(completed_threads) if completed_threads else 'Henüz tamamlanan konu arşivlenmedi.'}
"""
    _atomic_write_file(companion / "Threads.md", threads_doc)


def ensure_migration(vault_root: Path) -> bool:
    """Migrate legacy Last-Session.md and Threads.md into an initial event if no events exist."""
    companion = get_companion_dir(vault_root)
    events_dir = get_events_dir(vault_root)
    existing_events = list(events_dir.glob("*.json"))
    if existing_events:
        return False

    last_session_path = companion / "Last-Session.md"
    threads_path = companion / "Threads.md"
    if not last_session_path.is_file() and not threads_path.is_file():
        return False

    context = ""
    if last_session_path.is_file():
        context = last_session_path.read_text(encoding="utf-8")
    threads_summary = ""
    if threads_path.is_file():
        threads_summary = threads_path.read_text(encoding="utf-8")

    record_event(
        vault_root=vault_root,
        provider="system",
        event_type="migration",
        session_id="legacy-migration-0",
        context=context,
        decisions=["Mevcut Last-Session ve Threads dosyaları 1.4.0 event loguna aktarıldı."],
        learnings=["Kayıpsız migrasyon tamamlandı."],
        todos=[],
        threads=[{
            "title": "Legacy Context",
            "status": "active",
            "summary": threads_summary[:500] if threads_summary else "Tarihsel veriler",
        }],
        now=dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
    )
    return True
