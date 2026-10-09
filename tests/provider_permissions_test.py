"""Tests for provider runner permissions, sandbox flags, bypass avoidance, and safety contracts."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from respectedbrain.core.context import AppContext, AppPaths
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.providers.runner import (
    _command,
    _find_executable,
    run_model,
    ModelRunner,
)


class ProviderPermissionsAndBoundariesTest(unittest.TestCase):
    def test_no_provider_uses_permission_bypass_flags(self):
        """No provider invocation may contain dangerous bypass flags such as --dangerously-skip-permissions, --dangerously-bypass-approvals-and-sandbox, --yolo, or --force."""
        forbidden_flags = {
            "--dangerously-skip-permissions",
            "--dangerously-bypass-approvals-and-sandbox",
            "--yolo",
            "-y",
            "--force",
            "bypassPermissions",
        }

        with patch("respectedbrain.providers.runner._find_executable", return_value="dummy-cli"):
            for provider in ("claude", "codex", "antigravity", "gemini"):
                for mode in ("text", "workspace"):
                    inv = _command(provider, "test prompt", mode=mode)
                    if inv is None:
                        continue
                    argv_str = " ".join(inv.argv)
                    for flag in forbidden_flags:
                        self.assertNotIn(
                            flag,
                            inv.argv,
                            f"Provider {provider} in mode {mode} contains forbidden bypass flag {flag}: {argv_str}",
                        )
                        self.assertNotIn(
                            flag,
                            argv_str,
                            f"Provider {provider} in mode {mode} contains forbidden bypass text {flag}: {argv_str}",
                        )

    def test_antigravity_enforces_sandbox_in_both_modes_without_bypass(self):
        """Antigravity must use --sandbox in text and workspace modes, and never use --dangerously-skip-permissions."""
        with patch("respectedbrain.providers.runner._find_executable", return_value="C:/path/agy.exe"):
            text_inv = _command("antigravity", "hello", mode="text")
            self.assertIsNotNone(text_inv)
            self.assertIn("--sandbox", text_inv.argv)
            self.assertNotIn("--dangerously-skip-permissions", text_inv.argv)

            ws_inv = _command("antigravity", "hello", mode="workspace")
            self.assertIsNotNone(ws_inv)
            self.assertIn("--sandbox", ws_inv.argv)
            self.assertIn("--mode", ws_inv.argv)
            self.assertIn("accept-edits", ws_inv.argv)
            self.assertNotIn("--dangerously-skip-permissions", ws_inv.argv)

    def test_gemini_uses_safe_modes_and_no_bypass(self):
        """Gemini must use --sandbox and approval modes (plan in text, auto_edit in workspace) without bypass flags."""
        with patch("respectedbrain.providers.runner._find_executable", return_value="C:/path/gemini.cmd"):
            text_inv = _command("gemini", "hello", mode="text")
            self.assertIsNotNone(text_inv)
            self.assertEqual(text_inv.argv, ["C:/path/gemini.cmd", "--sandbox", "--approval-mode", "plan", "--output-format", "json", "-p", ""])
            self.assertNotIn("-y", text_inv.argv)
            self.assertNotIn("--yolo", text_inv.argv)

            ws_inv = _command("gemini", "hello", mode="workspace")
            self.assertIsNotNone(ws_inv)
            self.assertIn("--sandbox", ws_inv.argv)
            self.assertIn("--approval-mode", ws_inv.argv)
            self.assertIn("auto_edit", ws_inv.argv)
            self.assertNotIn("-y", ws_inv.argv)
            self.assertNotIn("--yolo", ws_inv.argv)

    def test_codex_enforces_read_only_in_text_and_workspace_write_in_workspace(self):
        """Codex must strictly bind sandbox modes based on execution mode."""
        with patch("respectedbrain.providers.runner._find_executable", return_value="C:/path/codex.exe"):
            text_inv = _command("codex", "hello", mode="text")
            self.assertIsNotNone(text_inv)
            idx = text_inv.argv.index("--sandbox")
            self.assertEqual(text_inv.argv[idx + 1], "read-only")

            ws_inv = _command("codex", "hello", mode="workspace")
            self.assertIsNotNone(ws_inv)
            idx = ws_inv.argv.index("--sandbox")
            self.assertEqual(ws_inv.argv[idx + 1], "workspace-write")

    def test_claude_disables_tools_in_text_mode_and_restricts_tools_in_workspace(self):
        """Claude must disable all tools in text mode (--tools \"\") and restrict to workspace edits in workspace mode."""
        with patch("respectedbrain.providers.runner._find_executable", return_value="C:/path/claude.cmd"):
            text_inv = _command("claude", "hello", mode="text")
            self.assertIsNotNone(text_inv)
            self.assertIn("--safe-mode", text_inv.argv)
            idx = text_inv.argv.index("--tools")
            self.assertEqual(text_inv.argv[idx + 1], "")

            ws_inv = _command("claude", "hello", mode="workspace")
            self.assertIsNotNone(ws_inv)
            self.assertIn("--safe-mode", ws_inv.argv)
            self.assertIn("--permission-mode", ws_inv.argv)
            self.assertIn("acceptEdits", ws_inv.argv)
            ws_tools_idx = ws_inv.argv.index("--tools")
            self.assertEqual(ws_inv.argv[ws_tools_idx + 1], "Read,Write,Edit,Glob,Grep")

    def test_custom_command_rejects_dangerous_bypass_flags(self):
        """Custom command lacks a verified process isolation boundary and must be rejected before launch."""
        paths = AppPaths(
            app_root=Path("C:/test/app").resolve(),
            data_root=Path("C:/test/data").resolve(),
            vault_root=Path("C:/test/vault").resolve(),
            vault_id="00000000-0000-0000-0000-000000000001",
        )
        ctx = AppContext(paths=paths, config={}, resources=ResourceCatalog())

        with patch.dict("os.environ", {"BEYIN_LLM_COMMAND": "my-llm --dangerously-skip-permissions"}):
            stdout, err, prov = run_model("prompt", Path("C:/test/vault"), mode="text", timeout=5, ctx=ctx)
            self.assertIsNone(stdout)
            self.assertEqual(err, "custom-isolation-required")
            self.assertEqual(prov, "custom")

    def test_concurrent_human_directories_never_deleted_by_runner(self):
        """Runner must never delete concurrent human/user directories outside or inside cwd."""
        import sys, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            vault_dir = tmp_root / "vault"
            vault_dir.mkdir()
            human_dir = tmp_root / "concurrent-human-work"
            human_dir.mkdir()
            (human_dir / "note.md").write_text("precious human content")

            command = f'"{sys.executable}" -c "print(\'ok\')"'
            paths = AppPaths(
                app_root=Path("C:/test/app").resolve(),
                data_root=Path("C:/test/data").resolve(),
                vault_root=vault_dir,
                vault_id="00000000-0000-0000-0000-000000000001",
            )
            ctx = AppContext(paths=paths, config={}, resources=ResourceCatalog())
            with patch.dict("os.environ", {"BEYIN_LLM_COMMAND": command, "BEYIN_RECURSION_DEPTH": "0"}):
                stdout, err, prov = run_model("prompt", vault_dir, mode="text", timeout=5, ctx=ctx)
            self.assertIsNone(stdout)
            self.assertEqual(err, "custom-isolation-required")
            self.assertEqual(prov, "custom")
            self.assertTrue(human_dir.exists())
            self.assertEqual((human_dir / "note.md").read_text(), "precious human content")

    def test_cursor_command_invocation_fails_closed_in_text_mode(self):
        """Cursor agent lacks sandbox/read-only mode and must fail-closed in text mode."""
        with patch("respectedbrain.providers.runner._find_executable", return_value="C:/path/cursor-agent.cmd"):
            inv_text = _command("cursor", "hello", mode="text")
            self.assertIsNone(inv_text, "Cursor must return None in text mode because it cannot enforce read-only boundary")
            inv_ws = _command("cursor", "hello", mode="workspace")
            self.assertIsNotNone(inv_ws)
            self.assertEqual(inv_ws.argv, ["C:/path/cursor-agent.cmd", "-p", "--output-format", "text", "hello"])



if __name__ == "__main__":
    unittest.main()
