"""Tests for Respected Brain Uninstaller (uninstall.py)."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uninstall


class TestUninstall(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="respected-uninstall-test-"))
        self.fake_home = self.tmp_dir / "home"
        self.fake_home.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_remove_global_integrations_cleans_ai_configs(self):
        # 1. Setup Antigravity
        gemini_dir = self.fake_home / ".gemini"
        gemini_config = gemini_dir / "config"
        gemini_config.mkdir(parents=True, exist_ok=True)
        (gemini_dir / "GEMINI.md").write_text(
            "# User rules\n<!-- RESPECTED-GLOBAL:BEGIN -->\n# Respected global\n<!-- RESPECTED-GLOBAL:END -->\nOther rules\n",
            encoding="utf-8",
        )
        (gemini_config / "hooks.json").write_text(
            json.dumps({
                "SessionStart": ["respected-brain-session-start", "other-tool-start"],
                "SessionEnd": ["respected-brain-session-end"],
            }),
            encoding="utf-8",
        )

        # 2. Setup Cursor
        cursor_dir = self.fake_home / ".cursor"
        cursor_rules = cursor_dir / "rules"
        cursor_rules.mkdir(parents=True, exist_ok=True)
        (cursor_rules / "respected-brain.mdc").write_text("rule", encoding="utf-8")
        (cursor_dir / "hooks.json").write_text(
            json.dumps({
                "SessionStart": ["python /path/to/respected/lifecycle.py", "custom-hook"]
            }),
            encoding="utf-8",
        )

        # 3. Setup Codex
        codex_dir = self.fake_home / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        (codex_dir / "hooks.json").write_text(
            json.dumps({
                "SessionStart": ["respected-brain"]
            }),
            encoding="utf-8",
        )

        with patch("pathlib.Path.home", return_value=self.fake_home):
            cleaned = uninstall.remove_global_integrations()

        self.assertTrue(any("Antigravity global kuralı temizlendi" in c for c in cleaned))
        self.assertTrue(any("Cursor global kuralı silindi" in c for c in cleaned))
        self.assertFalse((cursor_rules / "respected-brain.mdc").exists())

        # Check that unrelated entries survived
        gemini_md_after = (gemini_dir / "GEMINI.md").read_text(encoding="utf-8")
        self.assertIn("Other rules", gemini_md_after)
        self.assertNotIn("RESPECTED-GLOBAL", gemini_md_after)

        gemini_hooks_after = json.loads((gemini_config / "hooks.json").read_text(encoding="utf-8"))
        self.assertIn("other-tool-start", gemini_hooks_after["SessionStart"])
        self.assertNotIn("respected-brain-session-start", gemini_hooks_after["SessionStart"])

        cursor_hooks_after = json.loads((cursor_dir / "hooks.json").read_text(encoding="utf-8"))
        self.assertIn("custom-hook", cursor_hooks_after["SessionStart"])
        self.assertEqual(len(cursor_hooks_after["SessionStart"]), 1)

    def test_remove_desktop_shortcuts(self):
        desktop = self.fake_home / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        sc1 = desktop / "RespectedOS.url"
        sc1.write_text("[InternetShortcut]\nURL=obsidian://...", encoding="utf-8")
        sc2 = desktop / "CustomBrain.url"
        sc2.write_text("[InternetShortcut]\nURL=obsidian://...", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=self.fake_home):
            cleaned = uninstall.remove_desktop_shortcuts(vault_name="CustomBrain")

        self.assertFalse(sc1.exists())
        self.assertFalse(sc2.exists())
        self.assertEqual(len(cleaned), 2)

    def test_remove_mcp_config(self):
        claude_dir = self.fake_home / "AppData" / "Roaming" / "Claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = claude_dir / "claude_desktop_config.json"
        cfg_file.write_text(
            json.dumps({
                "mcpServers": {
                    "respected-vault-mcp": {"command": "python", "args": ["mcp"]},
                    "other-server": {"command": "node", "args": ["server.js"]},
                }
            }),
            encoding="utf-8",
        )

        with patch("pathlib.Path.home", return_value=self.fake_home):
            cleaned = uninstall.remove_mcp_config()

        self.assertTrue(len(cleaned) >= 1)
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        self.assertNotIn("respected-vault-mcp", data["mcpServers"])
        self.assertIn("other-server", data["mcpServers"])


    def test_main_non_interactive_purge(self):
        vault_to_purge = self.tmp_dir / "PurgeVault"
        vault_to_purge.mkdir(parents=True, exist_ok=True)
        (vault_to_purge / "note.md").write_text("hello", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=self.fake_home):
            code = uninstall.main(["--non-interactive", "--purge-vault", "--vault-path", str(vault_to_purge)])

        self.assertEqual(code, 0)
        self.assertFalse(vault_to_purge.exists())

    def test_clean_hooks_formats(self):
        gemini_config = self.fake_home / ".gemini" / "config"
        gemini_config.mkdir(parents=True, exist_ok=True)
        hooks_format3 = gemini_config / "hooks.json"
        hooks_format3.write_text(
            json.dumps({
                "respected-brain": {
                    "PreInvocation": [{"type": "command", "command": "python3 bridge.py"}]
                }
            }),
            encoding="utf-8",
        )

        codex_dir = self.fake_home / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        hooks_format2 = codex_dir / "hooks.json"
        hooks_format2.write_text(
            json.dumps({
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 /path/bridge.py --provider codex",
                                }
                            ]
                        }
                    ]
                }
            }),
            encoding="utf-8",
        )

        with patch("pathlib.Path.home", return_value=self.fake_home):
            cleaned = uninstall.remove_global_integrations()

        self.assertFalse(hooks_format3.exists())
        self.assertFalse(hooks_format2.exists())
        self.assertTrue(any("tamamen temizlendi" in c for c in cleaned))

    def test_wsl_worker_flag(self):
        with patch("pathlib.Path.home", return_value=self.fake_home):
            code = uninstall.main(["--wsl-worker"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
