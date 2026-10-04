"""Windows processes and filesystem protections with explicit package roots."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.core.paths import Roots
from respectedbrain.core.config import ConfigStore
from respectedbrain.vault.registry import build_context
from respectedbrain.integrations.backend import IntegrationProfile
from respectedbrain.integrations.rendering import render_project_integrations
from tests.foundation_support import make_context, snapshot
from tests.foundation_install_support import seed_package
from tests.foundation_transactions_test import Backend

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = "## Bağlam\nNative test\n\n## Önemli Konuşmalar\nWindows süreçleri\n\n## Alınan Kararlar\nPaket kullanıldı\n\n## Öğrenilenler\nAyrı state\n\n## Yapılacaklar\n- Yok\n"

@unittest.skipUnless(os.name == "nt", "native Windows only")
class WindowsNativeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respected-native-")
        self.addCleanup(self._cleanup_process_workspace)
        self.root = Path(self.temporary.name).resolve()
        self.vault = self.root / "Ada 🧠 Brain"
        with ResourceCatalog().materialize("vault-template") as template:
            shutil.copytree(template, self.vault)
        self.ctx = make_context(self.root, self.vault)
        self.state = self.ctx.paths.state_dir
        self.home = self.root / "home"
        self.home.mkdir()
        self.environment = {**os.environ, "RESPECTED_APP_DIR": str(self.ctx.paths.app_root), "RESPECTED_DATA_DIR": str(self.ctx.paths.data_root), "HOME": str(self.home), "USERPROFILE": str(self.home), "BEYIN_INVOKED_BY": "", "BEYIN_RECURSION_DEPTH": "0", "PYTHONUTF8": "1"}
        self.environment.pop("BEYIN_LLM_COMMAND", None)
        self.profile = IntegrationProfile("windows-native", (str(self.ctx.paths.app_root / "respectedbrain.exe"),), self.home)
        memory = self.vault / "🔮 850-Companion"
        (memory / "Last-Session.md").write_text("## Session: Native\nİlk provider kararı.\n## Previous Sessions\n", encoding="utf-8")
        (memory / "Threads.md").write_text("## Active\n### Native\n", encoding="utf-8")
        for relative, value in render_project_integrations(self.ctx, self.profile).items():
            path = self.vault / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)

    def _cleanup_process_workspace(self):
        deadline = time.monotonic() + 10
        while True:
            try:
                self.temporary.cleanup()
                return
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.05)

    def _cli(self, *arguments, payload=None, environment=None):
        return subprocess.run([sys.executable, "-m", "respectedbrain", *arguments], input=json.dumps(payload) if payload is not None else None, text=True, encoding="utf-8", capture_output=True, cwd=self.root, env=environment or self.environment, timeout=45)

    def _bridge(self, provider, event, payload):
        return self._cli("hook", "--vault-id", self.ctx.paths.vault_id, "--provider", provider, "--event", event, payload=payload)

    def test_all_provider_manifests_use_native_absolute_commands(self):
        combined = "\n".join((self.vault / relative).read_text(encoding="utf-8") for relative in (".claude/settings.json", ".codex/hooks.json", ".cursor/hooks.json", ".agents/hooks.json"))
        for provider in ("claude", "codex", "cursor", "antigravity"):
            self.assertIn(f"--provider {provider}", combined)
        self.assertIn("respectedbrain.exe", combined)
        self.assertIn(self.ctx.paths.vault_id, combined)
        for forbidden in ("python", ".py", "wsl.exe", "bash"):
            self.assertNotIn(forbidden, combined.lower())

    def test_start_prompt_end_and_precompact_run_in_separate_processes(self):
        started = self._bridge("codex", "start", {"session_id": "native"})
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("İlk provider kararı.", started.stdout)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self._bridge("cursor", "prompt", {"session_id": "native"}), range(30)))
        self.assertEqual([row.returncode for row in results], [0] * 30, [row.stderr for row in results])
        from respectedbrain.memory.lifecycle import session_key
        counter = self.state / ("prompt_count." + session_key("native"))
        self.assertEqual(counter.read_text(encoding="utf-8").strip(), "30")
        transcript = self.root / "native-transcript.jsonl"
        transcript.write_text("".join(json.dumps({"role": "user" if index % 2 == 0 else "assistant", "content": "native " + str(index)}) + "\n" for index in range(12)), encoding="utf-8")
        model = self.root / "model.py"
        model.write_text("import sys\nsys.stdout.reconfigure(encoding='utf-8')\nprint(" + repr(SUMMARY) + ")\n", encoding="utf-8")
        self.environment["BEYIN_LLM_COMMAND"] = shlex.join([sys.executable, str(model)])
        self.assertEqual(self._bridge("claude", "precompact", {"session_id": "native", "transcript_path": str(transcript)}).returncode, 0)
        result = self._bridge("antigravity", "end", {"session_id": "native", "transcript_path": str(transcript)})
        self.assertEqual(result.returncode, 0, result.stderr)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            logs = list((self.vault / "daily").glob("*.md"))
            if logs and any("Native test" in path.read_text(encoding="utf-8") for path in logs) and not any(self.state.glob("hookin-*.json")):
                break
            time.sleep(.05)
        else:
            self.fail("Detached package flush did not write the fake-model summary")
        self.assertFalse(any(self.state.glob("hookin-*.json")))
        self.assertFalse((self.vault / ".beyin").exists())

    def test_provider_first_retryable_failure_uses_the_next_real_cli_stub(self):
        from respectedbrain.providers import runner
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        log = self.root / "provider-order.txt"
        (bin_dir / "codex.cmd").write_text('@echo off\necho codex>>"%RESPECTED_STUB_LOG%"\necho 429 quota exceeded 1>&2\nexit /b 1\n', encoding="utf-8")
        (bin_dir / "cursor-agent.cmd").write_text('@echo off\necho cursor>>"%RESPECTED_STUB_LOG%"\necho fallback-summary\nexit /b 0\n', encoding="utf-8")
        self.ctx.config["preferences"].update(summary_provider="codex", provider_priority=["codex", "cursor"])
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir), "RESPECTED_STUB_LOG": str(log), "BEYIN_LLM_COMMAND": "", "BEYIN_RECURSION_DEPTH": "0"}):
            output, error, provider = runner.run_model("native prompt", self.vault, "text", 15, preferred="codex", ctx=self.ctx)
        self.assertEqual((output, error, provider), ("fallback-summary", None, "cursor"))
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["codex", "cursor"])

    def test_session_start_catchup_excludes_the_current_day(self):
        from respectedbrain.memory.flush import compile_catch_up
        daily = self.vault / ("daily/" + dt.date.today().isoformat() + ".md")
        daily.write_text("# Daily\nStill changing.\n", encoding="utf-8")
        model = mock.Mock()
        self.assertEqual(compile_catch_up(self.ctx, model=model, now=dt.datetime.now().astimezone()), 0)
        model.run.assert_not_called()
        self.assertFalse(any(self.state.glob("compile-trigger-*")))

    def test_compile_staging_uses_data_cache_and_is_cleaned(self):
        from respectedbrain.memory import compile as compiler
        daily = self.vault / "daily/2026-08-30.md"
        daily.write_text("# Native staging\n", encoding="utf-8")
        observed = {}
        def model_stub(_prompt, stage, _model):
            observed["stage"] = stage
            (stage / "knowledge/log.md").write_text("## native compile\n", encoding="utf-8")
            return None
        with mock.patch.object(compiler, "_run_model", side_effect=model_stub):
            result = compiler._compile_one(self.vault, self.state, daily, compiler._sha256(daily), "2026-08-31T08:00:00+03:00", mock.Mock(), self.ctx.paths.cache_dir)
        self.assertEqual(result, (None, ""))
        self.assertTrue(observed["stage"].is_relative_to(self.ctx.paths.cache_dir))
        self.assertFalse(observed["stage"].exists())
        self.assertFalse(observed["stage"].is_relative_to(self.vault))

    def test_map_builder_rejects_windows_directory_junction(self):
        from respectedbrain.vault.maps import refresh_maps
        outside = self.root / "outside-command-center"
        outside.mkdir()
        command_center = self.vault / "🎯 100-Command-Center"
        # Both absolute paths are verified inside this temporary fixture before removal.
        self.assertTrue(command_center.resolve().is_relative_to(self.root))
        shutil.rmtree(command_center)
        linked = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(command_center), str(outside)], capture_output=True, text=True, errors="replace")
        self.assertEqual(linked.returncode, 0, linked.stdout + linked.stderr)
        try:
            with self.assertRaisesRegex(ValueError, "unsafe-map-path"):
                refresh_maps(self.ctx, max_age_seconds=0)
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            command_center.rmdir()

    def test_transactional_updater_runs_with_native_paths_and_external_backup(self):
        from respectedbrain.installation.setup import setup
        from respectedbrain.installation.update import update
        vault = self.root / "Update 🧠 Brain"
        roots = Roots(self.root / "installed", self.root / "installation-data", vault)
        backend = Backend()
        disabled = dict.fromkeys(("global", "mcp", "schedule", "shortcut"), False)
        with mock.patch("respectedbrain.installation.payload.validate_installed_health"):
            self.assertTrue(setup(roots, vault, profile={}, desired=disabled, backend=backend, package=seed_package(self.root / "package")).success)
            ctx = build_context(roots, ConfigStore(roots.data_root), vault=vault, vault_id=None, env={})
            personal = vault / "🔮 850-Companion/Core.md"
            personal.write_bytes(b"native personal identity\n")
            before = snapshot(vault)
            result = update(ctx, package=seed_package(self.root / "next", content=b"MZ-next"), backend=backend)
        self.assertTrue(result.success, result.conflicts)
        self.assertEqual(snapshot(vault), before)
        self.assertTrue((roots.data_root / "backups" / result.tx_id / "journal.json").exists())
        self.assertFalse((vault / "scripts").exists())

if __name__ == "__main__":
    unittest.main(verbosity=2)
