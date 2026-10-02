#!/usr/bin/env python3
"""Adversarial tests for durable per-turn daily logging."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BEYIN = ROOT / "runtime" if (ROOT / "runtime").is_dir() else ROOT / "template/.beyin"
if str(BEYIN) not in sys.path:
    sys.path.insert(0, str(BEYIN))
if str(BEYIN / "hooks") not in sys.path:
    sys.path.insert(0, str(BEYIN / "hooks"))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FLUSH = load("turn_pipeline_flush", BEYIN / "engine/flush.py")
LIFECYCLE = load("turn_pipeline_lifecycle", BEYIN / "hooks/lifecycle.py")
CODEX_NOTIFY = load("turn_pipeline_codex_notify", BEYIN / "hooks/codex_notify.py")


class TurnLogPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="turn-log-")
        self.vault = Path(self.temporary.name) / "Furkan'ın 🧠 Brain"
        self.state = self.vault / ".beyin/engine/.state"
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
spec = importlib.util.spec_from_file_location('process_flush_' + sys.argv[4], sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module._upsert_daily_session(
    pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]),
    '## Baglam\\nProcess ' + sys.argv[4], 'turn',
    dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc),
    'process-' + sys.argv[4], 'codex')
"""

        def run(index: int) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable,
                    "-c",
                    worker,
                    str(BEYIN / "engine/flush.py"),
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
                self.vault, self.state, newer, "same-session", "turn", base
            )
            second = FLUSH._flush_session_transcript(
                self.vault, self.state, older, "same-session", "turn", base - dt.timedelta(seconds=1)
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
            LIFECYCLE.handle("turn", payload, self.vault, "codex")

        self.assertTrue(start_file.exists())
        self.assertTrue(prompt_file.exists())
        self.assertEqual(launch.call_args.kwargs["reason"], "turn")

    def test_codex_notify_creates_hook_input_and_launches_detached_flush(self):
        hook_dir = self.vault / ".beyin/hooks"
        engine = self.vault / ".beyin/engine"
        hook_dir.mkdir(parents=True)
        engine.mkdir(parents=True, exist_ok=True)
        transcript = self.vault / "codex-session.jsonl"
        transcript.write_text('{}\n', encoding="utf-8")
        (engine / "flush.py").write_text("# test worker\n", encoding="utf-8")
        fake_bridge = types.SimpleNamespace(
            resolve_codex_transcript=lambda _session_id: str(transcript)
        )

        with (
            mock.patch.object(CODEX_NOTIFY, "__file__", str(hook_dir / "codex_notify.py")),
            mock.patch.object(CODEX_NOTIFY, "_forward_chained"),
            mock.patch.object(CODEX_NOTIFY.sys, "argv", [
                "codex_notify.py",
                '{"type":"agent-turn-complete","thread-id":"thread-123","cwd":"C:/work"}',
            ]),
            mock.patch.dict(sys.modules, {"bridge": fake_bridge}),
            mock.patch.object(CODEX_NOTIFY.subprocess, "Popen") as popen,
        ):
            result = CODEX_NOTIFY.main()

        self.assertEqual(result, 0)
        hook_inputs = list((engine / ".state").glob("hookin-*.json"))
        self.assertEqual(len(hook_inputs), 1)
        self.assertIn('"session_id": "thread-123"', hook_inputs[0].read_text(encoding="utf-8"))
        popen.assert_called_once()
        self.assertIn("--hook-input", popen.call_args.args[0])
        self.assertEqual(popen.call_args.args[0][-2:], ["--reason", "turn"])

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
                self.vault,
                self.state,
                now=now,
                home=home,
            )

        self.assertEqual(count, 1)
        flush.assert_called_once()


if __name__ == "__main__":
    unittest.main()
