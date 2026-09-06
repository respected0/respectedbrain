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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LIFECYCLE = load_module("c9_lifecycle", TEMPLATE / ".beyin/hooks/lifecycle.py")
BRIDGE = load_module("c9_bridge", TEMPLATE / ".beyin/hooks/bridge.py")
MODEL_RUNNER = load_module("c9_model_runner", TEMPLATE / ".beyin/model_runner.py")
RUNTIME = load_module("c9_runtime", TEMPLATE / ".beyin/runtime_platform.py")
FLUSH = load_module("c9_flush", TEMPLATE / ".beyin/engine/flush.py")
COMPILE = load_module("c9_compile", TEMPLATE / ".beyin/engine/compile.py")
BRIEFING = load_module("c9_briefing", TEMPLATE / ".beyin/morning_briefing.py")
REPAIR_DAILY = load_module("c9_repair_daily", ROOT / "scripts/repair_daily.py")


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


class RegressionMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respected-c9-")
        self.vault = Path(self.temporary.name) / "TestBrain"
        self.state_dir = self.vault / ".beyin" / "engine" / ".state"
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

    def tearDown(self):
        self.temporary.cleanup()

    # -------------------------------------------------------------------------
    # Scenario 1: Claude normal flow: SessionStart -> UserPromptSubmit -> SessionEnd
    # -------------------------------------------------------------------------
    def test_01_claude_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, stdout = LIFECYCLE.handle_event(self.vault, "claude", "SessionStart", {"session_id": "claude-1"})
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
            code, _ = LIFECYCLE.handle_event(self.vault, "claude", "PreCompact", payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once_with(
                self.vault, self.state_dir, "claude", payload=payload, reason="precompact"
            )

    # -------------------------------------------------------------------------
    # Scenario 3: Codex normal flow: SessionStart -> UserPromptSubmit -> SessionEnd
    # -------------------------------------------------------------------------
    def test_03_codex_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            start_payload = {"session_id": "codex-s1"}
            code, stdout = LIFECYCLE.handle_event(self.vault, "codex", "SessionStart", start_payload)
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()

        prompt_payload = {"session_id": "codex-s1", "prompt": "test"}
        code, _ = LIFECYCLE.handle_event(self.vault, "codex", "UserPromptSubmit", prompt_payload)
        self.assertEqual(code, 0)

        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            end_payload = {"session_id": "codex-s1", "transcript_path": "/fake/transcript.json"}
            code, _ = LIFECYCLE.handle_event(self.vault, "codex", "SessionEnd", end_payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 4: Codex PreCompact flow
    # -------------------------------------------------------------------------
    def test_04_codex_precompact_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            payload = {"session_id": "codex-pre", "transcript_path": "/fake/transcript.json"}
            code, _ = LIFECYCLE.handle_event(self.vault, "codex", "PreCompact", payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 5: Cursor normal flow: sessionStart -> beforeSubmitPrompt -> sessionEnd
    # -------------------------------------------------------------------------
    def test_05_cursor_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, stdout = LIFECYCLE.handle_event(self.vault, "cursor", "sessionStart", {"session_id": "cur-1"})
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()

        code, _ = LIFECYCLE.handle_event(self.vault, "cursor", "beforeSubmitPrompt", {"session_id": "cur-1"})
        self.assertEqual(code, 0)

        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, _ = LIFECYCLE.handle_event(self.vault, "cursor", "sessionEnd", {"session_id": "cur-1", "transcript_path": "/path"})
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 6: Cursor preCompact (empty transcript scenario)
    # -------------------------------------------------------------------------
    def test_06_cursor_precompact_empty_transcript(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            payload = {"session_id": "cur-pre-empty"}
            code, _ = LIFECYCLE.handle_event(self.vault, "cursor", "preCompact", payload)
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 7: Antigravity normal flow: PreInvocation -> Stop
    # -------------------------------------------------------------------------
    def test_07_antigravity_normal_flow(self):
        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, stdout = LIFECYCLE.handle_event(self.vault, "antigravity", "PreInvocation", {"session_id": "agy-1"})
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()

        with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
            code, _ = LIFECYCLE.handle_event(self.vault, "antigravity", "Stop", {"session_id": "agy-1", "transcript_path": "/path"})
            self.assertEqual(code, 0)
            mock_launch.assert_called_once()

    # -------------------------------------------------------------------------
    # Scenario 8: Antigravity background agy.exe recursion protection
    # -------------------------------------------------------------------------
    def test_08_antigravity_background_agy_recursion_guard(self):
        with mock.patch.dict(os.environ, {"BEYIN_INVOKED_BY": "beyin-scripts"}):
            with mock.patch.object(LIFECYCLE, "_launch_flush") as mock_launch:
                code, stdout = LIFECYCLE.handle_event(self.vault, "antigravity", "Stop", {"session_id": "agy-rec"})
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
                code, _ = LIFECYCLE.handle_event(self.vault, "claude", "SessionEnd", {"session_id": "s-dep"})
                self.assertEqual(code, 0)
                mock_launch.assert_not_called()

            # Health warning should be written
            health_path = self.state_dir / "health.json"
            if health_path.exists():
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
            with mock.patch.object(FLUSH, "VAULT_ROOT", self.vault):
                with mock.patch.object(FLUSH, "STATE_DIR", self.state_dir):
                    args = FLUSH._parse_args(["--hook-input", str(hook_input_path), "--reason", "sessionend"])
                    # First run: should append
                    code1 = FLUSH._flush_once(args, event_time)
                    self.assertEqual(code1, 0)
                    daily_file = self.daily_dir / "2026-09-04.md"
                    self.assertTrue(daily_file.exists())
                    self.assertEqual(daily_file.read_text(encoding="utf-8").count("### Oturum"), 1)

                    # Second run with same session_id: should be no-op
                    code2 = FLUSH._flush_once(args, event_time)
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
            with mock.patch.object(FLUSH, "VAULT_ROOT", self.vault):
                with mock.patch.object(FLUSH, "STATE_DIR", self.state_dir):
                    args = FLUSH._parse_args(["--hook-input", str(hook_input_path), "--reason", "sessionend"])
                    FLUSH._flush_once(args, after_18)

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
            return True, None

        def mock_briefing_model(*args, **kwargs):
            pipeline_order.append("briefing")
            return VALID_BRIEFING_BODY, None, "custom"

        morning_time = datetime(2026, 9, 4, 8, 15)
        with mock.patch.object(BRIEFING, "_run_morning_compile", mock_compile_stage):
            result = BRIEFING.run_if_due(self.vault, morning_time, model_call=mock_briefing_model)
            self.assertTrue(result)
            self.assertEqual(pipeline_order, ["compile", "briefing"])
            briefing_file = self.briefings_dir / "2026-09-04.md"
            self.assertTrue(briefing_file.exists())

    # -------------------------------------------------------------------------
    # Scenario 17: Missed 08:00 schedule runs catch-up when available
    # -------------------------------------------------------------------------
    def test_17_missed_0800_schedule_catches_up(self):
        later_time = datetime(2026, 9, 4, 11, 45)
        with mock.patch.object(BRIEFING, "_run_morning_compile", return_value=None):
            result = BRIEFING.run_if_due(
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
        def failing_compile(*args, **kwargs):
            return False, "compile-test-error"

        morning_time = datetime(2026, 9, 4, 8, 5)
        with mock.patch.object(BRIEFING, "_run_compile_stage", failing_compile, create=True):
            result = BRIEFING.run_if_due(
                self.vault,
                morning_time,
                model_call=lambda p, c: (VALID_BRIEFING_BODY, None, "custom"),
            )
            self.assertTrue(result)
            briefing_file = self.briefings_dir / "2026-09-04.md"
            self.assertTrue(briefing_file.exists())
            health = self.state_dir / "briefing-health.json"
            if health.exists():
                data = json.loads(health.read_text(encoding="utf-8"))
                self.assertIn("compile-test-error", str(data))

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
            code, stdout = LIFECYCLE.handle_event(self.vault, "antigravity", "PreInvocation", {"session_id": "agy-cont"})
            self.assertEqual(code, 0)
            self.assertIn("Furkan", stdout)
            mock_launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
