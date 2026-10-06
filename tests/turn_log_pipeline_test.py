#!/usr/bin/env python3
"""Adversarial tests for durable per-turn daily logging."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


from respectedbrain.memory import flush as FLUSH
from tests.foundation_memory_test import FakeModel, make_context
from respectedbrain.memory import lifecycle as LIFECYCLE
from respectedbrain.integrations.hooks import codex_notify as CODEX_NOTIFY
from respectedbrain.integrations.hooks import bridge as BRIDGE


class TurnLogPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="turn-log-")
        self.vault = Path(self.temporary.name) / "Furkan'ın 🧠 Brain"
        self.vault.mkdir(parents=True)
        self.ctx = make_context(self.vault)
        self.state = self.ctx.paths.state_dir
        self.state.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def upsert(
        self,
        session_id: str,
        summary: str,
        when: dt.datetime,
        provider: str = "codex",
    ) -> None:
        FLUSH._upsert_daily_session(
            self.vault,
            self.state,
            summary,
            "turn",
            when,
            session_id,
            provider,
        )

    def test_stale_hook_sweep_preserves_persistent_lock_files(self):
        locks = [self.state / name for name in ("writer.lock", "compile.lock", "daily-2026-09-14.lock", "flush-old.lock")]
        for lock in locks:
            lock.write_bytes(b"persistent lock identity")
            os.utime(lock, (1, 1))
        hook = self.state / "hookin-old.json"
        hook.write_text("{}", encoding="utf-8")
        os.utime(hook, (1, 1))
        FLUSH._sweep_stale_hook_inputs(self.state, None, 10_000)
        self.assertFalse(hook.exists())
        for lock in locks:
            self.assertTrue(lock.exists())
            self.assertEqual(lock.read_bytes(), b"persistent lock identity")

    def test_invalid_daily_marker_order_or_duplicate_end_preserves_human_bytes(self):
        identity = hashlib.sha256(b"codex\0session-a").hexdigest()
        begin = f"<!-- RESPECTED-SESSION:{identity}:BEGIN -->"
        end = f"<!-- RESPECTED-SESSION:{identity}:END -->"
        daily = self.vault / "daily/2026-09-14.md"
        daily.parent.mkdir()
        for malformed in (end + "\nHUMAN\n" + begin, begin + "\nHUMAN\n" + end + "\n" + end):
            with self.subTest(malformed=malformed):
                daily.write_text(malformed, encoding="utf-8")
                before = daily.read_bytes()
                with self.assertRaisesRegex(OSError, "daily-session-markers-invalid"):
                    self.upsert("session-a", "## Bağlam\nreplacement", dt.datetime(2026, 9, 14))
                self.assertEqual(daily.read_bytes(), before)

    def test_daily_edit_during_atomic_staging_is_preserved(self):
        daily = self.vault / "daily/2026-09-14.md"
        daily.parent.mkdir()
        daily.write_bytes(b"# Original human daily\n")
        edit = b"# Concurrent human daily\n"
        real_mkstemp = FLUSH.tempfile.mkstemp
        def staging(*args, **kwargs):
            if kwargs.get("prefix") == ".2026-09-14.md.":
                daily.write_bytes(edit)
            return real_mkstemp(*args, **kwargs)
        with mock.patch.object(FLUSH.tempfile, "mkstemp", side_effect=staging):
            with self.assertRaisesRegex(OSError, "daily-target-changed"):
                self.upsert("session-a", "## Bağlam\nreplacement", dt.datetime(2026, 9, 14))
        self.assertEqual(daily.read_bytes(), edit)

    def test_later_turn_replaces_the_same_session_without_touching_human_text(self):
        when = dt.datetime(2026, 9, 14, 3, 4, tzinfo=dt.timezone(dt.timedelta(hours=3)))
        daily = self.vault / "daily/2026-09-14.md"
        daily.parent.mkdir(parents=True)
        daily.write_text("# İnsan günlüğü\n\nBunu koru.\n", encoding="utf-8")

        self.upsert("session-a", "## Bağlam\nİlk turn", when)
        self.upsert("session-a", "## Bağlam\nİkinci turn", when + dt.timedelta(minutes=1))

        content = daily.read_text(encoding="utf-8")
        self.assertIn("# İnsan günlüğü", content)
        self.assertIn("Bunu koru.", content)
        self.assertNotIn("İlk turn", content)
        self.assertEqual(content.count("İkinci turn"), 1)
        self.assertEqual(content.count("### Oturum"), 1)

    def test_two_sessions_survive_concurrent_updates_without_truncation(self):
        when = dt.datetime(2026, 9, 14, 3, 10, tzinfo=dt.timezone.utc)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(
                    self.upsert,
                    f"session-{index}",
                    f"## Bağlam\nOturum içeriği {index}",
                    when + dt.timedelta(seconds=index),
                    "claude" if index % 2 else "codex",
                )
                for index in range(20)
            ]
            for future in futures:
                future.result()

        content = (self.vault / "daily/2026-09-14.md").read_text(encoding="utf-8")
        self.assertEqual(content.count("### Oturum"), 20)
        for index in range(20):
            self.assertEqual(content.count(f"Oturum içeriği {index}\n"), 1)

    def test_twenty_four_processes_share_one_daily_without_lost_updates(self):
        worker = """
import datetime as dt, importlib.util, pathlib, sys
from respectedbrain.memory import flush as module
module._upsert_daily_session(
    pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]),
    '## Baglam\\nProcess ' + sys.argv[3], 'turn',
    dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc),
    'process-' + sys.argv[3], 'codex')
"""

        def run(index: int) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable,
                    "-c",
                    worker,
                    str(self.vault),
                    str(self.state),
                    str(index),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(run, range(24)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        content = (self.vault / "daily/2026-09-14.md").read_text(encoding="utf-8")
        self.assertEqual(content.count("### Oturum"), 24)
        for index in range(24):
            self.assertEqual(content.count(f"Process {index}\n"), 1)

    def test_session_crossing_midnight_writes_each_day_without_stale_overwrite(self):
        before = dt.datetime(2026, 9, 14, 23, 59, tzinfo=dt.timezone.utc)
        after = before + dt.timedelta(minutes=2)

        self.upsert("session-midnight", "## Bağlam\nÖnce", before)
        self.upsert("session-midnight", "## Bağlam\nSonra", after)

        first = (self.vault / "daily/2026-09-14.md").read_text(encoding="utf-8")
        second = (self.vault / "daily/2026-09-15.md").read_text(encoding="utf-8")
        self.assertIn("Önce", first)
        self.assertNotIn("Sonra", first)
        self.assertIn("Sonra", second)

    def test_late_older_revision_cannot_overwrite_newer_session_summary(self):
        newer = self.vault / "newer.jsonl"
        older = self.vault / "older.jsonl"
        newer.write_text(
            '{"role":"user","content":"newer transcript"}\n', encoding="utf-8"
        )
        older.write_text(
            '{"role":"user","content":"older transcript"}\n', encoding="utf-8"
        )
        newer_summary = "## Bağlam\nNEWER\n\n## Önemli Konuşmalar\nN\n\n## Alınan Kararlar\nN\n\n## Öğrenilenler\nN\n\n## Yapılacaklar\nN"
        older_summary = newer_summary.replace("NEWER", "OLDER")
        base = dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc)

        with mock.patch.object(FLUSH, "_run_model", side_effect=[(newer_summary, None), (older_summary, None)]):
            first = FLUSH._flush_session_transcript(
                self.vault, self.state, newer, "same-session", "turn", base, FakeModel(), self.ctx.paths.cache_dir
            )
            second = FLUSH._flush_session_transcript(
                self.vault, self.state, older, "same-session", "turn", base - dt.timedelta(seconds=1), FakeModel(), self.ctx.paths.cache_dir
            )

        content = (self.vault / "daily/2026-09-14.md").read_text(encoding="utf-8")
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertIn("NEWER", content)
        self.assertNotIn("OLDER", content)

    def test_turn_event_launches_flush_with_turn_reason_and_keeps_session_state(self):
        payload = {"session_id": "session-turn", "transcript_path": "/tmp/t.jsonl"}
        start_file = self.state / f"session_start_time.{LIFECYCLE.session_key('session-turn')}"
        prompt_file = self.state / f"prompt_count.{LIFECYCLE.session_key('session-turn')}"
        start_file.write_text("1\n", encoding="utf-8")
        prompt_file.write_text("2\n", encoding="utf-8")

        with mock.patch.object(LIFECYCLE, "_launch_flush", return_value=True) as launch:
            LIFECYCLE.handle_event(self.ctx, event="turn", session_id=payload["session_id"], transcript=Path(payload["transcript_path"]), payload={**payload, "provider":"codex"}, now=dt.datetime.now())

        self.assertTrue(start_file.exists())
        self.assertTrue(prompt_file.exists())
        self.assertEqual(launch.call_args.kwargs["reason"], "turn")

    def test_codex_notify_creates_hook_input_and_launches_detached_flush(self):
        transcript = self.vault / "codex-session.jsonl"
        transcript.write_text('{}\n', encoding="utf-8")
        payload = '{"type":"agent-turn-complete","thread-id":"thread-123","cwd":"C:/work"}'
        with (
            mock.patch.object(CODEX_NOTIFY, "_forward_chained"),
            mock.patch.object(BRIDGE, "resolve_codex_transcript", return_value=str(transcript)),
            mock.patch.object(LIFECYCLE.subprocess, "Popen") as popen,
        ):
            result = CODEX_NOTIFY.dispatch(self.ctx, argv=[payload], stdin="")

        self.assertEqual(result, "")
        hook_inputs = list(self.state.glob("hookin-*.json"))
        self.assertEqual(len(hook_inputs), 1)
        self.assertIn('"session_id": "thread-123"', hook_inputs[0].read_text(encoding="utf-8"))
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertIn("--hook-input", command)
        self.assertIn("--vault-id", command)
        self.assertIn(self.ctx.paths.vault_id, command)
        self.assertEqual(command[-2:], ["--reason", "turn"])
        self.assertFalse((self.vault / ".beyin").exists())

    def test_codex_notify_forwards_exact_persisted_chain_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            chain_file = Path(temporary) / "chain.json"
            chain_file.write_text(
                json.dumps({"argv": ["custom-notify", "turn-ended"]}),
                encoding="utf-8",
            )
            with mock.patch.object(CODEX_NOTIFY.subprocess, "Popen") as popen:
                CODEX_NOTIFY._forward_chained(
                    ["--chain-file", str(chain_file), '{"thread-id":"abc"}']
                )

            self.assertEqual(
                popen.call_args.args[0],
                ["custom-notify", "turn-ended", '{"thread-id":"abc"}'],
            )

    def test_same_turn_count_with_changed_transcript_is_not_a_duplicate(self):
        session_id = "session-rewritten"
        FLUSH._write_flush_state(
            self.state,
            session_id,
            100.0,
            "ok",
            turn_count=2,
            transcript_hash="old-hash",
        )

        self.assertFalse(
            FLUSH._is_recent_duplicate(
                self.state,
                session_id,
                101.0,
                current_turns=2,
                transcript_hash="new-hash",
            )
        )
        self.assertTrue(
            FLUSH._is_recent_duplicate(
                self.state,
                session_id,
                101.0,
                current_turns=2,
                transcript_hash="old-hash",
            )
        )

    def test_catch_up_retries_a_session_whose_previous_flush_failed(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        home = self.vault / "home"
        transcript = home / ".codex/sessions" / f"rollout-{session_id}.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("{}\n", encoding="utf-8")
        now = dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc)
        old = now.timestamp() - 60
        os.utime(transcript, (old, old))
        FLUSH._session_state_path(self.state, session_id).write_text(
            json.dumps({"session_id": session_id, "status": "model-failed", "ts": old}),
            encoding="utf-8",
        )

        with mock.patch.object(FLUSH, "_flush_session_transcript", return_value=True) as flush:
            count = FLUSH.catch_up_unflushed_sessions(
                self.ctx,
                model=FakeModel(),
                now=now,
                home=home,
            )

        self.assertEqual(count, 1)
        flush.assert_called_once()


if __name__ == "__main__":
    unittest.main()
