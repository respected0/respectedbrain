#!/usr/bin/env python3
"""Tests for provider-neutral immutable handoff event log and projection engine (Faz 3)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "template/.beyin/events.py"


def load_events_module():
    spec = importlib.util.spec_from_file_location("events_module", EVENTS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EventLogTest(unittest.TestCase):
    def setUp(self):
        self.events = load_events_module()

    def test_record_event_creates_immutable_json_file(self):
        """record_event must create a valid append-only JSON file under companion/events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)

            event = self.events.record_event(
                vault_root=vault_root,
                provider="codex",
                event_type="session_end",
                session_id="sess-123",
                context="Respected Brain 1.4.0 mimarisi geliştirildi.",
                decisions=["Immutable event log mimarisi onaylandı."],
                learnings=["Projeksiyonlar deterministik üretilmeli."],
                todos=["Event testlerini tamamla."],
                threads=[{
                    "title": "1.4.0 Event Log Mimarisi",
                    "status": "active",
                    "summary": "Mimarinin ilk sürümü kodlanıyor.",
                }],
            )

            events_dir = companion / "events"
            self.assertTrue(events_dir.is_dir())
            event_files = list(events_dir.glob("*.json"))
            self.assertEqual(len(event_files), 1)

            saved = json.loads(event_files[0].read_text(encoding="utf-8"))
            self.assertEqual(saved["provider"], "codex")
            self.assertEqual(saved["event_type"], "session_end")
            self.assertIn("Immutable event log mimarisi onaylandı.", saved["decisions"])

    def test_projection_generates_last_session_and_threads(self):
        """project_companion must generate human-readable Last-Session.md and Threads.md from events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)

            self.events.record_event(
                vault_root=vault_root,
                provider="antigravity",
                event_type="session_end",
                session_id="sess-agy",
                context="Antigravity oturumu tamamlandı.",
                decisions=["Karar A alındı."],
                learnings=["Öğrenilen B not edildi."],
                todos=["İş C yapılacak."],
                threads=[{
                    "title": "Thread 1",
                    "status": "active",
                    "summary": "İlerleme kaydedildi.",
                }],
            )

            self.events.project_companion(vault_root)

            last_session = companion / "Last-Session.md"
            threads = companion / "Threads.md"
            self.assertTrue(last_session.is_file())
            self.assertTrue(threads.is_file())

            ls_text = last_session.read_text(encoding="utf-8")
            self.assertIn("Antigravity oturumu tamamlandı.", ls_text)
            self.assertIn("Karar A alındı.", ls_text)

            th_text = threads.read_text(encoding="utf-8")
            self.assertIn("Thread 1", th_text)
            self.assertIn("İlerleme kaydedildi.", th_text)

    def test_initial_migration_preserves_existing_last_session_and_threads(self):
        """If events are absent, initial migration must capture existing markdown files without data loss."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)

            # Create existing historical files
            (companion / "Last-Session.md").write_text("# Tarihsel Son Oturum\nEski bağlam verisi.", encoding="utf-8")
            (companion / "Threads.md").write_text("# Eski Konular\nEski açık işler.", encoding="utf-8")

            migrated = self.events.ensure_migration(vault_root)
            self.assertTrue(migrated)

            events_dir = companion / "events"
            self.assertTrue(events_dir.is_dir())
            migration_files = list(events_dir.glob("*migration*.json"))
            self.assertEqual(len(migration_files), 1)

            data = json.loads(migration_files[0].read_text(encoding="utf-8"))
            self.assertIn("Eski bağlam verisi", data["context"])


    def test_event_rotation_archives_excess_files_and_preserves_limit(self):
        """When event count exceeds keep_limit, older events must move to archive/ without data loss."""
        import datetime as dt
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)

            base_time = dt.datetime(2026, 9, 1, 10, 0, 0, tzinfo=dt.timezone.utc)
            for i in range(25):
                event_time = base_time + dt.timedelta(minutes=i)
                self.events.record_event(
                    vault_root=vault_root,
                    provider="antigravity",
                    event_type="session_end",
                    session_id=f"sess-{i:03d}",
                    context=f"Oturum {i}",
                    now=event_time,
                )

            events_dir = companion / "events"
            active_files = [p for p in events_dir.iterdir() if p.is_file() and p.suffix == ".json"]
            self.assertEqual(len(active_files), 20)

            archive_dir = events_dir / "archive"
            self.assertTrue(archive_dir.is_dir())
            archived_files = [p for p in archive_dir.iterdir() if p.is_file() and p.suffix == ".json"]
            self.assertEqual(len(archived_files), 5)

            # list_events default should return 20 active events
            active_events = self.events.list_events(vault_root)
            self.assertEqual(len(active_events), 20)

            # list_events with include_archive should return all 25 events
            all_events = self.events.list_events(vault_root, include_archive=True)
            self.assertEqual(len(all_events), 25)

    def test_project_companion_preserves_threads_when_events_have_empty_threads(self):
        """Existing Threads.md must not be wiped when flush/session records empty threads."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)

            existing_threads_content = """---
title: Aktif Konular
updated: 2026-09-08 02:33
type: memory
tags: [companion, threads]
---

# Aktif Konular (Threads)

## Açık Konular
### Thread: Respected Brain v0.0.1 Public Release & Kasa Mimarisi İyileştirmeleri
**Status:** active
Kapsam: Event rotasyonu & Threads.md koruması, Karpathy LLM Wiki.
Detaylı Yol Haritası: [[v0.0.1-Public-Release-Yol-Haritasi.md]]

## Karar Bekleyenler
Karar bekleyen konu yok.

## Tamamlananlar
Henüz tamamlanan konu arşivlenmedi.
"""
            (companion / "Threads.md").write_text(existing_threads_content, encoding="utf-8")

            # Record event with empty threads list
            self.events.record_event(
                vault_root=vault_root,
                provider="antigravity",
                event_type="session_end",
                session_id="sess-empty-threads",
                context="Yeni oturum tamamlandı.",
                decisions=["Karar alındı."],
                threads=[],
            )

            self.events.project_companion(vault_root)

            threads_doc = (companion / "Threads.md").read_text(encoding="utf-8")
            self.assertIn("Respected Brain v0.0.1 Public Release & Kasa Mimarisi İyileştirmeleri", threads_doc)
            self.assertIn("v0.0.1-Public-Release-Yol-Haritasi.md", threads_doc)
            self.assertNotIn("Aktif konu bulunmuyor.", threads_doc)

    def test_project_companion_merges_thread_updates_and_status_changes(self):
        """Threads from existing markdown and new events must merge accurately with status updates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)

            existing_threads_content = """# Aktif Konular (Threads)

## Açık Konular
### Thread: Thread Alpha
**Status:** active
Alpha detayları.

### Thread: Thread Beta
**Status:** active
Beta detayları.
"""
            (companion / "Threads.md").write_text(existing_threads_content, encoding="utf-8")

            # Event updates Thread Alpha to completed, and adds Thread Gamma as active
            self.events.record_event(
                vault_root=vault_root,
                provider="antigravity",
                event_type="session_end",
                session_id="sess-merge",
                context="Thread güncelleme oturumu.",
                threads=[
                    {"title": "Thread Alpha", "status": "completed"},
                    {"title": "Thread Gamma", "status": "active", "summary": "Gamma detayları."},
                ],
            )

            self.events.project_companion(vault_root)

            threads_doc = (companion / "Threads.md").read_text(encoding="utf-8")
            # Thread Alpha should now be under completed
            self.assertIn("## Tamamlananlar", threads_doc)
            alpha_pos = threads_doc.find("Thread: Thread Alpha")
            completed_pos = threads_doc.find("## Tamamlananlar")
            self.assertGreater(alpha_pos, completed_pos)

            # Thread Beta should still be preserved under active
            self.assertIn("Thread: Thread Beta", threads_doc)
            self.assertIn("Beta detayları.", threads_doc)

            # Thread Gamma should be under active
            self.assertIn("Thread: Thread Gamma", threads_doc)
            self.assertIn("Gamma detayları.", threads_doc)

    def test_project_companion_protection_gate_prevents_erasing_non_empty_threads(self):
        """Protection gate must prevent erasing existing Threads.md when thread_map is empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)

            unparsed_custom_content = """# Custom Freeform Threads Document
Bu dosya elle düzenlenmiş özel bir nottur ve kaybolmamalıdır.
Sadece serbest metinler ve açıklamalar içerir.
"""
            (companion / "Threads.md").write_text(unparsed_custom_content, encoding="utf-8")

            # Record event without threads
            self.events.record_event(
                vault_root=vault_root,
                provider="antigravity",
                event_type="session_end",
                session_id="sess-gate",
                context="Oturum",
                threads=[],
            )

            self.events.project_companion(vault_root)

            threads_doc = (companion / "Threads.md").read_text(encoding="utf-8")
            self.assertIn("Custom Freeform Threads Document", threads_doc)
            self.assertIn("Bu dosya elle düzenlenmiş özel bir nottur", threads_doc)

    def test_parse_threads_markdown_ignores_code_blocks(self):
        """Threads inside markdown code fences must be ignored."""
        content = """# Threads
## Açık Konular
### Thread: Gerçek Thread
**Status:** active
Gerçek içerik.

```markdown
### Thread: Sahte Thread
**Status:** active
Bu bir koddur ve thread olarak algılanmamalıdır.
```
"""
        parsed = self.events.parse_threads_markdown(content)
        self.assertIn("Gerçek Thread", parsed)
        self.assertNotIn("Sahte Thread", parsed)

    def test_rotate_events_boundary_limits(self):
        """rotate_events must safely clamp keep_limit <= 0 to at least 1."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)
            import datetime as dt

            for i in range(3):
                self.events.record_event(
                    vault_root=vault_root,
                    provider="antigravity",
                    event_type="session_end",
                    session_id=f"sess-b-{i}",
                    now=dt.datetime(2026, 9, 1, 10, i, 0, tzinfo=dt.timezone.utc),
                )

            # Rotate with keep_limit=0 should clamp to 1
            archived = self.events.rotate_events(vault_root, keep_limit=0)
            events_dir = companion / "events"
            active_files = [p for p in events_dir.iterdir() if p.is_file() and p.suffix == ".json"]
            self.assertEqual(len(active_files), 1)
            self.assertEqual(len(archived), 2)


FLUSH_PATH = ROOT / "template/.beyin/engine/flush.py"


def load_flush_module():
    spec = importlib.util.spec_from_file_location("flush_module", FLUSH_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FlushThreadsIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.flush = load_flush_module()
        self.events = load_events_module()

    def test_flush_extract_session_threads_preserves_and_discovers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)
            (vault_root / ".beyin").mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(EVENTS_PATH, vault_root / ".beyin" / "events.py")

            existing = """# Threads
## Açık Konular
### Thread: Mevcut İş
**Status:** active
Açıklama.
"""
            (companion / "Threads.md").write_text(existing, encoding="utf-8")

            sections = {
                "Bağlam": "Respected Brain v0.0.1 geliştirmeleri.",
                "Yapılacaklar": "- [ ] Testleri tamamla.\n- Thread: Yeni Keşfedilen İş\n- [x] Thread: Tamamlanan Eski İş",
            }
            threads = self.flush._extract_session_threads(sections, vault_root)
            thread_titles = {t["title"]: t["status"] for t in threads}

            self.assertIn("Mevcut İş", thread_titles)
            self.assertEqual(thread_titles["Mevcut İş"], "active")

            self.assertIn("Yeni Keşfedilen İş", thread_titles)
            self.assertEqual(thread_titles["Yeni Keşfedilen İş"], "active")

            self.assertIn("Tamamlanan Eski İş", thread_titles)
            self.assertEqual(thread_titles["Tamamlanan Eski İş"], "completed")

    def test_flush_record_session_event_passes_populated_threads(self):
        import datetime as dt
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            companion = vault_root / "🔮 850-Companion"
            companion.mkdir(parents=True, exist_ok=True)
            (vault_root / ".beyin").mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(EVENTS_PATH, vault_root / ".beyin" / "events.py")

            existing = """# Threads
## Açık Konular
### Thread: Public Release
**Status:** active
0.0.1 sürümü.
"""
            (companion / "Threads.md").write_text(existing, encoding="utf-8")

            summary = """## Bağlam
Sürüm hazırlığı yapıldı.
## Önemli Konuşmalar
Konuşuldu.
## Alınan Kararlar
- Karar verildi.
## Öğrenilenler
- Bilgi edinildi.
## Yapılacaklar
- İşler listelendi.
"""
            now = dt.datetime.now(dt.timezone.utc)
            self.flush._record_session_event(
                vault_root=vault_root,
                summary=summary,
                reason="session_end",
                event_time=now,
                session_id="sess-flush-test",
            )

            # Verify event JSON has non-empty threads
            events = self.events.list_events(vault_root)
            self.assertEqual(len(events), 1)
            event_threads = events[0].get("threads", [])
            self.assertTrue(len(event_threads) > 0)
            self.assertEqual(event_threads[0]["title"], "Public Release")

            # Verify Threads.md was NOT wiped out!
            threads_doc = (companion / "Threads.md").read_text(encoding="utf-8")
            self.assertIn("Public Release", threads_doc)
            self.assertNotIn("Aktif konu bulunmuyor.", threads_doc)


if __name__ == "__main__":
    unittest.main()
