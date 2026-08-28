#!/usr/bin/env python3
"""Behavior tests for deterministic multi-platform adapter rendering."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RENDER_PATH = ROOT / "scripts" / "render_integrations.py"


def load_renderer():
    spec = importlib.util.spec_from_file_location("respot_profile_renderer", RENDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load renderer: {RENDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RENDER = load_renderer()


class ProfileRenderTest(unittest.TestCase):
    def test_native_bridge_argv_preserves_a_spaced_windows_vault_as_one_argument(self):
        profile = RENDER.Profile("windows-native", ("py.exe", "-3"))

        argv = RENDER.bridge_argv(
            profile,
            PureWindowsPath(r"C:\Users\Ada\Ada Brain"),
            "codex",
            "start",
        )

        self.assertEqual(
            argv,
            [
                "py.exe",
                "-3",
                r"C:\Users\Ada\Ada Brain\.beyin\hooks\bridge.py",
                "--provider",
                "codex",
                "--event",
                "start",
            ],
        )

    def test_each_profile_renders_explicit_config_and_all_provider_adapters(self):
        cases = {
            "portable": {"required": "python3", "forbidden": ()},
            "windows-wsl": {"required": "wsl.exe --cd", "forbidden": ()},
            "windows-native": {
                "required": "py.exe",
                "forbidden": ("wsl.exe", "/mnt/", ".sh", "bash"),
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for name, expected in cases.items():
                vault = base / f"{name} Brain"
                shutil.copytree(ROOT / "template", vault)

                result = subprocess.run(
                    [
                        sys.executable,
                        str(RENDER_PATH),
                        "--root",
                        str(vault),
                        "--platform",
                        name,
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                config = json.loads((vault / ".beyin/config.json").read_text(encoding="utf-8"))
                self.assertEqual(config["platform"], name)
                self.assertIsInstance(config["python_command"], list)
                artifacts = {
                    "claude": json.loads((vault / ".claude/settings.json").read_text(encoding="utf-8")),
                    "codex": json.loads((vault / ".codex/hooks.json").read_text(encoding="utf-8")),
                    "cursor": json.loads((vault / ".cursor/hooks.json").read_text(encoding="utf-8")),
                    "antigravity": json.loads((vault / ".agents/hooks.json").read_text(encoding="utf-8")),
                }
                combined = json.dumps(artifacts, ensure_ascii=False)
                self.assertIn(expected["required"], combined)
                for forbidden in expected["forbidden"]:
                    self.assertNotIn(forbidden, combined)
                if name == "windows-native":
                    self.assertIn("--provider claude", combined)
                else:
                    self.assertIn(".claude/hooks/session-start.sh", combined)
                self.assertIn("--provider codex", combined)
                self.assertIn("--provider cursor", combined)
                self.assertIn("--provider antigravity", combined)

    def test_render_check_uses_the_persisted_profile_without_mutating_the_vault(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "Persisted Brain"
            shutil.copytree(ROOT / "template", vault)
            first = subprocess.run(
                [sys.executable, str(RENDER_PATH), "--root", str(vault), "--platform", "windows-native"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            before = {path.relative_to(vault): path.read_bytes() for path in vault.rglob("*") if path.is_file()}

            checked = subprocess.run(
                [sys.executable, str(RENDER_PATH), "--root", str(vault), "--check"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            after = {path.relative_to(vault): path.read_bytes() for path in vault.rglob("*") if path.is_file()}
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
