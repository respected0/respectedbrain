#!/usr/bin/env python3
"""Behavior tests for the provider-neutral morning briefing worker."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


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
    from respectedbrain.briefing import service
    from respectedbrain.core.context import ModelResult
    from tests.foundation_support import make_context
    from types import SimpleNamespace

    def run(vault, now, model_call):
        ctx = make_context(vault.parent, vault)
        called = []
        class Model:
            def run(self, prompt, *, cwd, mode, timeout):
                called.append(True)
                text, error, provider = model_call(prompt, cwd)
                return ModelResult(text, provider, error)
        return service.run_if_due(ctx, model=Model(), now=now) == 0 and bool(called)
    return SimpleNamespace(**{**vars(service), "run_if_due": run})


class MorningBriefingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respected-briefing-")
        self.vault = Path(self.temporary.name).resolve() / "Ada Brain"
        from respectedbrain.briefing import service
        from tests.foundation_support import make_context
        self.ctx = make_context(Path(self.temporary.name).resolve(), self.vault)
        self.compiler = patch.object(service, "compile_memory", return_value=0)
        self.compiler.start()
        self.addCleanup(self.compiler.stop)
        for relative in (
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

    def test_model_stage_uses_selected_uuid_cache(self):
        calls = []
        load_worker().run_if_due(self.vault, datetime(2026, 8, 31, 9),
                                lambda prompt, cwd: (calls.append(cwd) or VALID, None, "codex"))
        self.assertEqual(calls[0].parent, self.ctx.paths.cache_dir)
        self.assertFalse(calls[0].exists())

    def test_linked_cache_is_rejected_before_model_or_compilation(self):
        from respectedbrain.briefing import service
        from respectedbrain.core.context import ModelResult
        outside = Path(self.temporary.name) / "outside-cache"
        outside.mkdir()
        cache = self.ctx.paths.cache_dir
        cache.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            result = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(cache), str(outside)],
                                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            cache.symlink_to(outside, target_is_directory=True)
        calls = []
        class Model:
            def run(self, prompt, *, cwd, mode, timeout):
                calls.append(cwd)
                return ModelResult(VALID, "custom", None)
        try:
            compile_marker = Path(self.temporary.name) / "compiled"
            def compile_probe(*args, **kwargs):
                compile_marker.touch()
                return 0
            with patch.object(service, "compile_memory", side_effect=compile_probe):
                status = service.run_if_due(self.ctx, model=Model(), now=datetime(2026, 8, 31, 9))
            self.assertEqual(status, 1)
            self.assertFalse(compile_marker.exists())
            self.assertEqual(calls, [])
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((self.vault / "🎯 100-Command-Center/Briefings/2026-08-31.md").exists())
        finally:
            if os.name == "nt":
                cache.rmdir()
            else:
                cache.unlink()

    def test_dashboard_edit_during_staging_is_preserved_on_first_attempt(self):
        from respectedbrain.briefing import service
        dashboard = self.vault / "🎯 100-Command-Center/Dashboard.md"
        user_edit = b"# Dashboard\nUser edit during staging\n"
        original = service.tempfile.mkstemp
        def staging(*args, **kwargs):
            if kwargs.get("prefix") == ".Dashboard.md.":
                dashboard.write_bytes(user_edit)
            return original(*args, **kwargs)
        with patch.object(service.tempfile, "mkstemp", side_effect=staging):
            created = load_worker().run_if_due(self.vault, datetime(2026, 8, 31, 9),
                                             lambda prompt, cwd: (VALID, None, "codex"))
        self.assertEqual(dashboard.read_bytes(), user_edit)
        self.assertFalse(created)
        self.assertFalse((self.vault / "🎯 100-Command-Center/Briefings/2026-08-31.md").exists())
        self.assertEqual(list(dashboard.parent.glob(".*.tmp")), [])

    def test_briefing_created_during_model_run_is_preserved(self):
        final = self.vault / "🎯 100-Command-Center/Briefings/2026-08-31.md"
        user_note = b"# User briefing\nDo not replace\n"
        def model(prompt, cwd):
            final.parent.mkdir(parents=True, exist_ok=True)
            final.write_bytes(user_note)
            return VALID, None, "codex"
        created = load_worker().run_if_due(self.vault, datetime(2026, 8, 31, 9), model)
        self.assertEqual(final.read_bytes(), user_note)
        self.assertFalse(created)

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
        self.assertFalse((self.ctx.paths.state_dir / "briefing-health.json").exists())

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

    def test_windows_sharing_retry_publishes_without_running_model_again(self):
        self._sharing_failure_case('transient')

    def test_persistent_windows_sharing_failure_preserves_dashboard(self):
        self._sharing_failure_case('persistent')

    def test_windows_sharing_retry_aborts_on_concurrent_dashboard_edit(self):
        self._sharing_failure_case('user-edit')

    def test_windows_share_violation_retries_prepared_bytes(self):
        self._sharing_failure_case('transient', winerror=32)

    def test_unrelated_or_non_windows_replace_errors_are_not_retried(self):
        for platform, code in (('linux', 5), ('win32', 87)):
            with self.subTest(platform=platform, code=code):
                self._sharing_failure_case('no-retry', platform=platform, winerror=code)

    def _sharing_failure_case(self, variant, *, platform='win32', winerror=5):
        from respectedbrain.briefing import service
        worker = load_worker()
        dashboard = self.vault / '🎯 100-Command-Center/Dashboard.md'
        before = dashboard.read_bytes()
        final = self.vault / '🎯 100-Command-Center/Briefings/2026-08-31.md'
        user_edit = b'# Dashboard\nConcurrent user edit\n'
        original = service.os.replace
        calls, attempts = [], []
        def replacing(source, target):
            if Path(target) == dashboard:
                attempts.append(True)
                if len(attempts) == 1 or variant == 'persistent':
                    if variant == 'user-edit':
                        dashboard.write_bytes(user_edit)
                    error = PermissionError('synthetic Windows sharing failure')
                    error.winerror = winerror
                    raise error
            return original(source, target)
        with patch.object(service.sys, 'platform', platform), patch.object(service.os, 'replace', side_effect=replacing):
            created = worker.run_if_due(self.vault, datetime(2026, 8, 31, 10),
                                      lambda prompt, cwd: (calls.append(True) or VALID, None, 'codex'))
        self.assertEqual(len(calls), 1)
        if variant == 'transient':
            self.assertTrue(created)
            self.assertEqual(len(attempts), 2)
            self.assertTrue(final.is_file())
            self.assertIn('Kullanıcı içeriği.', dashboard.read_text(encoding='utf-8'))
        else:
            self.assertFalse(created)
            self.assertFalse(final.exists())
            self.assertEqual(dashboard.read_bytes(), user_edit if variant == 'user-edit' else before)
            self.assertLessEqual(len(attempts), 5, 'Sharing retries must remain finite')
            self.assertEqual(len(attempts), 5 if variant == 'persistent' else 1)

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
        self.ctx.paths.state_dir.mkdir(parents=True, exist_ok=True)
        lock = self.ctx.paths.state_dir / "morning-briefing-2026-08-31.lock"
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
