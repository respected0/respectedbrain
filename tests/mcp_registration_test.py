"""MCP editor registration safety through readonly plans and CAS writes."""
import json
from pathlib import Path
from unittest import TestCase
from tests.foundation_integrations_test import IntegrationFixture
from tests.foundation_support import snapshot
from respectedbrain.integrations.rendering import plan_integrations
from respectedbrain.core.errors import OwnershipConflict

class TestMcpRegistration(IntegrationFixture, TestCase):
    def apply(self, rows):
        backend = self.backend()
        for row in rows:
            backend.apply(row)

    def test_update_mcp_json_preserves_existing_servers(self):
        path = self.home / ".cursor/mcp.json"
        path.parent.mkdir()
        original = {"mcpServers": {"existing_mcp": {"command": "npx", "args": ["-y", "some-tool"]}}, "other_setting": True}
        path.write_text(json.dumps(original), encoding="utf-8")
        self.apply(plan_integrations(self.ctx, self.profile, {"mcp": True}, self.backend()))
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(loaded["other_setting"])
        self.assertEqual(loaded["mcpServers"]["existing_mcp"], original["mcpServers"]["existing_mcp"])
        entry = loaded["mcpServers"]["respected-vault"]
        self.assertEqual(entry["command"], str(self.app / "respectedbrain.exe"))
        self.assertEqual(entry["args"], ["mcp", "--vault-id", self.ctx.paths.vault_id])

    def test_register_all_editors_in_fake_environment(self):
        cline = self.home / "AppData/Roaming/Code/User/globalStorage/saoudrizwan.claude-dev"
        cline.mkdir(parents=True)
        roo = cline.with_name("rooveterinaryinc.roo-cline")
        roo.mkdir()
        self.apply(plan_integrations(self.ctx, self.profile, {"mcp": True}, self.backend()))
        for path in (self.home / ".claude.json", self.home / ".cursor/mcp.json", self.home / ".codeium/windsurf/mcp_config.json", self.home / "AppData/Roaming/Claude/claude_desktop_config.json", cline / "settings/cline_mcp_settings.json", roo / "settings/roo_mcp_settings.json"):
            self.assertIn("respected-vault", json.loads(path.read_text(encoding="utf-8"))["mcpServers"])

    def test_disabled_client_registration_leaves_every_user_file_unchanged(self):
        before = snapshot(self.root)
        self.assertEqual(plan_integrations(self.ctx, self.profile, {"mcp": False}, self.backend()), ())
        self.assertEqual(snapshot(self.root), before)

    def test_corrupt_json_fails_closed_without_mutating_preview(self):
        path = self.home / ".cursor/mcp.json"
        path.parent.mkdir()
        path.write_bytes(b"{ this is not valid json : ;")
        before = snapshot(self.root)
        with self.assertRaises(ValueError):
            plan_integrations(self.ctx, self.profile, {"mcp": True}, self.backend())
        self.assertEqual(snapshot(self.root), before)

    def test_antigravity_dual_registration(self):
        (self.home / ".gemini").mkdir()
        rows = plan_integrations(self.ctx, self.profile, {"mcp": True}, self.backend())
        self.apply(rows)
        path = self.home / ".gemini/config/mcp_config.json"
        self.assertIn("respected-vault", json.loads(path.read_text(encoding="utf-8"))["mcpServers"])
        directory = self.home / ".gemini/antigravity-ide/mcp/respected-vault"
        self.assertTrue((directory / "instructions.md").is_file())
        tool = json.loads((directory / "respected_search.json").read_text(encoding="utf-8"))
        self.assertEqual(tool["name"], "respected_search")
        self.assertEqual(tool["parameters"]["type"], "object")
