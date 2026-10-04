#!/usr/bin/env python3
"""Cross-platform/provider behavior matrix for the advertised 0.0.1 contract."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


from unittest import mock
from respectedbrain.integrations.backend import IntegrationProfile
from respectedbrain.integrations import rendering as RENDERER
from tests.foundation_integrations_test import IntegrationFixture
ROOT = Path(__file__).resolve().parents[1]

class ScenarioMatrixTest(IntegrationFixture, unittest.TestCase):
    TARGET_PROFILES = {"windows-native": "windows-native", "wsl": "posix", "hybrid": "windows-wsl", "linux": "posix", "macos": "posix"}

    def test_orchestrator_never_calls_skipped_hosts_golden(self):
        source = (ROOT / "tests/run_all.py").read_text(encoding="utf-8")
        self.assertNotIn("Golden Standard Sağlandı", source)
        self.assertIn("NOT VERIFIED", source)

    def render_target(self, target):
        vault = self.vault / target
        vault.mkdir()
        platform = self.TARGET_PROFILES[target]
        launcher = self.profile.launcher if platform == "windows-native" else ("/opt/respectedbrain/respectedbrain",)
        profile = IntegrationProfile(platform, launcher, self.home)
        with mock.patch.object(RENDERER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=self.wsl_registry_output())):
            output = RENDERER.render_project_integrations(self.ctx, profile)
        for relative, value in output.items():
            destination = vault / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(value)
        return vault, None

    def global_output(self, path):
        changes = RENDERER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        return json.loads(next(row.after for row in changes if row.key == str(self.home / path)))

    def test_every_advertised_target_renders_real_provider_adapters(self):
        for target in self.TARGET_PROFILES:
            with self.subTest(target=target):
                vault, _ = self.render_target(target)
                for relative in (".claude/settings.json", ".codex/hooks.json", ".cursor/hooks.json", ".agents/hooks.json", ".gemini/settings.json"):
                    payload = json.loads((vault / relative).read_text(encoding="utf-8"))
                    self.assertIsInstance(payload, dict)
                    self.assertIn(self.ctx.paths.vault_id, json.dumps(payload))

    def test_gemini_project_adapter_uses_after_agent_and_strict_json_schema(self):
        vault, temporary = self.render_target("linux")
        settings = json.loads((vault / ".gemini/settings.json").read_text(encoding="utf-8"))
        handler = settings["hooks"]["AfterAgent"][0]["hooks"][0]
        self.assertIn("--provider gemini", handler["command"])
        self.assertIn("--event turn", handler["command"])
        self.assertEqual(set(handler), {"name", "type", "command", "timeout", "description"})

    def test_claude_uses_stop_for_per_turn_logging(self):
        vault, temporary = self.render_target("linux")
        settings = json.loads((vault / ".claude/settings.json").read_text(encoding="utf-8"))

        stop = settings["hooks"].get("Stop")

        self.assertIsInstance(stop, list)
        command = stop[0]["hooks"][0]
        self.assertTrue(command.get("async"), command)

    def test_cursor_uses_after_agent_response_for_per_turn_logging(self):
        vault, temporary = self.render_target("linux")
        hooks = json.loads((vault / ".cursor/hooks.json").read_text(encoding="utf-8"))["hooks"]

        per_turn = hooks.get("afterAgentResponse")

        self.assertIsInstance(per_turn, list)
        self.assertIn("--event turn", per_turn[0]["command"])

    def test_antigravity_uses_stop_for_per_turn_logging(self):
        vault, temporary = self.render_target("linux")
        hooks = json.loads((vault / ".agents/hooks.json").read_text(encoding="utf-8"))

        stop = hooks["respected-brain"].get("Stop")

        self.assertIsInstance(stop, list)
        self.assertIn("--event turn", stop[0]["command"])

    def test_codex_global_config_uses_notify_for_per_turn_logging(self):
        notify = RENDERER.bridge_argv(self.ctx, self.profile, "codex", "notify")
        self.assertEqual(notify, [*self.profile.launcher, "hook", "--vault-id", self.ctx.paths.vault_id, "--provider", "codex", "--event", "notify"])
        self.assertFalse(any(value.endswith(".py") for value in notify))

    def test_gemini_global_install_uses_after_agent_for_per_turn_logging(self):
        settings = self.global_output(".gemini/settings.json")
        handler = settings["hooks"]["AfterAgent"][0]["hooks"][0]
        self.assertIn("--provider gemini", handler["command"])
        self.assertIn("--event turn", handler["command"])
        self.assertEqual(set(handler), {"name", "type", "command", "timeout", "description"})

    def test_claude_global_stop_hook_is_async(self):
        settings = self.global_output(".claude/settings.json")
        self.assertTrue(settings["hooks"]["Stop"][0]["hooks"][0].get("async"))


class PythonSuiteDiagnosticsTest(unittest.TestCase):
    def load_orchestrator(self):
        spec = importlib.util.spec_from_file_location('test_orchestrator', ROOT / 'tests/run_all.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_python_only_runs_discovery_without_native_payload_and_reports_public_test_id(self):
        tool = self.load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            (fixture / 'tests').mkdir()
            (fixture / 'tests/diagnostic_test.py').write_text(
                "import unittest\nclass Fixture(unittest.TestCase):\n"
                "    def test_failure(self):\n        self.fail('ordinary traceback sentinel')\n",
                encoding='utf-8')
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.object(tool, 'ROOT', fixture), mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = tool.main(['--python-only'])
            self.assertEqual(status, 1)
            annotations = [line for line in stdout.getvalue().splitlines() if line.startswith('::error')]
            self.assertEqual(annotations, ['::error title=Python unittest failure::test=diagnostic_test.Fixture.test_failure'])
            self.assertNotIn('Required Native Distribution', stdout.getvalue())
            self.assertIn('ordinary traceback sentinel', stderr.getvalue())
            self.assertIn('Ran 1 test', stderr.getvalue())

    def test_more_than_ten_failures_share_one_safe_annotation(self):
        tool = self.load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            (fixture / 'tests').mkdir()
            source = "import unittest\nclass Fixture(unittest.TestCase):\n"
            for number in range(12):
                source += f"    def test_failure_{number:02d}(self):\n        self.fail('private failure payload')\n"
            (fixture / 'tests/many_test.py').write_text(source, encoding='utf-8')
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.object(tool, 'ROOT', fixture), mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = tool.main(['--python-only'])
            self.assertEqual(status, 1)
            annotations = [line for line in stdout.getvalue().splitlines() if line.startswith('::error')]
            self.assertEqual(len(annotations), 1, 'GitHub drops diagnostics beyond ten error annotations per step')
            for number in range(12):
                self.assertIn(f'test=many_test.Fixture.test_failure_{number:02d}', annotations[0])
            self.assertNotIn('private failure payload', annotations[0])
            self.assertIn('Ran 12 tests', stderr.getvalue())

    def test_python310_class_header_is_normalized_to_public_test_id(self):
        tool = self.load_orchestrator()
        output = (
            "ERROR: test_legacy (fixture_test.OldCase)\n"
            "FAIL: test_legacy (fixture_test.OldCase) (private='value')\n"
            "AssertionError: private exception payload\n"
        )
        self.assertEqual(tool.failed_test_ids(output), ['fixture_test.OldCase.test_legacy'])

    def test_failure_identifiers_reject_nonpublic_header_data(self):
        tool = self.load_orchestrator()
        output = (
            "FAIL: test_good (fixture_test.Case.test_good) (payload='private subtest value')\n"
            "ERROR: test_good (fixture_test.Case.test_good)\n"
            "FAIL: test_bad (/private/path/fixture_test.Case.test_bad)\n"
            "ERROR: test_bad (fixture_test.Case.test_bad%0A::error)\n"
            "FAIL: test_bad (fixture_test.Case.test_bad,private=value)\n"
            "FAIL: test_bad (fixture_test.Case.other_method)\n"
            "AssertionError: private exception payload\n"
            "UNEXPECTED SUCCESS: test_surprise (fixture_test.Case.test_surprise)\n"
        )
        self.assertEqual(tool.failed_test_ids(output), ['fixture_test.Case.test_good', 'fixture_test.Case.test_surprise'])


if __name__ == "__main__":
    unittest.main()
