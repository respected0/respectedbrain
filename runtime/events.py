#!/usr/bin/env python3
"""Provider-neutral immutable handoff event log and projection engine."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import time
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


DEFAULT_KEEP_EVENTS = 20


def get_events_archive_dir(vault_root: Path) -> Path:
    """Return the events archive directory."""
    archive_dir = get_events_dir(vault_root) / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


def rotate_events(vault_root: Path, keep_limit: int = DEFAULT_KEEP_EVENTS) -> list[Path]:
    """Rotate older events into events/archive/ keeping only the newest keep_limit events active."""
    events_dir = get_events_dir(vault_root)
    if not events_dir.exists():
        return []

    keep_limit = max(1, keep_limit)

    event_files = sorted(
        [p for p in events_dir.iterdir() if p.is_file() and p.suffix == ".json" and not p.name.startswith(".")],
        key=lambda p: p.name,
    )
    if len(event_files) <= keep_limit:
        return []

    archive_dir = get_events_archive_dir(vault_root)
    files_to_archive = event_files[:-keep_limit]
    archived_paths: list[Path] = []

    for file_path in files_to_archive:
        dest_path = archive_dir / file_path.name
        moved = False
        for attempt in range(5):
            try:
                if dest_path.exists():
                    dest_path.unlink()
                os.replace(file_path, dest_path)
                archived_paths.append(dest_path)
                moved = True
                break
            except (PermissionError, OSError):
                if attempt < 4:
                    time.sleep(0.02 * (attempt + 1))
        if not moved:
            try:
                dest_path.write_bytes(file_path.read_bytes())
                file_path.unlink()
                archived_paths.append(dest_path)
            except OSError:
                pass

    return archived_paths


def _atomic_write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8", newline="\n")
        for attempt in range(5):
            try:
                os.replace(temp_path, path)
                break
            except (PermissionError, OSError):
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
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
    """Record an immutable, append-only JSON event and rotate excess older events."""
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
    rotate_events(vault_root, keep_limit=DEFAULT_KEEP_EVENTS)
    return event_payload


def list_events(vault_root: Path, include_archive: bool = False) -> list[dict[str, Any]]:
    """Return all valid events sorted chronologically."""
    events_dir = get_events_dir(vault_root)
    if not events_dir.exists():
        return []

    files_to_read: list[Path] = []
    if include_archive:
        archive_dir = events_dir / "archive"
        if archive_dir.is_dir():
            files_to_read.extend(
                [p for p in archive_dir.iterdir() if p.is_file() and p.suffix == ".json" and not p.name.startswith(".")]
            )

    files_to_read.extend(
        [p for p in events_dir.iterdir() if p.is_file() and p.suffix == ".json" and not p.name.startswith(".")]
    )

    # Sort all files together chronologically by filename (compact ISO timestamp)
    files_to_read.sort(key=lambda p: p.name)

    records = []
    for file_path in files_to_read:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                records.append(data)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return records


def parse_threads_markdown(content: str) -> dict[str, dict[str, Any]]:
    """Parse existing Threads.md markdown into structured thread records."""
    if not content or not content.strip():
        return {}

    lines = content.splitlines()
    in_frontmatter = False
    frontmatter_count = 0
    current_section_status = "active"
    current_title: str | None = None
    current_status: str | None = None
    current_summary_lines: list[str] = []
    threads: dict[str, dict[str, Any]] = {}

    def commit_current():
        nonlocal current_title, current_status, current_summary_lines
        if current_title:
            cleaned_summary = "\n".join(current_summary_lines).strip()
            placeholders = [
                "Aktif konu bulunmuyor.",
                "Karar bekleyen konu yok.",
                "Henüz tamamlanan konu arşivlenmedi.",
            ]
            for p in placeholders:
                cleaned_summary = cleaned_summary.replace(p, "").strip()

            threads[current_title] = {
                "title": current_title,
                "status": current_status or current_section_status or "active",
                "summary": cleaned_summary,
            }
        current_title = None
        current_status = None
        current_summary_lines = []

    in_code_block = False
    for line in lines:
        stripped = line.strip()

        # Handle Markdown code block fences
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Handle YAML frontmatter
        if stripped == "---":
            frontmatter_count += 1
            in_frontmatter = frontmatter_count < 2
            continue
        if in_frontmatter:
            continue

        # Check section headings (## ...)
        if stripped.startswith("## "):
            commit_current()
            heading_text = stripped[3:].strip().lower()
            if any(w in heading_text for w in ("açık", "aktif", "active", "open", "in progress")):
                current_section_status = "active"
            elif any(w in heading_text for w in ("karar bekleyen", "pending", "decision")):
                current_section_status = "pending_decision"
            elif any(w in heading_text for w in ("tamamlanan", "arşiv", "archive", "closed", "completed", "done", "biten")):
                current_section_status = "completed"
            else:
                current_section_status = "active"
            continue

        # Check thread item heading (### ...)
        if stripped.startswith("### "):
            commit_current()
            raw_title = stripped[4:].strip()
            if raw_title.lower().startswith("thread:"):
                raw_title = raw_title[7:].strip()
            raw_title = re.sub(r"^[*_]+|[*_]+$", "", raw_title).strip()
            current_title = raw_title
            current_status = current_section_status
            current_summary_lines = []
            continue

        # Inside a thread item
        if current_title:
            status_match = re.match(r"^\*\*Status:\*\*\s*(.+)$", stripped, re.IGNORECASE)
            if status_match:
                raw_stat = status_match.group(1).strip().lower()
                if raw_stat in {"active", "in progress", "in_progress", "açık", "aktif", "devam", "open"}:
                    current_status = "active"
                elif raw_stat in {"pending_decision", "pending", "karar", "karar bekliyor", "decision"}:
                    current_status = "pending_decision"
                elif raw_stat in {"completed", "closed", "done", "tamamlandı", "tamamlanan", "biten"}:
                    current_status = "completed"
                else:
                    current_status = raw_stat
                continue

            if stripped in {
                "Aktif konu bulunmuyor.",
                "Karar bekleyen konu yok.",
                "Henüz tamamlanan konu arşivlenmedi.",
            }:
                continue

            current_summary_lines.append(line)

    commit_current()
    return threads


def load_existing_threads(vault_root: Path) -> dict[str, dict[str, Any]]:
    """Load existing threads from Threads.md if available."""
    companion = get_companion_dir(vault_root)
    threads_path = companion / "Threads.md"
    if not threads_path.is_file():
        return {}
    try:
        content = threads_path.read_text(encoding="utf-8")
        return parse_threads_markdown(content)
    except OSError:
        return {}


def project_companion(vault_root: Path) -> None:
    """Atomically project Last-Session.md and Threads.md from recorded events with read-merge protection."""
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

    # 2. Project Threads.md with Read-Merge & Protection Gate
    threads_path = companion / "Threads.md"
    existing_content = ""
    existing_threads: dict[str, dict[str, Any]] = {}
    if threads_path.is_file():
        try:
            existing_content = threads_path.read_text(encoding="utf-8")
            existing_threads = parse_threads_markdown(existing_content)
        except OSError:
            existing_threads = {}

    # Start with existing threads
    thread_map: dict[str, dict[str, Any]] = dict(existing_threads)

    # Merge threads from all recorded events
    for event in events:
        for thread in event.get("threads", []):
            if isinstance(thread, dict) and "title" in thread:
                title = thread["title"].strip()
                if title:
                    if title in thread_map:
                        merged = dict(thread_map[title])
                        merged.update(thread)
                        if not thread.get("summary") and thread_map[title].get("summary"):
                            merged["summary"] = thread_map[title]["summary"]
                        thread_map[title] = merged
                    else:
                        thread_map[title] = thread

    # PROTECTION GATE:
    # If thread_map is empty, check if existing Threads.md already has real content.
    # If it does, DO NOT overwrite it!
    if not thread_map and existing_content.strip():
        has_real_content = any(
            line.strip().startswith("### ") or (
                line.strip() and not line.strip().startswith("#") and not line.strip().startswith("-")
                and "bulunmuyor" not in line and "yok" not in line and "arşivlenmedi" not in line
            )
            for line in existing_content.splitlines()
        )
        if has_real_content:
            return

    def normalize_status(raw_status: str) -> str:
        s = raw_status.strip().lower()
        if s in {"active", "in progress", "in_progress", "açık", "aktif", "open", "devam"}:
            return "active"
        if s in {"pending_decision", "pending", "karar", "karar bekliyor", "decision"}:
            return "pending_decision"
        if s in {"completed", "closed", "done", "tamamlandı", "tamamlanan", "biten"}:
            return "completed"
        return "active"

    active_threads = []
    completed_threads = []
    pending_decisions = []

    for title, th in thread_map.items():
        status = normalize_status(th.get("status", "active"))
        summary = th.get("summary", "").strip()
        summary_block = f"\n{summary}\n" if summary else "\n"
        formatted = f"### Thread: {title}\n**Status:** {status}{summary_block}"
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
