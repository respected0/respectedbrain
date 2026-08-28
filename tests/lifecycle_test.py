#!/usr/bin/env python3
"""Behavior parity tests for the provider-neutral lifecycle core."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_PATH = ROOT / "template" / ".beyin" / "hooks" / "lifecycle.py"
FIXED_NOW = datetime(2026, 8, 28, 20, 15)


def load_lifecycle():
    spec = importlib.util.spec_from_file_location("respot_lifecycle", LIFECYCLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load lifecycle module: {LIFECYCLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LIFECYCLE = load_lifecycle()


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.vault = Path(self.temporary.name) / "Ada Brain"
        self.state = self.vault / ".claude" / "scripts" / ".state"
        self.memory = self.vault / "🔮 850-Companion"
        self.state.mkdir(parents=True)
        self.memory.mkdir(parents=True)
        (self.vault / "knowledge").mkdir()
        (self.vault / "daily").mkdir()
        self._write_fixture_memory()
        self._write_flush_recorder()

    def tearDown(self):
        self.temporary.cleanup()

    def _write_fixture_memory(self):
        (self.memory / "Last-Session.md").write_text(
            "# Last Session\n## Session: Current\nSon karar.\n## Previous Sessions\nEski.\n",
            encoding="utf-8",
        )
        (self.memory / "Threads.md").write_text(
            "# Threads\n## Active\n### Native Windows\n**Status:** In progress\n"
            "## Closed\n### Old\n**Status:** Done\n",
            encoding="utf-8",
        )
        (self.memory / "Kurallar.md").write_text("# Kurallar\n- Tek kaynak.\n", encoding="utf-8")
        (self.memory / "Journal.md").write_text(
            "# Journal\n## 2026-08-27\nEski kayıt.\n## 2026-08-28\nYeni kayıt.\n",
            encoding="utf-8",
        )
        (self.vault / "knowledge" / "index.md").write_text(
            "# Knowledge\n- Respot\n", encoding="utf-8"
        )
        (self.vault / "daily" / "2026-08-28.md").write_text(
            "# Daily\nBugünün girdisi.\n", encoding="utf-8"
        )

    def _write_flush_recorder(self):
        script = self.vault / ".claude" / "scripts" / "flush.py"
        script.write_text(
            """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

state = Path(__file__).parent / ".state"
record = {"argv": sys.argv[1:], "provider": os.environ.get("BEYIN_PROVIDER")}
if "--hook-input" in sys.argv:
    source = Path(sys.argv[sys.argv.index("--hook-input") + 1])
    record["payload"] = json.loads(source.read_text(encoding="utf-8"))
    source.unlink()
with (state / "flush-records.jsonl").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\\n")
""",
            encoding="utf-8",
        )

    def _records(self, expected: int = 1):
        path = self.state / "flush-records.jsonl"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if path.exists():
                lines = path.read_text(encoding="utf-8").splitlines()
                if len(lines) >= expected:
                    return [json.loads(line) for line in lines]
            time.sleep(0.02)
        self.fail(f"expected {expected} detached flush record(s)")

    def test_start_builds_ordered_context_and_initializes_only_its_session(self):
        context = LIFECYCLE.handle("start", {"session_id": "s1"}, self.vault, "codex", FIXED_NOW)

        self.assertEqual(
            [line for line in context.splitlines() if line.startswith("[") and line.endswith("]")],
            [
                "[Hafıza: Son Oturum]",
                "[Hafıza: Aktif Konular]",
                "[Hafıza: Kurallar]",
                "[Hafıza: Son Journal]",
                "[Bilgi Tabanı: İndeks]",
                "[Bugünün Logu]",
            ],
        )
        self.assertLessEqual(len(context), 16_000)
        key = LIFECYCLE.session_key("s1")
        self.assertEqual((self.state / f"prompt_count.{key}").read_text().strip(), "0")
        self.assertEqual(
            (self.state / f"session_start_time.{key}").read_text().strip(),
            str(int(FIXED_NOW.timestamp())),
        )
        self.assertEqual(self._records()[0]["argv"], ["--maybe-compile"])

    def test_start_caps_large_context_without_losing_protected_sections(self):
        (self.memory / "Last-Session.md").write_text(
            "## Session: Current\n" + ("L" * 8_000) + "\n## Previous Sessions\n",
            encoding="utf-8",
        )
        (self.memory / "Kurallar.md").write_text("K" * 8_000, encoding="utf-8")
        (self.vault / "knowledge" / "index.md").write_text("I" * 20_000, encoding="utf-8")

        context = LIFECYCLE.handle("start", {"session_id": "large"}, self.vault, "claude", FIXED_NOW)

        self.assertLessEqual(len(context), 16_000)
        self.assertIn("[Hafıza: Son Oturum]", context)
        self.assertIn("[Hafıza: Kurallar]", context)
        self.assertIn("[not: son oturum 4.000 karakterde kırpıldı", context)
        self.assertIn("[not: kurallar 4.000 karakterde kırpıldı", context)
        self.assertEqual(self._records()[0]["argv"], ["--maybe-compile"])

    def test_prompt_nudges_on_each_fifteenth_message(self):
        payload = {"session_id": "counted"}
        for _ in range(14):
            self.assertEqual(LIFECYCLE.handle("prompt", payload, self.vault, "antigravity"), "")
        self.assertEqual(
            LIFECYCLE.handle("prompt", payload, self.vault, "antigravity"),
            "[Hafıza] 15. mesaj. Oturum sonunda 🔮 850-Companion/Last-Session.md ve Threads.md güncellemeyi unutma.",
        )
        for _ in range(14):
            self.assertEqual(LIFECYCLE.handle("prompt", payload, self.vault, "antigravity"), "")
        self.assertIn("30. mesaj", LIFECYCLE.handle("prompt", payload, self.vault, "antigravity"))

    def test_concurrent_prompts_are_not_lost(self):
        payload = {"session_id": "parallel"}
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(lambda _: LIFECYCLE.handle("prompt", payload, self.vault, "cursor"), range(100)))
        key = LIFECYCLE.session_key("parallel")
        self.assertEqual((self.state / f"prompt_count.{key}").read_text().strip(), "100")

    def test_end_marks_reflection_and_preserves_other_session_state(self):
        ended = LIFECYCLE.session_key("ended")
        live = LIFECYCLE.session_key("live")
        (self.state / f"session_start_time.{ended}").write_text("2000000000\n", encoding="utf-8")
        (self.state / f"prompt_count.{ended}").write_text("5\n", encoding="utf-8")
        (self.state / f"session_start_time.{live}").write_text("2000000001\n", encoding="utf-8")
        (self.state / f"prompt_count.{live}").write_text("3\n", encoding="utf-8")
        transcript = self.vault / "transcript.jsonl"
        transcript.write_text('{"role":"user","content":"hello"}\n', encoding="utf-8")
        os.utime(self.memory / "Last-Session.md", (1_900_000_000, 1_900_000_000))

        output = LIFECYCLE.handle(
            "end",
            {"session_id": "ended", "transcript_path": str(transcript)},
            self.vault,
            "codex",
            FIXED_NOW,
        )

        self.assertEqual(output, "")
        self.assertTrue((self.state / f"needs_reflection.{ended}").exists())
        self.assertFalse((self.state / f"session_start_time.{ended}").exists())
        self.assertFalse((self.state / f"prompt_count.{ended}").exists())
        self.assertTrue((self.state / f"prompt_count.{live}").exists())
        record = self._records()[0]
        self.assertEqual(record["provider"], "codex")
        self.assertEqual(record["payload"]["session_id"], "ended")
        self.assertNotIn("--reason", record["argv"])
        self.assertFalse(any(self.state.glob("hookin-*.json")))

    def test_precompact_flushes_without_changing_live_session(self):
        key = LIFECYCLE.session_key("live")
        (self.state / f"session_start_time.{key}").write_text("2000000000\n", encoding="utf-8")
        (self.state / f"prompt_count.{key}").write_text("9\n", encoding="utf-8")

        output = LIFECYCLE.handle(
            "precompact", {"session_id": "live", "trigger": "manual"}, self.vault, "claude", FIXED_NOW
        )

        self.assertEqual(output, "")
        self.assertEqual((self.state / f"prompt_count.{key}").read_text().strip(), "9")
        self.assertFalse((self.state / f"needs_reflection.{key}").exists())
        record = self._records()[0]
        self.assertEqual(record["argv"][-2:], ["--reason", "precompact"])
        self.assertEqual(record["payload"]["trigger"], "manual")

    def test_invalid_payload_records_health_and_has_no_lifecycle_effect(self):
        output = LIFECYCLE.handle("start", {"session_id": ""}, self.vault, "codex", FIXED_NOW)

        self.assertEqual(output, "")
        health = json.loads((self.state / "health.json").read_text(encoding="utf-8"))
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["event"], "start")
        self.assertFalse(any(self.state.glob("prompt_count.*")))


if __name__ == "__main__":
    unittest.main()
