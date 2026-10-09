"""Explicit context memory contracts against isolated fixtures and fake providers."""
from datetime import datetime
from pathlib import Path
import importlib
import json
import subprocess
import tempfile
import unittest
from unittest import mock

from respectedbrain.core.context import AppContext
from respectedbrain.core.paths import AppPaths
from respectedbrain.core.resources import ResourceCatalog
from tests.foundation_support import snapshot

NOW = datetime(2026, 10, 3, 20, 15)
SUMMARY = "\n".join("## " + name + "\n- Kalıcı karar." for name in
    ("Bağlam", "Önemli Konuşmalar", "Alınan Kararlar", "Öğrenilenler", "Yapılacaklar"))

class FakeModel:
    def __init__(self, response=SUMMARY):
        self.calls = 0
        self.response = response
    def run(self, prompt, *, cwd, mode, timeout):
        from respectedbrain.core.context import ModelResult
        self.calls += 1
        if mode == "workspace":
            index = cwd / "knowledge/index.md"
            index.write_text(index.read_text(encoding="utf-8") + "\nDerlenmiş bilgi.\n", encoding="utf-8")
        return ModelResult(self.response, "codex", None)

class FoundationMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = self.root / "app"
        self.app.mkdir()
        (self.app / "config.json").write_text('{"summary_provider":"claude"}')
        (self.app / "config.json").chmod(0o444)
        self.addCleanup(lambda: (self.app / "config.json").chmod(0o666))
        self.data = self.root / "data"
        self.ctx1 = self.context("Türkçe 🧠 Vault", "11111111-1111-4111-8111-111111111111")
        self.ctx2 = self.context("İkinci Vault", "22222222-2222-4222-8222-222222222222")
    def context(self, name, uuid):
        vault = self.root / name
        vault.mkdir()
        (vault / "daily").mkdir()
        (vault / "knowledge").mkdir()
        (vault / "knowledge/index.md").write_text("# İndeks\n", encoding="utf-8")
        (vault / "🔮 850-Companion").mkdir()
        return AppContext(AppPaths(self.app, self.data, vault, uuid),
            {"preferences": {"summary_provider": "codex", "provider_priority": ["codex", "gemini"], "provider_fallback": False}}, ResourceCatalog())
    def transcript(self, ctx):
        path = self.root / (ctx.paths.vault_id + ".jsonl")
        path.write_text(json.dumps({"role":"user", "content":"Kalıcı bir mimari karar alındı."}) + "\n", encoding="utf-8")
        return path
    def module(self, name):
        try:
            return importlib.import_module("respectedbrain." + name)
        except ModuleNotFoundError:
            self.fail("Missing explicit-context service: " + name)
    def test_two_vaults_share_package_not_session_state(self):
        mod = self.module("memory.flush")
        fake = FakeModel()
        before2, app = snapshot(self.ctx2.paths.state_dir), snapshot(self.app)
        t = self.transcript(self.ctx1)
        self.assertEqual(mod.flush(self.ctx1, session_id="same", transcript=t, model=fake, now=NOW), 0)
        self.assertEqual(mod.flush(self.ctx1, session_id="same", transcript=t, model=fake, now=NOW), 0)
        daily = self.ctx1.paths.vault_root / "daily/2026-10-03.md"
        self.assertEqual(daily.read_text(encoding="utf-8").count("RESPECTED-SESSION:"), 2)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(snapshot(self.ctx2.paths.state_dir), before2)
        self.assertEqual(snapshot(self.app), app)
        self.assertFalse((self.ctx1.paths.vault_root / ".beyin").exists())
        mod.flush(self.ctx2, session_id="same", transcript=self.transcript(self.ctx2), model=fake, now=NOW)
        self.assertEqual(fake.calls, 2)
    def test_compile_claim_and_flush_idempotency_survive_restart(self):
        flush = self.module("memory.flush")
        compile = self.module("memory.compile")
        fake = FakeModel()
        t = self.transcript(self.ctx1)
        flush.flush(self.ctx1, session_id="same", transcript=t, model=fake, now=NOW)
        compile.compile_memory(self.ctx1, model=fake, now=NOW)
        calls = fake.calls
        importlib.reload(flush)
        importlib.reload(compile)
        flush.flush(self.ctx1, session_id="same", transcript=t, model=fake, now=NOW)
        compile.compile_memory(self.ctx1, model=fake, now=NOW)
        self.assertEqual(fake.calls, calls)
        state = json.loads((self.ctx1.paths.state_dir / "compile-state.json").read_text())
        self.assertIn("2026-10-03.md", state["ingested"])
        self.assertEqual(state["last_status"], "ok")
    def test_provider_preferences_come_from_user_config(self):
        mod = self.module("providers.runner")
        runner = mod.ModelRunner(self.ctx1)
        with mock.patch.object(mod.shutil, "which", return_value="codex"), mock.patch.object(mod, "_run_process_tree", return_value=subprocess.CompletedProcess([], 0, "summary", "")) as process:
            result = runner.run("prompt", cwd=self.root, mode="text", timeout=1)
        self.assertEqual(result.provider, "codex")
        self.assertEqual(result.text, "summary")
        self.assertIn("exec", process.call_args.args[0].argv)
        self.assertEqual(runner.preferences["summary_provider"], "codex")
        self.assertEqual(runner.preferences["provider_priority"][0], "codex")
    def test_lifecycle_prompt_uses_uuid_state(self):
        lifecycle = self.module("memory.lifecycle")
        lifecycle.handle_event(self.ctx1, event="prompt", session_id="same", transcript=None, payload={}, now=NOW)
        lifecycle.handle_event(self.ctx2, event="prompt", session_id="same", transcript=None, payload={}, now=NOW)
        key = lifecycle.session_key("same")
        self.assertEqual((self.ctx1.paths.state_dir / ("prompt_count." + key)).read_text().strip(), "1")
        self.assertEqual((self.ctx2.paths.state_dir / ("prompt_count." + key)).read_text().strip(), "1")
        self.assertFalse((self.ctx1.paths.vault_root / ".beyin").exists())
    def test_compile_rejects_model_writes_outside_allowed_notes(self):
        compile = self.module("memory.compile")
        (self.ctx1.paths.vault_root / "daily/2026-10-02.md").write_text("# Daily\nDecision.")
        class Malicious(FakeModel):
            def run(self, prompt, *, cwd, mode, timeout):
                (cwd / "forbidden.txt").write_text("unsafe")
                return super().run(prompt, cwd=cwd, mode=mode, timeout=timeout)
        compile.compile_memory(self.ctx1, model=Malicious(), now=NOW)
        state = json.loads((self.ctx1.paths.state_dir / "compile-state.json").read_text())
        self.assertEqual(state["last_status"], "fail:policy")
        self.assertEqual(state["ingested"], {})
        self.assertEqual((self.ctx1.paths.vault_root / "knowledge/index.md").read_text(encoding="utf-8"), "# İndeks\n")

    def test_invalid_compile_claim_never_removes_external_file(self):
        compile = self.module("memory.compile")
        claim = self.root / "compile-trigger-2026-10-03"
        claim.write_text("other writer")
        compile.compile_pending(self.ctx1, model=FakeModel(), now=NOW, trigger_claim=claim)
        self.assertTrue(claim.exists())
        self.assertEqual(claim.read_text(), "other writer")

    def test_provider_status_preserves_shape_and_cached_versions(self):
        mod = self.module("providers.runner")
        self.assertTrue(hasattr(mod, "ProviderStatus"), "Provider discovery must be owned by providers service")
        service = mod.ProviderStatus()
        with mock.patch.object(mod, "_find_executable", side_effect=lambda name: "codex" if name == "codex" else None), mock.patch.object(mod.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "codex 1.2.3", "")) as process:
            status = service.get_cli_status()
            self.assertEqual(service.get_cli_status(), status)
        self.assertEqual(process.call_count, 1)
        self.assertEqual(status["codex"]["version"], "codex 1.2.3")
        self.assertEqual(status["codex"]["auth_status"], "unknown")
        self.assertFalse(status["claude"]["installed"])

    def test_provider_version_is_not_authentication_and_cache_is_not_mutable_by_callers(self):
        from respectedbrain.providers import runner
        service=runner.ProviderStatus()
        with mock.patch.object(runner,'_find_executable',side_effect=lambda name:'codex' if name=='codex' else None),mock.patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'codex 1.2.3','')) as process:
            first=service.get_cli_status()
            self.assertEqual(first['codex']['auth_status'],'unknown')
            first['codex']['installed']=False
            second=service.get_cli_status()
            self.assertTrue(second['codex']['installed'])
            self.assertEqual(process.call_count,1)


    def test_explicit_flush_reports_model_failure(self):
        from respectedbrain.core.context import ModelResult
        class Failure(FakeModel):
            def run(self, prompt, *, cwd, mode, timeout):
                return ModelResult(None, "codex", "codex-timeout")
        flush = self.module("memory.flush")
        result = flush.flush(self.ctx1, session_id="failed", transcript=self.transcript(self.ctx1), model=Failure(), now=NOW)
        self.assertEqual(result, 1)
        state = json.loads(flush._session_state_path(self.ctx1.paths.state_dir, "failed").read_text())
        self.assertEqual(state["status"], "fail")

    def test_companion_failure_is_visible_and_retries_without_model_or_duplicate_event(self):
        from respectedbrain.memory import flush, events
        from datetime import timedelta
        for operation in ('record_event', 'project_companion'):
            with self.subTest(operation=operation):
                identity = 'pending-' + operation
                model = FakeModel()
                transcript = self.transcript(self.ctx1)
                with mock.patch.object(events, operation, side_effect=OSError('fixture failure')):
                    self.assertEqual(flush.flush(self.ctx1, session_id=identity, transcript=transcript, model=model, now=NOW), 1)
                state = json.loads(flush._session_state_path(self.ctx1.paths.state_dir, identity).read_text())
                self.assertEqual(state['status'], 'pending')
                self.assertEqual(state['detail'], 'companion-sync-failed')
                self.assertTrue((self.ctx1.paths.state_dir / 'health.json').exists())
                daily = self.ctx1.paths.vault_root / 'daily/2026-10-03.md'
                before = daily.read_bytes()
                self.assertEqual(flush.flush(self.ctx1, session_id=identity, transcript=transcript, model=model, now=NOW+timedelta(days=1)), 0)
                self.assertEqual(model.calls, 1)
                self.assertEqual(daily.read_bytes(), before)
                self.assertFalse((daily.parent/'2026-10-04.md').exists())
                recorded = [event for event in events.list_events(self.ctx1.paths.vault_root, include_archive=True) if event['session_id']==identity]
                self.assertEqual(len(recorded), 1)
                self.assertEqual(json.loads(flush._session_state_path(self.ctx1.paths.state_dir,identity).read_text())['status'],'ok')

    def test_pending_companion_survives_short_precompact_and_preserves_daily_edit(self):
        from respectedbrain.memory import flush,events
        from datetime import timedelta
        transcript=self.transcript(self.ctx1)
        model=FakeModel()
        with mock.patch.object(events,'record_event',side_effect=OSError('fixture failure')):
            self.assertEqual(flush.flush(self.ctx1,session_id='short-pending',transcript=transcript,model=model,now=NOW),1)
        daily=self.ctx1.paths.vault_root/'daily/2026-10-03.md'
        edited=daily.read_bytes().replace('Kalıcı karar.'.encode('utf-8'),b'Human revised text')
        daily.write_bytes(edited)
        self.assertEqual(flush.flush_transcript(self.ctx1,session_id='short-pending',transcript=transcript,model=model,now=NOW+timedelta(minutes=1),reason='precompact'),0)
        self.assertEqual(model.calls,1)
        self.assertEqual(daily.read_bytes(),edited)
        self.assertEqual(len(events.list_events(self.ctx1.paths.vault_root)),1)

    def test_explicit_compile_reports_model_failure(self):
        from respectedbrain.core.context import ModelResult
        class Failure(FakeModel):
            def run(self, prompt, *, cwd, mode, timeout):
                return ModelResult(None, "codex", "codex-timeout")
        compile = self.module("memory.compile")
        (self.ctx1.paths.vault_root / "daily/2026-10-02.md").write_text("# Daily\nDecision.")
        self.assertEqual(compile.compile_memory(self.ctx1, model=Failure(), now=NOW), 1)

    def test_explicit_compile_reports_invalid_claim_and_failed_state_write(self):
        compile = self.module("memory.compile")
        claim = self.root / "compile-trigger-2026-10-03"
        claim.write_text("external")
        self.assertEqual(compile.compile_pending(self.ctx1, model=FakeModel(), now=NOW, trigger_claim=claim), 1)
        with mock.patch.object(compile, "_save_state", side_effect=OSError("write failure")):
            self.assertEqual(compile.compile_memory(self.ctx1, model=FakeModel(), now=NOW), 1)
        self.assertTrue(claim.exists())

    def test_catch_up_compile_claim_ignores_today_and_is_released(self):
        flush = self.module("memory.flush")
        self.assertTrue(hasattr(flush, "compile_catch_up"), "Context catch-up compile service is missing")
        yesterday = self.ctx1.paths.vault_root / "daily/2026-10-02.md"
        yesterday.write_text("# Yesterday\nDecision.")
        (self.ctx1.paths.vault_root / "daily/2026-10-03.md").write_text("# Today\nOngoing.")
        fake = FakeModel()
        self.assertEqual(flush.compile_catch_up(self.ctx1, model=fake, now=NOW), 0)
        self.assertEqual(fake.calls, 1)
        state = json.loads((self.ctx1.paths.state_dir / "compile-state.json").read_text())
        self.assertEqual(set(state["ingested"]), {"2026-10-02.md"})
        self.assertFalse(any(self.ctx1.paths.state_dir.glob("compile-trigger-*")))
        self.assertEqual(flush.compile_catch_up(self.ctx1, model=fake, now=NOW), 0)
        self.assertEqual(fake.calls, 1)

    def test_importing_memory_services_does_not_access_user_data_or_launch_processes(self):
        code = """
from unittest import mock
import importlib, os, pathlib, subprocess, sys
import respectedbrain  # immutable distribution metadata is permitted
names = ('providers.runner', 'memory.flush', 'memory.compile', 'memory.lifecycle',
         'memory.session_brain', 'memory.session_viz', 'memory.bounded_recall',
         'memory.events', 'memory.graph.graph_analysis', 'memory.graph.graphrag')
with mock.patch.object(pathlib.Path, 'read_text', side_effect=AssertionError('user read during import')), mock.patch.object(pathlib.Path, 'mkdir', side_effect=AssertionError('mkdir during import')), mock.patch.object(subprocess, 'run', side_effect=AssertionError('process during import')), mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('process during import')), mock.patch.object(sys.stdout, 'reconfigure', side_effect=AssertionError('stream changed during import')):
    for name in names:
        importlib.import_module('respectedbrain.' + name)
"""
        environment = dict(__import__("os").environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([__import__("sys").executable, "-c", code], cwd=self.root,
                                env=environment, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

def make_context(vault: Path, fixture_root: Path | None = None) -> AppContext:
    root = fixture_root or vault.parent
    return AppContext(AppPaths(root / "app", root / "data", vault,
        "11111111-1111-4111-8111-111111111111"), {"preferences": {}}, ResourceCatalog())
