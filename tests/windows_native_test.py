#!/usr/bin/env python3
"""Real-process checks for the Windows-native Respot profile."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "native Windows only")
class WindowsNativeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respot-native-")
        self.vault = Path(self.temporary.name) / "Ada Brain"
        shutil.copytree(ROOT / "template", self.vault)
        subprocess.run(
            [
                sys.executable,
                str(self.vault / "scripts/render_integrations.py"),
                "--root",
                str(self.vault),
                "--platform",
                "windows-native",
            ],
            check=True,
            text=True,
        )
        self.state = self.vault / ".claude/scripts/.state"
        self.state.mkdir(parents=True, exist_ok=True)
        self._write_memory()
        self._write_flush_recorder()

    def tearDown(self):
        self.temporary.cleanup()

    def _write_memory(self):
        memory = self.vault / "🔮 850-Companion"
        memory.mkdir(parents=True, exist_ok=True)
        (memory / "Last-Session.md").write_text(
            "## Session: Native\nİlk provider kararı.\n## Previous Sessions\n",
            encoding="utf-8",
        )
        (memory / "Threads.md").write_text("## Active\n### Native\n", encoding="utf-8")
        (memory / "Kurallar.md").write_text("# Kurallar\n- Ortak.\n", encoding="utf-8")
        (memory / "Journal.md").write_text("# Journal\n", encoding="utf-8")
        (self.vault / "knowledge").mkdir(exist_ok=True)
        (self.vault / "daily").mkdir(exist_ok=True)
        (self.vault / "knowledge/index.md").write_text("# Index\n", encoding="utf-8")

    def _write_flush_recorder(self):
        recorder = self.vault / ".claude/scripts/flush.py"
        recorder.write_text(
            """import json, os, sys
from pathlib import Path
state = Path(__file__).parent / '.state'
payload = {'argv': sys.argv[1:], 'provider': os.environ.get('BEYIN_PROVIDER')}
if '--hook-input' in sys.argv:
    source = Path(sys.argv[sys.argv.index('--hook-input') + 1])
    payload['hook'] = json.loads(source.read_text(encoding='utf-8'))
    source.unlink()
with (state / 'native-flush.jsonl').open('a', encoding='utf-8') as handle:
    handle.write(json.dumps(payload) + '\\n')
""",
            encoding="utf-8",
        )

    def _bridge(self, provider: str, event: str, payload: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(self.vault / ".beyin/hooks/bridge.py"),
                "--provider",
                provider,
                "--event",
                event,
            ],
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=self.vault,
            check=False,
        )

    def _wait_for_flush(self, count: int = 1) -> list[dict]:
        path = self.state / "native-flush.jsonl"
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if path.exists():
                records = [json.loads(line) for line in path.read_text().splitlines()]
                if len(records) >= count:
                    return records
            time.sleep(0.05)
        self.fail("detached native flush did not finish")

    def test_all_provider_manifests_use_native_absolute_commands(self):
        paths = (
            self.vault / ".claude/settings.json",
            self.vault / ".codex/hooks.json",
            self.vault / ".cursor/hooks.json",
            self.vault / ".agents/hooks.json",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for provider in ("claude", "codex", "cursor", "antigravity"):
            self.assertIn(f"--provider {provider}", combined)
        self.assertIn("py.exe -3", combined)
        self.assertIn("Ada Brain", combined)
        for forbidden in ("wsl.exe", ".sh", "bash"):
            self.assertNotIn(forbidden, combined.lower())

    def test_start_prompt_end_and_precompact_run_in_separate_processes(self):
        started = self._bridge("codex", "start", {"session_id": "native"})
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.assertIn("İlk provider kararı.", started.stdout)

        def prompt(_index: int) -> int:
            return self._bridge("cursor", "prompt", {"session_id": "native"}).returncode

        with ThreadPoolExecutor(max_workers=12) as pool:
            self.assertEqual(list(pool.map(prompt, range(30))), [0] * 30)
        counters = [path for path in self.state.glob("prompt_count.*") if not path.name.endswith(".lock")]
        self.assertEqual(len(counters), 1)
        self.assertEqual(counters[0].read_text(encoding="utf-8").strip(), "30")

        compacted = self._bridge("claude", "precompact", {"session_id": "native"})
        self.assertEqual(compacted.returncode, 0, compacted.stdout + compacted.stderr)
        transcript = self.vault / "native-transcript.jsonl"
        transcript.write_text('{"role":"user","content":"native"}\n', encoding="utf-8")
        ended = self._bridge(
            "antigravity",
            "end",
            {"session_id": "native", "transcript_path": str(transcript)},
        )
        self.assertEqual(ended.returncode, 0, ended.stdout + ended.stderr)
        records = self._wait_for_flush(3)
        self.assertEqual(records[-1]["provider"], "antigravity")
        self.assertFalse(any(self.state.glob("hookin-*.json")))

    def test_provider_first_retryable_failure_uses_the_next_real_cli_stub(self):
        bin_dir = Path(self.temporary.name) / "bin"
        bin_dir.mkdir()
        log = Path(self.temporary.name) / "provider-order.txt"
        (bin_dir / "codex.cmd").write_text(
            '@echo off\r\necho codex>>"%RESPOT_STUB_LOG%"\r\necho 429 quota exceeded 1>&2\r\nexit /b 1\r\n',
            encoding="utf-8",
        )
        (bin_dir / "cursor-agent.cmd").write_text(
            '@echo off\r\necho cursor>>"%RESPOT_STUB_LOG%"\r\necho fallback-summary\r\nexit /b 0\r\n',
            encoding="utf-8",
        )
        module_path = self.vault / ".beyin/model_runner.py"
        spec = importlib.util.spec_from_file_location("native_model_runner", module_path)
        assert spec and spec.loader
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        environment = {
            "PATH": str(bin_dir),
            "RESPOT_STUB_LOG": str(log),
        }

        with mock.patch.dict(os.environ, environment):
            output, error, provider = runner.run_model(
                "native prompt", self.vault, "text", 15, preferred="codex"
            )

        self.assertEqual((output, error, provider), ("fallback-summary", None, "cursor"))
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["codex", "cursor"])

    def test_session_start_catchup_excludes_the_current_day(self):
        (self.vault / "daily/2026-08-28.md").write_text(
            "# Daily\nStill changing.\n", encoding="utf-8"
        )
        environment = os.environ.copy()
        environment["BEYIN_FAKE_NOW"] = "2026-08-28T23:00:00+03:00"

        result = subprocess.run(
            [sys.executable, str(self.vault / ".claude/scripts/flush.py"), "--maybe-compile"],
            cwd=self.vault,
            env=environment,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any(self.state.glob("compile-trigger-*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
