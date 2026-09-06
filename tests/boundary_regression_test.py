#!/usr/bin/env python3
"""Tests for boundary regressions (unsafe staging) and tracked bytecode cleanup (Faz 1)."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
COMPILE_PATH = ROOT / "template/.claude/scripts/compile.py"
UPDATE_PATH = ROOT / "scripts/update_respected.py"


def load_compile_module():
    spec = importlib.util.spec_from_file_location("compile_module", COMPILE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_update_module():
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("update_module", UPDATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BoundaryRegressionTest(unittest.TestCase):
    def setUp(self):
        self.compile = load_compile_module()
        self.update = load_update_module()

    def test_staging_inside_vault_is_rejected_before_model_call(self):
        """If temporary staging directory falls inside vault root, compile must abort immediately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            state_dir = vault_root / ".claude" / "scripts" / ".state"
            state_dir.mkdir(parents=True, exist_ok=True)
            daily_dir = vault_root / "daily"
            daily_dir.mkdir(parents=True, exist_ok=True)
            daily_file = daily_dir / "2026-09-01.md"
            daily_file.write_text("# Test Daily\n\nSome content", encoding="utf-8")
            knowledge_dir = vault_root / "knowledge"
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            (knowledge_dir / "index.md").write_text("# Index", encoding="utf-8")

            # Simulate staging created inside vault
            inside_stage = vault_root / "accidental_internal_staging"
            inside_stage.mkdir(parents=True, exist_ok=True)

            with mock.patch("tempfile.mkdtemp", return_value=str(inside_stage)), \
                 mock.patch.object(self.compile, "_run_model") as mock_model:

                with self.assertRaises(self.compile.PolicyError) as cm:
                    self.compile._prepare_stage(vault_root, state_dir, daily_file)

                self.assertIn("staging-inside-vault", str(cm.exception))
                self.assertEqual(mock_model.call_count, 0)

    def test_untrack_bytecode_and_gitignore_rules(self):
        """Updating a vault must untrack any committed .pyc or __pycache__ without deleting files on disk."""
        if shutil.which("git") is None:
            self.skipTest("git is not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            # Initialize git repo in vault
            subprocess.run(["git", "init"], cwd=vault, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=vault, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=vault, check=True, capture_output=True)

            # Create standard vault layout
            (vault / ".beyin-version").write_text("2.0.0\n", encoding="utf-8")
            (vault / ".beyin-multi-version").write_text("1.3.2\n", encoding="utf-8")
            (vault / ".beyin").mkdir(parents=True, exist_ok=True)
            (vault / ".beyin/instructions.md").write_text("# Instructions\n", encoding="utf-8")
            (vault / ".beyin/config.json").write_text('{"summary_provider": "auto", "platform": "windows-native"}\n', encoding="utf-8")

            # Create and commit bytecode files (simulating legacy/buggy vault state)
            pycache_dir = vault / ".beyin" / "__pycache__"
            pycache_dir.mkdir(parents=True, exist_ok=True)
            committed_pyc = pycache_dir / "test_module.cpython-311.pyc"
            committed_pyc.write_bytes(b"dummy bytecode")

            root_pyc = vault / "stray.pyc"
            root_pyc.write_bytes(b"dummy stray bytecode")

            gitignore = vault / ".gitignore"
            gitignore.write_text(".env\n", encoding="utf-8")

            subprocess.run(["git", "add", "."], cwd=vault, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial with bytecode"], cwd=vault, check=True, capture_output=True)

            # Verify files are tracked
            tracked_before = subprocess.run(["git", "ls-files"], cwd=vault, capture_output=True, text=True, check=True).stdout
            self.assertIn("test_module.cpython-311.pyc", tracked_before)
            self.assertIn("stray.pyc", tracked_before)

            # Ensure clean_bytecode_and_gitignore helper exists on update module
            self.assertTrue(
                hasattr(self.update, "ensure_bytecode_cleanup") or hasattr(self.update, "_ensure_bytecode_cleanup"),
                "update_respected module must provide ensure_bytecode_cleanup",
            )
            cleanup_func = getattr(self.update, "ensure_bytecode_cleanup", None) or getattr(self.update, "_ensure_bytecode_cleanup")
            cleanup_func(vault)

            # Check git index: files should NO LONGER be tracked
            tracked_after = subprocess.run(["git", "ls-files"], cwd=vault, capture_output=True, text=True, check=True).stdout
            self.assertNotIn("test_module.cpython-311.pyc", tracked_after)
            self.assertNotIn("stray.pyc", tracked_after)

            # Check disk: files must STILL EXIST on disk
            self.assertTrue(committed_pyc.exists(), "bytecode file must not be deleted from disk")
            self.assertTrue(root_pyc.exists(), "stray pyc must not be deleted from disk")

            # Check .gitignore: must contain __pycache__/ and *.pyc
            gitignore_content = gitignore.read_text(encoding="utf-8")
            self.assertIn("__pycache__/", gitignore_content)
            self.assertIn("*.pyc", gitignore_content)

    def test_prepare_config_handles_custom_python_and_resets_invalid(self):
        """Valid custom python command (e.g. pyenv shim) is preserved; invalid or empty is reset."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            (vault / ".beyin").mkdir(parents=True, exist_ok=True)
            config_file = vault / ".beyin/config.json"

            # Case 1: custom valid pyenv shim command with auto request
            config_file.write_text(
                '{"python_command": ["/home/furkan/.pyenv/shims/python3"]}\n',
                encoding="utf-8",
            )
            self.update._prepare_config(vault, "portable", "auto")
            import json
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["python_command"], ["/home/furkan/.pyenv/shims/python3"])

            # Case 2: invalid/empty command with auto request is safely reset to default
            config_file.write_text('{"python_command": []}\n', encoding="utf-8")
            self.update._prepare_config(vault, "windows-wsl", "auto")
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["python_command"], ["python3"])

            # Case 3: explicitly requested profile resets to default
            config_file.write_text(
                '{"python_command": ["custom-py"]}\n',
                encoding="utf-8",
            )
            self.update._prepare_config(vault, "windows-native", "windows-native")
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["python_command"], ["py.exe", "-3"])

    def test_install_antigravity_global_accepts_non_windows_vault_path(self):
        """install_antigravity_global must not reject Linux/POSIX vault paths where windows_path is None."""
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import install_antigravity_global

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            home = temp_path / "home"
            home.mkdir(parents=True, exist_ok=True)
            vault = ROOT / "template"

            # Before fix, windows_path returning None caused parser.error (SystemExit 2)
            # After fix, windows_path is not required, so main succeeds with return code 0
            patch_target = getattr(install_antigravity_global, "windows_path", None)
            if patch_target is not None:
                with mock.patch("install_antigravity_global.windows_path", return_value=None), \
                     mock.patch.object(sys, "argv", ["install_antigravity_global.py", str(vault), "--antigravity-home", str(home), "--apply"]):
                    exit_code = install_antigravity_global.main()
                    self.assertEqual(exit_code, 0)
                    self.assertTrue((home / ".gemini/config/hooks.json").is_file())
            else:
                with mock.patch.object(sys, "argv", ["install_antigravity_global.py", str(vault), "--antigravity-home", str(home), "--apply"]):
                    exit_code = install_antigravity_global.main()
                    self.assertEqual(exit_code, 0)
                    self.assertTrue((home / ".gemini/config/hooks.json").is_file())


if __name__ == "__main__":
    unittest.main()
