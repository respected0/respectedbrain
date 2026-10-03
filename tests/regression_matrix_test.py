#!/usr/bin/env python3
"""End-to-end regression matrix test suite (20 scenarios) for C5-C10 stabilization."""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SCRIPTS_DIR = str((ROOT / "runtime" / "scripts") if (ROOT / "runtime" / "scripts").is_dir() else (ROOT / "scripts"))
ORIGINAL_SYS_PATH = list(sys.path)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

LOADED_MODULE_NAMES: list[str] = []


def tearDownModule() -> None:
    for name in LOADED_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path[:] = ORIGINAL_SYS_PATH


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    LOADED_MODULE_NAMES.append(name)
    spec.loader.exec_module(module)
    return module


RUNTIME_DIR = ROOT / "runtime" if (ROOT / "runtime").is_dir() else ROOT / "template/.beyin"
from respectedbrain.memory import lifecycle as LIFECYCLE
BRIDGE = load_module("c9_bridge", RUNTIME_DIR / "hooks/bridge.py" if (RUNTIME_DIR / "hooks/bridge.py").is_file() else TEMPLATE / ".beyin/hooks/bridge.py")
from respectedbrain.providers import runner as MODEL_RUNNER
from respectedbrain.core import platform as RUNTIME
from respectedbrain.memory import flush as FLUSH
from respectedbrain.memory import compile as COMPILE
from respectedbrain.briefing import service as BRIEFING
REPAIR_DAILY = load_module("c9_repair_daily", (ROOT / "runtime/scripts/repair_daily.py") if (ROOT / "runtime/scripts/repair_daily.py").is_file() else ROOT / "scripts/repair_daily.py")


VALID_FLUSH_SUMMARY = """## Bağlam
Test bağlamı.
## Önemli Konuşmalar
- Önemli nokta.
## Alınan Kararlar
- Karar verildi.
## Öğrenilenler
- Bilgi edinildi.
## Yapılacaklar
- Görev tamamlanacak.
"""

VALID_BRIEFING_BODY = """## Dün tamamlananlar
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


from contextlib import nullcontext
from tests.foundation_memory_test import FakeModel, make_context


class RegressionMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respected-c9-")
        self.vault = Path(self.temporary.name) / "TestBrain"
        self.ctx = make_context(self.vault)
        self.state_dir = self.ctx.paths.state_dir
        self.daily_dir = self.vault / "daily"
        self.knowledge_dir = self.vault / "knowledge"
        self.briefings_dir = self.vault / "🎯 100-Command-Center" / "Briefings"
        self.command_dir = self.vault / "🎯 100-Command-Center"
        self.companion_dir = self.vault / "🔮 850-Companion"
        self.beyin_dir = self.vault / ".beyin"

        for directory in (
            self.state_dir,
            self.daily_dir,
            self.knowledge_dir,
            self.briefings_dir,
            self.command_dir,
            self.companion_dir,
            self.beyin_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        # Baseline companion and map files
        (self.companion_dir / "Core.md").write_text("# Core\nFurkan's second brain.\n", encoding="utf-8")
        (self.companion_dir / "Last-Session.md").write_text("# Last-Session\nNone.\n", encoding="utf-8")
        (self.companion_dir / "Threads.md").write_text("# Threads\nNone.\n", encoding="utf-8")
        (self.companion_dir / "Kurallar.md").write_text("# Kurallar\nKullanıcı: Furkan.\n", encoding="utf-8")
        (self.command_dir / "Dashboard.md").write_text("# Dashboard\nKullanıcı paneli.\n", encoding="utf-8")
        (self.command_dir / "Vault-Map.md").write_text("# Vault Map\nHarita.\n", encoding="utf-8")
        (self.command_dir / "Skills-Map.md").write_text("# Skills Map\nBeceriler.\n", encoding="utf-8")
        (self.knowledge_dir / "index.md").write_text("# Knowledge Index\nKavramlar.\n", encoding="utf-8")

    def handle_event(self, vault, provider, event, payload):
        output = LIFECYCLE.handle_event(self.ctx, event=event, session_id=payload.get("session_id", ""),
            transcript=None,
            payload={**payload, "provider":provider}, now=datetime.now())
        return 0, output

    def run_briefing(self, vault, now, *, model_call, compile_call=None):
        from respectedbrain.core.context import ModelResult
        class Model:
            def run(self, prompt, *, cwd, mode, timeout):
                text, error, provider = model_call(prompt, cwd)
                return ModelResult(text, provider, error)
        if compile_call:
            with mock.patch.object(BRIEFING, "compile_memory", side_effect=lambda ctx, **kw: compile_call(ctx.paths.vault_root)):
                self.briefing_status = BRIEFING.run_if_due(self.ctx, model=Model(), now=now)
        else:
            self.briefing_status = BRIEFING.run_if_due(self.ctx, model=Model(), now=now)
        return (self.briefings_dir / f"{now:%Y-%m-%d}.md").is_file()

    def tearDown(self):
        self.temporary.cleanup()

    # -------------------------------------------------------------------------
    # Scenario 1: Claude normal flow: SessionStart -> UserPromptSubmit -> SessionEnd
    # -------------------------------------------------------------------------
    def test_01_claude_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, stdout = self.handle_event(self.vault, "claude", "SessionStart", {"session_id": "claude-1"})
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            self.assertIn("[Hafıza: Kurallar]", stdout)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 2: Claude PreCompact flow and transcript capture
    # -------------------------------------------------------------------------
    def test_02_claude_precompact_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            payload = {"session_id": "claude-pre", "transcript_path": "/fake/transcript.json"}
            code, _ = self.handle_event(self.vault, "claude", "PreCompact", payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once_with(
                self.ctx, "claude", payload={**payload, "provider":"claude"}, reason="precompact"
            )

    # -------------------------------------------------------------------------
    # Scenario 3: Codex normal flow: SessionStart -> UserPromptSubmit -> SessionEnd
    # -------------------------------------------------------------------------
    def test_03_codex_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            start_payload = {"session_id": "codex-s1"}
            code, stdout = self.handle_event(self.vault, "codex", "SessionStart", start_payload)
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()

        prompt_payload = {"session_id": "codex-s1", "prompt": "test"}
        code, _ = self.handle_event(self.vault, "codex", "UserPromptSubmit", prompt_payload)
        self.assertEqual(code, 0)

        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            end_payload = {"session_id": "codex-s1", "transcript_path": "/fake/transcript.json"}
            code, _ = self.handle_event(self.vault, "codex", "SessionEnd", end_payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 4: Codex PreCompact flow
    # -------------------------------------------------------------------------
    def test_04_codex_precompact_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            payload = {"session_id": "codex-pre", "transcript_path": "/fake/transcript.json"}
            code, _ = self.handle_event(self.vault, "codex", "PreCompact", payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 5: Cursor normal flow: sessionStart -> beforeSubmitPrompt -> sessionEnd
    # -------------------------------------------------------------------------
    def test_05_cursor_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, stdout = self.handle_event(self.vault, "cursor", "sessionStart", {"session_id": "cur-1"})
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()

        code, _ = self.handle_event(self.vault, "cursor", "beforeSubmitPrompt", {"session_id": "cur-1"})
        self.assertEqual(code, 0)

        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, _ = self.handle_event(self.vault, "cursor", "sessionEnd", {"session_id": "cur-1", "transcript_path": "/path"})
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 6: Cursor preCompact (empty transcript scenario)
    # -------------------------------------------------------------------------
    def test_06_cursor_precompact_empty_transcript(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            payload = {"session_id": "cur-pre-empty"}
            code, _ = self.handle_event(self.vault, "cursor", "preCompact", payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 7: Antigravity normal flow: PreInvocation -> Stop
    # -------------------------------------------------------------------------
    def test_07_antigravity_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, stdout = self.handle_event(self.vault, "antigravity", "PreInvocation", {"session_id": "agy-1"})
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()

        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, _ = self.handle_event(self.vault, "antigravity", "Stop", {"session_id": "agy-1", "transcript_path": "/path"})
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 8: Antigravity background agy.exe recursion protection
    # -------------------------------------------------------------------------
    def test_08_antigravity_background_agy_recursion_guard(self):
        with mock.patch.dict(os.environ, {"BEYIN_INVOKED_BY": "beyin-scripts"}):
            with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
                code, stdout = self.handle_event(self.vault, "antigravity", "Stop", {"session_id": "agy-rec"})
                self.assertEqual(code, 0)
                mock_launch.assert_not_called()

    # -------------------------------------------------------------------------
    # Scenario 9: WSL -> Windows cross-CLI invocation BEYIN_INVOKED_BY in WSLENV
    # -------------------------------------------------------------------------
    def test_09_wsl_to_windows_wslenv_forwarding(self):
        env = {"WSL_INTEROP": "1", "WSLENV": "EXISTING_VAR"}
        with mock.patch.object(MODEL_RUNNER.runtime_platform, "windows_user_root", return_value=Path("/mnt/c/Users/Furkan")), \
             mock.patch.object(MODEL_RUNNER.os, "name", "posix"):
            MODEL_RUNNER._windows_user_environment(env, self.vault)
        wslenv = env.get("WSLENV", "")
        # BEYIN_INVOKED_BY and BEYIN_RECURSION_DEPTH must be present in WSLENV as scalar (no /p)
        self.assertIn("BEYIN_INVOKED_BY", wslenv)
        self.assertIn("BEYIN_RECURSION_DEPTH", wslenv)
        self.assertNotIn("BEYIN_INVOKED_BY/p", wslenv)
        # Paths like USERPROFILE, LOCALAPPDATA, APPDATA should have /p
        self.assertIn("USERPROFILE/p", wslenv)

    # -------------------------------------------------------------------------
    # Scenario 10: Windows -> WSL bridge call re-entrancy prevention
    # -------------------------------------------------------------------------
    def test_10_windows_to_wsl_bridge_reentrancy_prevention(self):
        with mock.patch.dict(os.environ, {"BEYIN_INVOKED_BY": "beyin-scripts"}):
            with mock.patch.object(LIFECYCLE, "handle_event") as mock_handle:
                result = BRIDGE.main(["--provider", "antigravity", "--event", "end", "--global-hook"])
                self.assertEqual(result, 0)
                mock_handle.assert_not_called()

    # -------------------------------------------------------------------------
    # Scenario 11: BEYIN_RECURSION_DEPTH limit exceeded triggers no-op and warning
    # -------------------------------------------------------------------------
    def test_11_recursion_depth_limit_exceeded(self):
        with mock.patch.dict(os.environ, {"BEYIN_RECURSION_DEPTH": "2"}):
            with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
                code, _ = self.handle_event(self.vault, "claude", "SessionEnd", {"session_id": "s-dep"})
                self.assertEqual(code, 0)
                mock_launch.assert_not_called()

            # Health warning must be written
            health_path = self.state_dir / "health.json"
            self.assertTrue(health_path.is_file(), "health.json must exist when re-entrant call is ignored")
            health_data = json.loads(health_path.read_text(encoding="utf-8"))
            self.assertTrue(any("reentrant" in str(v) or "recursion" in str(v) for v in health_data.values()))

    # -------------------------------------------------------------------------
    # Scenario 12: Duplicate daily blocks cleanup with timestamped backup
    # -------------------------------------------------------------------------
    def test_12_repair_daily_duplicate_blocks(self):
        daily_file = self.daily_dir / "2026-09-04.md"
        daily_file.write_text(
            "# Günlük Log: 2026-09-04\n\n## Oturumlar\n\n"
            "### Oturum (10:00)\n\n"
            "## Bağlam\nAynı bağlam.\n\n## Önemli Konuşmalar\n- Konu.\n\n"
            "## Alınan Kararlar\n- Karar.\n\n## Öğrenilenler\n- Bilgi.\n\n## Yapılacaklar\n- İş.\n\n"
            "### Oturum (10:05)\n\n"
            "## Bağlam\nAynı bağlam.\n\n## Önemli Konuşmalar\n- Konu.\n\n"
            "## Alınan Kararlar\n- Karar.\n\n## Öğrenilenler\n- Bilgi.\n\n## Yapılacaklar\n- İş.\n",
            encoding="utf-8",
        )

        cleaned, backup_path = REPAIR_DAILY.repair_daily_file(daily_file, self.vault)
        self.assertTrue(cleaned)
        self.assertTrue(backup_path.is_file())
        self.assertIn("daily-backup", str(backup_path))

        # Check deduplication: only 1 "### Oturum" should remain
        content = daily_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("### Oturum"), 1)

    # -------------------------------------------------------------------------
    # Scenario 13: Idempotency: same session_id flush call does not append a second time
    # -------------------------------------------------------------------------
    def test_13_flush_idempotency_prevents_duplicate_append(self):
        hook_input_path = self.state_dir / "hookin-test-idempotency.json"
        transcript_file = self.vault / "transcript.jsonl"
        transcript_file.write_text(
            json.dumps({"type": "user", "message": {"content": "Merhaba"}}) + "\n"
            + json.dumps({"type": "assistant", "message": {"content": "Selamlar"}}) + "\n",
            encoding="utf-8",
        )
        hook_input_path.write_text(
            json.dumps({"session_id": "session-unique-123", "transcript_path": str(transcript_file)}),
            encoding="utf-8",
        )

        event_time = datetime(2026, 9, 4, 11, 0)
        with mock.patch.object(FLUSH, "_run_model", return_value=(VALID_FLUSH_SUMMARY, None)):
            with nullcontext():
                with nullcontext():
                    hook_data = FLUSH.load_hook_input(hook_input_path)
                    # First run: should append
                    code1 = FLUSH.flush(self.ctx, session_id=hook_data["session_id"], transcript=Path(hook_data["transcript_path"]), model=FakeModel(), now=event_time)
                    self.assertEqual(code1, 0)
                    daily_file = self.daily_dir / "2026-09-04.md"
                    self.assertTrue(daily_file.exists())
                    self.assertEqual(daily_file.read_text(encoding="utf-8").count("### Oturum"), 1)

                    # Second run with same session_id: should be no-op
                    code2 = FLUSH.flush(self.ctx, session_id=hook_data["session_id"], transcript=Path(hook_data["transcript_path"]), model=FakeModel(), now=event_time)
                    self.assertEqual(code2, 0)
                    self.assertEqual(daily_file.read_text(encoding="utf-8").count("### Oturum"), 1)

    # -------------------------------------------------------------------------
    # Scenario 14: Sweeping stale .state/ files
    # -------------------------------------------------------------------------
    def test_14_sweep_stale_state_files(self):
        stale_lock = self.state_dir / "flush-stale123.lock"
        stale_lock.write_text("", encoding="utf-8")
        stale_input = self.state_dir / "hookin-stale456.json"
        stale_input.write_text("{}", encoding="utf-8")

        # Set mtime to 2 hours ago
        past = datetime.now().timestamp() - 7200
        os.utime(stale_lock, (past, past))
        os.utime(stale_input, (past, past))

        FLUSH._sweep_stale_hook_inputs(self.state_dir, self.state_dir / "nonexistent.json", datetime.now().timestamp())
        self.assertFalse(stale_input.exists())

    # -------------------------------------------------------------------------
    # Scenario 15: SessionEnd after 18:00 does NOT trigger compile
    # -------------------------------------------------------------------------
    def test_15_session_end_after_1800_does_not_trigger_compile(self):
        hook_input_path = self.state_dir / "hookin-test-18.json"
        transcript_file = self.vault / "transcript_18.jsonl"
        transcript_file.write_text(
            json.dumps({"type": "user", "message": {"content": "Akşam işi"}}) + "\n"
            + json.dumps({"type": "assistant", "message": {"content": "Tamamlandı"}}) + "\n",
            encoding="utf-8",
        )
        hook_input_path.write_text(
            json.dumps({"session_id": "session-1800", "transcript_path": str(transcript_file)}),
            encoding="utf-8",
        )

        after_18 = datetime(2026, 9, 4, 19, 30)
        with mock.patch.object(FLUSH, "_run_model", return_value=(VALID_FLUSH_SUMMARY, None)):
            with nullcontext():
                with nullcontext():
                    hook_data = FLUSH.load_hook_input(hook_input_path)
                    FLUSH.flush(self.ctx, session_id=hook_data["session_id"], transcript=Path(hook_data["transcript_path"]), model=FakeModel(), now=after_18)

                    # Trigger file must NOT be created
                    trigger = self.state_dir / "compile-trigger-2026-09-04"
                    self.assertFalse(trigger.exists())

    # -------------------------------------------------------------------------
    # Scenario 16: 08:00 scheduler runs compile first, then briefing
    # -------------------------------------------------------------------------
    def test_16_morning_pipeline_compiles_then_briefs(self):
        yesterday_daily = self.daily_dir / "2026-09-03.md"
        yesterday_daily.write_text("# Günlük Log: 2026-09-03\n\n## Oturumlar\n\n### Oturum (15:00)\n\n" + VALID_FLUSH_SUMMARY, encoding="utf-8")

        pipeline_order = []

        def mock_compile_stage(*args, **kwargs):
            pipeline_order.append("compile")
            return 0

        def mock_briefing_model(*args, **kwargs):
            pipeline_order.append("briefing")
            return VALID_BRIEFING_BODY, None, "custom"

        morning_time = datetime(2026, 9, 4, 8, 15)
        with mock.patch.object(BRIEFING, "compile_memory", mock_compile_stage):
            result = self.run_briefing(self.vault, morning_time, model_call=mock_briefing_model)
            self.assertTrue(result)
            self.assertEqual(pipeline_order, ["compile", "briefing"])
            briefing_file = self.briefings_dir / "2026-09-04.md"
            self.assertTrue(briefing_file.exists())

    # -------------------------------------------------------------------------
    # Scenario 17: Missed 08:00 schedule runs catch-up when available
    # -------------------------------------------------------------------------
    def test_17_missed_0800_schedule_catches_up(self):
        later_time = datetime(2026, 9, 4, 11, 45)
        with mock.patch.object(BRIEFING, "compile_memory", return_value=None):
            result = self.run_briefing(
                self.vault,
                later_time,
                model_call=lambda p, c: (VALID_BRIEFING_BODY, None, "custom"),
            )
            self.assertTrue(result)
            briefing_file = self.briefings_dir / "2026-09-04.md"
            self.assertTrue(briefing_file.exists())

    # -------------------------------------------------------------------------
    # Scenario 18: Briefing generates even if compile fails (fail-soft)
    # -------------------------------------------------------------------------
    def test_18_briefing_generates_even_if_compile_fails(self):
        compile_called = False

        def failing_compile(root):
            nonlocal compile_called
            compile_called = True
            raise RuntimeError("compile-simulated-error")

        morning_time = datetime(2026, 9, 4, 8, 5)
        result = self.run_briefing(
            self.vault,
            morning_time,
            model_call=lambda p, c: (VALID_BRIEFING_BODY, None, "custom"),
            compile_call=failing_compile,
        )
        self.assertTrue(result, "run_if_due must return True even if compilation raises an exception")
        self.assertEqual(self.briefing_status, 1, "compile failure must remain visible to explicit callers")
        self.assertTrue(compile_called, "compile_call must be attempted before generating briefing")
        briefing_file = self.briefings_dir / "2026-09-04.md"
        self.assertTrue(briefing_file.is_file(), "Briefing file must be successfully generated")

    def test_21_briefing_model_failure_records_health(self):
        morning_time = datetime(2026, 9, 4, 8, 30)
        result = self.run_briefing(
            self.vault,
            morning_time,
            model_call=lambda p, c: (None, "model-timeout-error", "custom"),
        )
        self.assertFalse(result, "run_if_due must return False when model call fails")
        health = self.ctx.paths.state_dir / "briefing-health.json"
        self.assertTrue(health.is_file(), "briefing-health.json must be recorded on model error")
        data = json.loads(health.read_text(encoding="utf-8"))
        self.assertEqual(data.get("error"), "model-timeout-error")

    # -------------------------------------------------------------------------
    # Scenario 19: All background processes run without console & no UAC
    # -------------------------------------------------------------------------
    def test_19_silent_background_process_options(self):
        with mock.patch("os.name", "nt"):
            detached = RUNTIME.detached_process_options()
            hidden = RUNTIME.hidden_process_options()
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            self.assertEqual(hidden.get("creationflags", 0) & CREATE_NO_WINDOW, CREATE_NO_WINDOW)
            self.assertEqual(detached.get("creationflags", 0) & DETACHED_PROCESS, DETACHED_PROCESS)

    # -------------------------------------------------------------------------
    # Scenario 20: Memory continuity across different providers
    # -------------------------------------------------------------------------
    def test_20_memory_continuity_across_providers(self):
        daily_file = self.daily_dir / "2026-09-03.md"
        daily_file.write_text(
            "# Günlük Log: 2026-09-03\n\n## Oturumlar\n\n### Oturum (14:00)\n\n"
            "## Bağlam\nClaude ile mimari çalışma.\n\n"
            "## Önemli Konuşmalar\n- Ortak bellek tasarlandı.\n\n"
            "## Alınan Kararlar\n- Respected Brain standardı.\n\n"
            "## Öğrenilenler\n- Çapraz model sürekliliği mümkün.\n\n"
            "## Yapılacaklar\n- Antigravity ile devam et.\n",
            encoding="utf-8",
        )

        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, stdout = self.handle_event(self.vault, "antigravity", "PreInvocation", {"session_id": "agy-cont"})
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
