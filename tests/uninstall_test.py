"""Tests for Respected Brain Uninstaller (uninstall.py)."""

from __future__ import annotations

import ast
import contextlib
import io
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
if str(ROOT / "installer") not in sys.path:
    sys.path.insert(0, str(ROOT / "installer"))

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
        (gemini_dir / "settings.json").write_text(
            json.dumps({
                "theme": "custom",
                "hooks": {
                    "AfterAgent": [
                        {"hooks": [
                            {"type": "command", "command": "python bridge.py --global-hook --provider gemini"},
                            {"type": "command", "command": "other-tool"},
                        ]}
                    ]
                },
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
        original_notify = ["custom-notify", "turn-ended"]
        (codex_dir / "config.toml").write_text(
            'notify = ["python3", "/vault/.beyin/hooks/codex_notify.py", "--chain-file", "chain.json"]\nmodel = "gpt-test"\n',
            encoding="utf-8",
        )
        (codex_dir / "respected-notify-chain.json").write_text(
            json.dumps({"argv": original_notify}), encoding="utf-8"
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

        gemini_settings_after = json.loads((gemini_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(gemini_settings_after["theme"], "custom")
        self.assertEqual(
            gemini_settings_after["hooks"]["AfterAgent"][0]["hooks"],
            [{"type": "command", "command": "other-tool"}],
        )

        cursor_hooks_after = json.loads((cursor_dir / "hooks.json").read_text(encoding="utf-8"))
        self.assertIn("custom-hook", cursor_hooks_after["SessionStart"])
        self.assertEqual(len(cursor_hooks_after["SessionStart"]), 1)
        codex_config_after = (codex_dir / "config.toml").read_text(encoding="utf-8")
        self.assertIn('notify = ["custom-notify", "turn-ended"]', codex_config_after)
        self.assertIn('model = "gpt-test"', codex_config_after)
        self.assertFalse((codex_dir / "respected-notify-chain.json").exists())

    def test_remove_global_integrations_removes_managed_codex_notify_without_chain(self):
        codex = self.fake_home / ".codex"
        codex.mkdir(parents=True)
        config = codex / "config.toml"
        config.write_text(
            'notify = ["python3", "/vault/.beyin/hooks/codex_notify.py"]\nmodel = "gpt-test"\n',
            encoding="utf-8",
        )

        with patch("pathlib.Path.home", return_value=self.fake_home):
            uninstall.remove_global_integrations(clean_wsl=False)

        content = config.read_text(encoding="utf-8")
        self.assertNotIn("notify =", content)
        self.assertIn('model = "gpt-test"', content)

    def test_remove_global_integrations_preserves_outer_codex_notify_wrapper(self):
        codex = self.fake_home / ".codex"
        codex.mkdir(parents=True)
        config = codex / "config.toml"
        outer_notify = [
            "codex-computer-use.exe",
            "turn-ended",
            "--previous-notify",
            '["py.exe","-3","C:\\\\Vault\\\\.beyin\\\\hooks\\\\codex_notify.py"]',
        ]
        config.write_text(
            "notify = " + json.dumps(outer_notify) + '\n\nmodel = "gpt-test"\n',
            encoding="utf-8",
        )

        with patch("pathlib.Path.home", return_value=self.fake_home):
            uninstall.remove_global_integrations(clean_wsl=False)

        content = config.read_text(encoding="utf-8")
        self.assertIn("notify = ", content)
        notify_literal = content.split("notify = ", 1)[1].splitlines()[0]
        self.assertEqual(
            ast.literal_eval(notify_literal),
            ["codex-computer-use.exe", "turn-ended"],
        )
        self.assertEqual(
            content,
            'notify = ["codex-computer-use.exe", "turn-ended"]\n\nmodel = "gpt-test"\n',
        )

    def test_remove_desktop_shortcuts(self):
        desktop = self.fake_home / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        sc1 = desktop / "RespectedOS.url"
        sc1.write_text("[InternetShortcut]\nURL=obsidian://...", encoding="utf-8")
        sc2 = desktop / "CustomBrain.url"
        sc2.write_text("[InternetShortcut]\nURL=obsidian://...", encoding="utf-8")
        sc3 = desktop / "CustomBrain.webloc"
        sc3.write_text("plist", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=self.fake_home):
            cleaned = uninstall.remove_desktop_shortcuts(vault_name="CustomBrain")

        self.assertFalse(sc1.exists())
        self.assertFalse(sc2.exists())
        self.assertFalse(sc3.exists())
        self.assertEqual(len(cleaned), 3)

    def test_remove_scheduled_tasks_deletes_current_and_legacy_prefixed_tasks(self):
        legacy_prefix = "res" + "pot-morning-briefing-"
        query = type(
            "Result",
            (),
            {
                "stdout": (
                    '"\\\\respected-morning-briefing-current","N/A","Ready"\n'
                    f'"\\\\{legacy_prefix}legacy","N/A","Ready"\n'
                    '"\\\\Unrelated User Task","N/A","Ready"\n'
                ),
                "returncode": 0,
            },
        )()
        deleted = type("Result", (), {"stdout": b"", "stderr": b"", "returncode": 0})()

        with (
            patch("uninstall.os.name", "nt"),
            patch("uninstall.subprocess.run", side_effect=[query, deleted, deleted]) as run,
        ):
            cleaned = uninstall.remove_scheduled_tasks()

        self.assertEqual(len(cleaned), 2)
        delete_calls = [call.args[0] for call in run.call_args_list[1:]]
        self.assertEqual(
            delete_calls,
            [
                ["schtasks.exe", "/Delete", "/TN", "\\\\respected-morning-briefing-current", "/F"],
                ["schtasks.exe", "/Delete", "/TN", f"\\\\{legacy_prefix}legacy", "/F"],
            ],
        )

    def test_main_uses_vault_name_for_shortcut_cleanup(self):
        desktop = self.fake_home / "Desktop"
        desktop.mkdir(parents=True)
        shortcut = desktop / "CustomBrain.url"
        shortcut.write_text("[InternetShortcut]\nURL=obsidian://open?vault=CustomBrain\n", encoding="utf-8")
        vault = self.tmp_dir / "CustomBrain"
        vault.mkdir()

        with (
            patch("pathlib.Path.home", return_value=self.fake_home),
            patch("uninstall.remove_global_integrations", return_value=[]),
            patch("uninstall.remove_scheduled_tasks", return_value=[]),
            patch("uninstall.remove_mcp_config", return_value=[]),
        ):
            code = uninstall.main(
                ["--non-interactive", "--vault-path", str(vault)]
            )

        self.assertEqual(code, 0)
        self.assertFalse(shortcut.exists())

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

    def test_main_purge_fails_when_vault_still_exists_after_tree_removal(self):
        vault_to_purge = self.tmp_dir / "StubbornVault"
        vault_to_purge.mkdir(parents=True)
        (vault_to_purge / "locked.txt").write_text("locked", encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("pathlib.Path.home", return_value=self.fake_home),
            patch("uninstall.remove_global_integrations", return_value=[]),
            patch("uninstall.remove_scheduled_tasks", return_value=[]),
            patch("uninstall.remove_desktop_shortcuts", return_value=[]),
            patch("uninstall.remove_mcp_config", return_value=[]),
            patch("uninstall.shutil.rmtree", return_value=None),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = uninstall.main(
                ["--non-interactive", "--purge-vault", "--vault-path", str(vault_to_purge)]
            )

        self.assertEqual(code, 1)
        self.assertTrue(vault_to_purge.exists())
        self.assertIn("silinemedi", stderr.getvalue().lower())
        self.assertNotIn("tamamen silindi", stdout.getvalue().lower())

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
