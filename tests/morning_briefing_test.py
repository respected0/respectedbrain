#!/usr/bin/env python3
"""Behavior tests for the provider-neutral morning briefing worker."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "template/.beyin/morning_briefing.py"
VALID = """## Dün tamamlananlar
- Derleyici düzeldi.
## Açık işler
- Haritaları bitir.
## Devam eden projeler
- Respected Brain.
## Bugünün öncelikleri
1. Testleri çalıştır.
## Unutulmaması gerekenler
- Provider-neutral kal.
"""


def load_worker():
    spec = importlib.util.spec_from_file_location("respected_morning_briefing", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("morning briefing worker cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MorningBriefingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respected-briefing-")
        self.vault = Path(self.temporary.name) / "Ada Brain"
        for relative in (
            ".beyin",
            ".claude/scripts/.state",
            "daily",
            "knowledge",
            "🎯 100-Command-Center",
            "🔮 850-Companion",
        ):
            (self.vault / relative).mkdir(parents=True, exist_ok=True)
        (self.vault / "daily/2026-08-30.md").write_text("# Dün\nTamamlandı.\n", encoding="utf-8")
        (self.vault / "knowledge/index.md").write_text("# Index\nRespected\n", encoding="utf-8")
        (self.vault / "🎯 100-Command-Center/Dashboard.md").write_text(
            "# Dashboard\n\nKullanıcı içeriği.\n", encoding="utf-8"
        )
        (self.vault / "🎯 100-Command-Center/Vault-Map.md").write_text(
            "# Vault Map\n- Respected\n", encoding="utf-8"
        )
        (self.vault / "🔮 850-Companion/Threads.md").write_text(
            "## Active\n### Respected\n", encoding="utf-8"
        )
        (self.vault / "🔮 850-Companion/Last-Session.md").write_text(
            "## Session: Current\nPlan onaylandı.\n", encoding="utf-8"
        )
        (self.vault / "🔮 850-Companion/Journal.md").write_text(
            "# Journal\n## 2026-08-30\nKarar.\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_before_eight_is_a_read_only_noop(self):
        worker = load_worker()
        calls = []

        created = worker.run_if_due(
            self.vault,
            datetime.fromisoformat("2026-08-31T07:59:00+03:00"),
            lambda prompt, cwd: calls.append((prompt, cwd)),
        )

        self.assertFalse(created)
        self.assertEqual(calls, [])
        self.assertFalse((self.vault / "🎯 100-Command-Center/Briefings").exists())

    def test_success_writes_real_time_required_sections_and_preserves_dashboard(self):
        worker = load_worker()
        calls = []

        def model(prompt, cwd):
            calls.append((prompt, cwd))
            return VALID, None, "codex"

        created = worker.run_if_due(
            self.vault,
            datetime.fromisoformat("2026-08-31T09:17:00+03:00"),
            model,
        )

        self.assertTrue(created)
        briefing = self.vault / "🎯 100-Command-Center/Briefings/2026-08-31.md"
        body = briefing.read_text(encoding="utf-8")
        self.assertIn("prepared_at: 2026-08-31T09:17:00+03:00", body)
        self.assertIn(VALID.strip(), body)
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(calls[0][1], self.vault)
        dashboard = (self.vault / "🎯 100-Command-Center/Dashboard.md").read_text(encoding="utf-8")
        self.assertIn("Kullanıcı içeriği.", dashboard)
        self.assertIn("[[Briefings/2026-08-31|Bugünün Brifingi]]", dashboard)

    def test_temporary_directory_uses_external_temp_parent_when_present(self):
        worker = load_worker()
        target = self.vault / "external-temp"
        with patch.object(
            worker.runtime_platform, "external_temp_parent", return_value=target
        ):
            kwargs = worker._temporary_directory_kwargs(self.vault)
        self.assertEqual(kwargs, {"dir": target})
        self.assertTrue(target.is_dir())

    def test_success_replaces_one_legacy_dashboard_block_with_current_markers(self):
        worker = load_worker()
        old_upper = "RES" + "POT"
        old_begin = "<!-- " + old_upper + "-BRIEFING:BEGIN -->"
        old_end = "<!-- " + old_upper + "-BRIEFING:END -->"
        dashboard_path = self.vault / "🎯 100-Command-Center/Dashboard.md"
        dashboard_path.write_text(
            "# Dashboard\n\nKullanıcı içeriği.\n\n"
            + old_begin
            + "\n## Bugünün Brifingi\n\n[[Briefings/2026-08-30|Dün]]\n"
            + old_end
            + "\n",
            encoding="utf-8",
        )

        created = worker.run_if_due(
            self.vault,
            datetime.fromisoformat("2026-08-31T09:17:00+03:00"),
            lambda _prompt, _cwd: (VALID, None, "codex"),
        )

        self.assertTrue(created)
        dashboard = dashboard_path.read_text(encoding="utf-8")
        self.assertIn("Kullanıcı içeriği.", dashboard)
        self.assertEqual(dashboard.count("<!-- RESPECTED-BRIEFING:BEGIN -->"), 1)
        self.assertEqual(dashboard.count("<!-- RESPECTED-BRIEFING:END -->"), 1)
        self.assertNotIn(old_begin, dashboard)
        self.assertNotIn(old_end, dashboard)

    def test_failure_leaves_no_final_and_can_retry_same_day(self):
        worker = load_worker()
        now = datetime.fromisoformat("2026-08-31T10:00:00+03:00")

        self.assertFalse(
            worker.run_if_due(self.vault, now, lambda prompt, cwd: (None, "codex-exit-1", "codex"))
        )
        self.assertFalse((self.vault / "🎯 100-Command-Center/Briefings/2026-08-31.md").exists())
        self.assertTrue(
            worker.run_if_due(self.vault, now, lambda prompt, cwd: (VALID, None, "cursor"))
        )
        self.assertFalse((self.vault / ".claude/scripts/.state/briefing-health.json").exists())

    def test_concurrent_runs_make_one_model_call_and_one_final(self):
        worker = load_worker()
        now = datetime.fromisoformat("2026-08-31T10:00:00+03:00")
        call_count = 0
        guard = threading.Lock()

        def model(prompt, cwd):
            nonlocal call_count
            with guard:
                call_count += 1
            return VALID, None, "claude"

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: worker.run_if_due(self.vault, now, model), range(8)))

        self.assertEqual(call_count, 1)
        self.assertEqual(results.count(True), 1)
        self.assertTrue((self.vault / "🎯 100-Command-Center/Briefings/2026-08-31.md").is_file())

    def test_large_dashboard_is_preserved_without_truncation(self):
        worker = load_worker()
        dashboard = self.vault / "🎯 100-Command-Center/Dashboard.md"
        original = "# Dashboard\n" + ("x" * 1_100_000) + "\nTAIL-MUST-SURVIVE\n"
        dashboard.write_text(original, encoding="utf-8")

        self.assertTrue(
            worker.run_if_due(
                self.vault,
                datetime.fromisoformat("2026-08-31T10:00:00+03:00"),
                lambda prompt, cwd: (VALID, None, "codex"),
            )
        )

        updated = dashboard.read_text(encoding="utf-8")
        self.assertIn("TAIL-MUST-SURVIVE", updated)
        self.assertIn(original, updated)

    def test_undecodable_dashboard_fails_closed_and_preserves_bytes(self):
        worker = load_worker()
        dashboard = self.vault / "🎯 100-Command-Center/Dashboard.md"
        original = b"# Dashboard\n\xff\xfeUSER-DATA\n"
        dashboard.write_bytes(original)

        self.assertFalse(
            worker.run_if_due(
                self.vault,
                datetime.fromisoformat("2026-08-31T10:00:00+03:00"),
                lambda prompt, cwd: (VALID, None, "codex"),
            )
        )

        self.assertEqual(dashboard.read_bytes(), original)
        self.assertFalse((self.vault / "🎯 100-Command-Center/Briefings/2026-08-31.md").exists())

    def test_latest_journal_entry_comes_from_tail(self):
        worker = load_worker()
        journal = self.vault / "🔮 850-Companion/Journal.md"
        journal.write_text(
            "# Journal\n## Eski\n" + ("a" * 13_000) + "\n## En Yeni\nLATEST-JOURNAL\n",
            encoding="utf-8",
        )
        prompts = []

        worker.run_if_due(
            self.vault,
            datetime.fromisoformat("2026-08-31T10:00:00+03:00"),
            lambda prompt, cwd: (prompts.append(prompt) or VALID, None, "codex"),
        )

        self.assertIn("LATEST-JOURNAL", prompts[0])

    def test_journal_tail_recovers_when_offset_splits_multibyte_character(self):
        worker = load_worker()
        journal = self.vault / "🔮 850-Companion/Journal.md"
        latest = b"\n## En Yeni\nUTF8-TAIL\n"
        suffix = (b"a" * (65_535 - len(latest))) + latest
        journal.write_bytes(b"# Journal\n" + "ş".encode("utf-8") + suffix)
        prompts = []

        worker.run_if_due(
            self.vault,
            datetime.fromisoformat("2026-08-31T10:00:00+03:00"),
            lambda prompt, cwd: (prompts.append(prompt) or VALID, None, "codex"),
        )

        self.assertIn("UTF8-TAIL", prompts[0])

    def test_linked_briefings_directory_cannot_redirect_writes(self):
        worker = load_worker()
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        briefings = self.vault / "🎯 100-Command-Center/Briefings"
        try:
            briefings.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlink unavailable: {error}")

        self.assertFalse(
            worker.run_if_due(
                self.vault,
                datetime.fromisoformat("2026-08-31T10:00:00+03:00"),
                lambda prompt, cwd: (VALID, None, "codex"),
            )
        )
        self.assertEqual(list(outside.iterdir()), [])

    def test_linked_daily_lock_cannot_redirect_writes(self):
        worker = load_worker()
        outside = Path(self.temporary.name) / "external-lock"
        outside.write_bytes(b"")
        lock = self.vault / ".claude/scripts/.state/morning-briefing-2026-08-31.lock"
        try:
            lock.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"symlink unavailable: {error}")

        self.assertFalse(
            worker.run_if_due(
                self.vault,
                datetime.fromisoformat("2026-08-31T10:00:00+03:00"),
                lambda prompt, cwd: (VALID, None, "codex"),
            )
        )
        self.assertEqual(outside.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
