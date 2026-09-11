#!/usr/bin/env python3
"""MCP Sunucusu ve Editör Kayıt Testleri.

Claude Desktop, Cursor, Windsurf, Claude Code, Antigravity IDE ve Cline/Roo-Code
konfigürasyon dosyalarına güvenli atomik yazma ve mevcut konfigürasyonları koruma testleri.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.vault_mcp_server import RespectedMcpServer, _update_mcp_json_file, register_mcp


class TestMcpRegistration(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.fake_home = self.base / "home"
        self.fake_home.mkdir(parents=True, exist_ok=True)
        self.fake_appdata = self.base / "appdata"
        self.fake_appdata.mkdir(parents=True, exist_ok=True)
        self.fake_vault = self.base / "TestVault"
        self.fake_vault.mkdir(parents=True, exist_ok=True)
        (self.fake_vault / "scripts").mkdir(parents=True, exist_ok=True)
        (self.fake_vault / "scripts" / "vault_mcp_server.py").write_text("# dummy", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_update_mcp_json_preserves_existing_servers(self) -> None:
        cfg_file = self.fake_home / "test_mcp.json"
        existing_data = {
            "mcpServers": {
                "existing_mcp": {
                    "command": "npx",
                    "args": ["-y", "some-tool"],
                }
            },
            "other_setting": True,
        }
        cfg_file.write_text(json.dumps(existing_data), encoding="utf-8")

        new_entry = {
            "command": "python",
            "args": ["server.py", "--vault", "path"],
        }
        _update_mcp_json_file(cfg_file, new_entry, server_key="respected-vault")

        loaded = json.loads(cfg_file.read_text(encoding="utf-8"))
        self.assertTrue(loaded.get("other_setting"))
        self.assertIn("existing_mcp", loaded["mcpServers"])
        self.assertIn("respected-vault", loaded["mcpServers"])
        self.assertEqual(loaded["mcpServers"]["respected-vault"]["command"], "python")

    def test_register_all_editors_in_fake_environment(self) -> None:
        # Önceden sahte VS Code Cline dizini oluşturalım
        cline_dir = self.fake_appdata / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev"
        cline_dir.mkdir(parents=True, exist_ok=True)

        actions = register_mcp(
            vault_root=self.fake_vault,
            home_dir=self.fake_home,
            appdata_dir=self.fake_appdata,
        )

        self.assertTrue(len(actions) >= 4)

        # 1. Claude Code (~/.claude.json)
        claude_cfg = self.fake_home / ".claude.json"
        self.assertTrue(claude_cfg.is_file())
        data = json.loads(claude_cfg.read_text(encoding="utf-8"))
        self.assertIn("respected-vault", data.get("mcpServers", {}))

        # 2. Cursor IDE (~/.cursor/mcp.json)
        cursor_cfg = self.fake_home / ".cursor" / "mcp.json"
        self.assertTrue(cursor_cfg.is_file())
        data = json.loads(cursor_cfg.read_text(encoding="utf-8"))
        self.assertIn("respected-vault", data.get("mcpServers", {}))

        # 3. Windsurf IDE (~/.codeium/windsurf/mcp_config.json)
        windsurf_cfg = self.fake_home / ".codeium" / "windsurf" / "mcp_config.json"
        self.assertTrue(windsurf_cfg.is_file())
        data = json.loads(windsurf_cfg.read_text(encoding="utf-8"))
        self.assertIn("respected-vault", data.get("mcpServers", {}))

        # 4. Claude Desktop (APPDATA/Claude/claude_desktop_config.json)
        desktop_cfg = self.fake_appdata / "Claude" / "claude_desktop_config.json"
        self.assertTrue(desktop_cfg.is_file())
        data = json.loads(desktop_cfg.read_text(encoding="utf-8"))
        self.assertIn("respected-vault", data.get("mcpServers", {}))

        # 5. Cline (kurulu olduğu için yazılmalı)
        cline_cfg = cline_dir / "settings" / "cline_mcp_settings.json"
        self.assertTrue(cline_cfg.is_file())
        data = json.loads(cline_cfg.read_text(encoding="utf-8"))
        self.assertIn("respected-vault", data.get("mcpServers", {}))

    def test_client_filter(self) -> None:
        actions = register_mcp(
            vault_root=self.fake_vault,
            home_dir=self.fake_home,
            appdata_dir=self.fake_appdata,
            clients=["cursor"],
        )
        self.assertEqual(len(actions), 1)
        self.assertTrue((self.fake_home / ".cursor" / "mcp.json").is_file())
        self.assertFalse((self.fake_home / ".claude.json").is_file())
        self.assertFalse((self.fake_home / ".codeium" / "windsurf" / "mcp_config.json").is_file())


if __name__ == "__main__":
    unittest.main()
