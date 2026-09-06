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


if __name__ == "__main__":
    unittest.main()
