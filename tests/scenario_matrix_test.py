#!/usr/bin/env python3
"""Cross-platform/provider behavior matrix for the advertised 0.0.1 contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
RENDER = (ROOT / "runtime/scripts/render_integrations.py") if (ROOT / "runtime/scripts/render_integrations.py").is_file() else (ROOT / "scripts/render_integrations.py")
GLOBAL_INSTALL = (ROOT / "runtime/scripts/install_global.py") if (ROOT / "runtime/scripts/install_global.py").is_file() else (ROOT / "scripts/install_global.py")


def load_renderer():
    spec = importlib.util.spec_from_file_location("scenario_renderer", RENDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load renderer: {RENDER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RENDERER = load_renderer()


class ScenarioMatrixTest(unittest.TestCase):
    TARGET_PROFILES = {
        "windows-native": "windows-native",
        "wsl": "portable",
        "hybrid": "windows-wsl",
        "linux": "portable",
        "macos": "portable",
    }

    def test_orchestrator_never_calls_skipped_hosts_golden(self):
        source = (ROOT / "tests/run_all.py").read_text(encoding="utf-8")
        self.assertNotIn("Golden Standard Sağlandı", source)
        self.assertIn("NOT VERIFIED", source)

    def render_target(self, target: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        vault = Path(temporary.name) / f"{target} Furkan'ın 🧠 Brain"
        shutil.copytree(ROOT / "template", vault)
        result = subprocess.run(
            [
                PYTHON,
                str(RENDER),
                "--root",
                str(vault),
                "--platform",
                self.TARGET_PROFILES[target],
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return vault, temporary

    def test_every_advertised_target_renders_real_provider_adapters(self):
        for target in self.TARGET_PROFILES:
            with self.subTest(target=target):
                vault, temporary = self.render_target(target)
                self.addCleanup(temporary.cleanup)
                for relative in (
                    ".claude/settings.json",
                    ".codex/hooks.json",
                    ".cursor/hooks.json",
                    ".agents/hooks.json",
                    ".gemini/settings.json",
                ):
                    payload = json.loads((vault / relative).read_text(encoding="utf-8"))
                    self.assertIsInstance(payload, dict)

    def test_gemini_project_adapter_uses_after_agent_and_strict_json_schema(self):
        vault, temporary = self.render_target("linux")
        self.addCleanup(temporary.cleanup)
        settings = json.loads((vault / ".gemini/settings.json").read_text(encoding="utf-8"))
        handler = settings["hooks"]["AfterAgent"][0]["hooks"][0]
        self.assertIn("--provider gemini", handler["command"])
        self.assertIn("--event turn", handler["command"])
        self.assertEqual(set(handler), {"name", "type", "command", "timeout", "description"})

    def test_claude_uses_stop_for_per_turn_logging(self):
        vault, temporary = self.render_target("linux")
        self.addCleanup(temporary.cleanup)
        settings = json.loads((vault / ".claude/settings.json").read_text(encoding="utf-8"))

        stop = settings["hooks"].get("Stop")

        self.assertIsInstance(stop, list)
        command = stop[0]["hooks"][0]
        self.assertTrue(command.get("async"), command)

    def test_cursor_uses_after_agent_response_for_per_turn_logging(self):
        vault, temporary = self.render_target("linux")
        self.addCleanup(temporary.cleanup)
        hooks = json.loads((vault / ".cursor/hooks.json").read_text(encoding="utf-8"))["hooks"]

        per_turn = hooks.get("afterAgentResponse")

        self.assertIsInstance(per_turn, list)
        self.assertIn("--event turn", per_turn[0]["command"])

    def test_antigravity_uses_stop_for_per_turn_logging(self):
        vault, temporary = self.render_target("linux")
        self.addCleanup(temporary.cleanup)
        hooks = json.loads((vault / ".agents/hooks.json").read_text(encoding="utf-8"))

        stop = hooks["respected-brain"].get("Stop")

        self.assertIsInstance(stop, list)
        self.assertIn("--event turn", stop[0]["command"])

    def test_codex_global_config_uses_notify_for_per_turn_logging(self):
        argv = RENDERER.Profile("portable", (PYTHON,))
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            shutil.copytree(ROOT / "template", vault)
            script = GLOBAL_INSTALL
            spec = importlib.util.spec_from_file_location("scenario_global", script)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            notify = module.codex_notify_argv(vault, argv.name)

            self.assertEqual(notify[-1], str(vault / ".beyin/hooks/codex_notify.py"))

    def test_gemini_global_install_uses_after_agent_for_per_turn_logging(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "vault"
            home = base / "home"
            shutil.copytree(ROOT / "template", vault)
            home.mkdir()

            result = subprocess.run(
                [
                    PYTHON,
                    str(GLOBAL_INSTALL),
                    str(vault),
                    "--home",
                    str(home),
                    "--providers",
                    "gemini",
                    "--platform",
                    "portable",
                    "--apply",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            settings = json.loads((home / ".gemini/settings.json").read_text(encoding="utf-8"))
            after_agent = settings["hooks"].get("AfterAgent")
            self.assertIsInstance(after_agent, list)
            handler = after_agent[0]["hooks"][0]
            self.assertIn("--provider gemini", handler["command"])
            self.assertIn("--event turn", handler["command"])
            self.assertEqual(
                set(handler),
                {"name", "type", "command", "timeout", "description"},
            )

    def test_claude_global_stop_hook_is_async(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "vault"
            home = base / "home"
            shutil.copytree(ROOT / "template", vault)
            home.mkdir()

            result = subprocess.run(
                [
                    PYTHON,
                    str(GLOBAL_INSTALL),
                    str(vault),
                    "--home",
                    str(home),
                    "--providers",
                    "claude",
                    "--platform",
                    "portable",
                    "--apply",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            settings = json.loads((home / ".claude/settings.json").read_text(encoding="utf-8"))
            stop_handler = settings["hooks"]["Stop"][0]["hooks"][0]
            self.assertTrue(stop_handler.get("async"), stop_handler)


if __name__ == "__main__":
    unittest.main()
