#!/usr/bin/env python3
"""Tests for generated multi-AI adapters and safe migration."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
import io


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MultiAITest(unittest.TestCase):
    def test_generated_files_have_no_drift(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_integrations.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_provider_configs_point_to_bridge(self):
        codex = json.loads((ROOT / "template/.codex/hooks.json").read_text())
        cursor = json.loads((ROOT / "template/.cursor/hooks.json").read_text())
        antigravity = json.loads((ROOT / "template/.agents/hooks.json").read_text())
        self.assertIn(".beyin/hooks/bridge.py", json.dumps(codex))
        self.assertIn(".beyin/hooks/bridge.py", json.dumps(cursor))
        self.assertIn(".beyin/hooks/bridge.py", json.dumps(antigravity))

    def test_bridge_normalizes_provider_inputs_and_outputs(self):
        bridge = load("bridge", ROOT / "template/.beyin/hooks/bridge.py")
        normalized = bridge.normalize("antigravity", {
            "conversationId": "abc", "transcriptPath": "/tmp/t.jsonl",
            "workspacePaths": ["/tmp/project"], "modelName": "gemini-test",
        })
        self.assertEqual(normalized["session_id"], "abc")
        self.assertEqual(normalized["transcript_path"], "/tmp/t.jsonl")
        self.assertEqual(normalized["cwd"], "/tmp/project")
        self.assertEqual(normalized["beyin_provider"], "antigravity")
        captured = io.StringIO()
        with redirect_stdout(captured):
            bridge.output("antigravity", "end", "")
        self.assertEqual(json.loads(captured.getvalue()), {"decision": "stop"})

    def test_runner_has_windows_user_local_agy_discovery(self):
        runner = (ROOT / "template/.beyin/model_runner.py").read_text(encoding="utf-8")
        self.assertIn('"AppData" / "Local" / "agy" / "bin" / "agy.exe"', runner)

    def test_canonical_skills_are_identical_for_all_agents(self):
        canonical_root = ROOT / "template/.beyin/skills"
        for source in sorted(canonical_root.glob("*/SKILL.md")):
            content = source.read_bytes()
            name = source.parent.name
            self.assertEqual(
                content,
                (ROOT / "template/.agents/skills" / name / "SKILL.md").read_bytes(),
            )
            self.assertEqual(
                content,
                (ROOT / "template/.claude/skills" / name / "SKILL.md").read_bytes(),
            )

    def test_global_antigravity_installer_preserves_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "windows-user"
            config = home / ".gemini/config"
            config.mkdir(parents=True)
            (config / "hooks.json").write_text(
                json.dumps({"my-existing-hook": {"enabled": True}}),
                encoding="utf-8",
            )
            (home / ".gemini/GEMINI.md").write_text(
                "# Kendi global kuralım\n",
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(ROOT / "scripts/install_antigravity_global.py"),
                str(ROOT / "template"),
                "--antigravity-home",
                str(home),
                "--apply",
            ]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            hooks = json.loads((config / "hooks.json").read_text(encoding="utf-8"))
            self.assertIn("my-existing-hook", hooks)
            self.assertIn("respot-brain", hooks)
            rule = (home / ".gemini/GEMINI.md").read_text(encoding="utf-8")
            self.assertIn("# Kendi global kuralım", rule)
            self.assertEqual(rule.count("<!-- RESPOT-GLOBAL:BEGIN -->"), 1)
            for source in sorted((ROOT / "template/.beyin/skills").glob("*/SKILL.md")):
                installed = config / "skills" / source.parent.name / "SKILL.md"
                self.assertEqual(source.read_bytes(), installed.read_bytes())
            snapshot = {
                path.relative_to(home): path.read_bytes()
                for path in home.rglob("*")
                if path.is_file() and "respot-backups" not in path.parts
            }
            second = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            repeated = {
                path.relative_to(home): path.read_bytes()
                for path in home.rglob("*")
                if path.is_file() and "respot-backups" not in path.parts
            }
            self.assertEqual(snapshot, repeated)

    def test_installer_preserves_personalized_instruction_as_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            vault.mkdir()
            (vault / ".beyin-version").write_text("2.0.0\n", encoding="utf-8")
            (vault / "CLAUDE.md").write_text("# AdaOS\n\nKişisel talimat.\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/enable_multiai.py"), str(vault), "--platform", "windows-wsl", "--apply"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            canonical = (vault / ".beyin/instructions.md").read_text(encoding="utf-8")
            self.assertEqual(canonical, "# AdaOS\n\nKişisel talimat.\n")
            self.assertIn(canonical, (vault / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertTrue((vault / ".codex/hooks.json").is_file())
            self.assertTrue((vault / ".cursor/hooks.json").is_file())
            self.assertTrue((vault / ".agents/hooks.json").is_file())
            antigravity = (vault / ".agents/hooks.json").read_text(encoding="utf-8")
            self.assertIn("wsl.exe --cd", antigravity)
            codex = json.loads((vault / ".codex/hooks.json").read_text(encoding="utf-8"))
            self.assertIn("commandWindows", json.dumps(codex))


if __name__ == "__main__":
    unittest.main(verbosity=2)
