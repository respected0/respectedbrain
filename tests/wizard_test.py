"""Wizard and source-launcher installation contracts use the same package services."""
from pathlib import Path
import json
import unittest
from unittest import mock
from respectedbrain.core.config import ConfigStore
from respectedbrain.vault.registry import build_context
from respectedbrain.installation import wizard
from respectedbrain.installation.setup import setup
from respectedbrain.installation.transaction import OperationResult
from tests import foundation_setup_test as setup_support
from tests.foundation_support import snapshot
from respectedbrain import cli

class WizardTest(unittest.TestCase):
    setUp = setup_support.FoundationSetupTest.setUp
    install = setup_support.FoundationSetupTest.install

    def action(self, *, mode="install", profile=None, desired=None, package=None):
        values={"OS_NAME":"AdaOS","USER_NAME":"Ada Lovelace","USER_BIO":"Algoritma Mimarı","COMPANION":"Babbage","platform":"windows-native","user_home":str(self.root / "home")}
        values.update(profile or {})
        return wizard.run_action(mode,self.roots,self.vault,profile=values,desired=self.desired if desired is None else desired,backend=self.backend,package=self.package if package is None else package,require_provenance=False)

    def test_automated_install_creates_complete_vault_and_resolves_placeholders(self):
        result=self.action(profile={"summary_provider":"antigravity","provider_priority":["antigravity","codex"]})
        self.assertTrue(result.success,result.conflicts)
        core=(self.vault / "🔮 850-Companion/Core.md").read_text(encoding="utf-8")
        self.assertIn("Ada Lovelace",core)
        self.assertIn("Babbage",core)
        self.assertNotIn("{{",core)
        self.assertTrue((self.vault / "knowledge/connections").is_dir())
        config=ConfigStore(self.roots.data_root).read()
        self.assertEqual(config["preferences"]["provider_priority"],["antigravity","codex"])
        self.assertFalse((self.vault / ".beyin").exists())

    def test_fresh_native_install_renders_hooks_for_final_registered_uuid(self):
        from respectedbrain.integrations.backend import NativeBackend
        self.backend = NativeBackend(self.roots.data_root)
        self.assertTrue(self.action().success)
        identity=json.loads((self.vault / ".respected.json").read_text())["vault_id"]
        content=(self.vault / ".claude/settings.json").read_text(encoding="utf-8")
        self.assertIn(identity,content)
        self.assertIn(str(self.roots.app_root / "respectedbrain.exe").replace("\\","\\\\"),content)
        self.assertNotIn(".respected-stage",content)

    def test_install_refuses_non_empty_unregistered_directory(self):
        self.vault.mkdir()
        (self.vault / "existing.txt").write_bytes(b"user")
        before=snapshot(self.root)
        result=self.action()
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.root),before)

    def test_reinstall_preserves_user_note_and_project_config_bytes(self):
        self.assertTrue(self.action().success)
        path=self.vault / "knowledge/human-note.md"
        path.write_bytes("İnsan notu.\n".encode())
        settings=self.vault / ".claude/settings.json"
        settings.write_bytes(b'{"myProjectSetting":true}')
        before=snapshot(self.vault)
        self.assertTrue(self.action(mode="modify").success)
        self.assertEqual(snapshot(self.vault),before)

    def test_reinstall_applies_requested_dashboard_shortcut(self):
        self.assertTrue(self.action().success)
        result=self.action(mode="modify",desired={**self.desired,"shortcut":True})
        self.assertTrue(result.success,result.conflicts)
        rows=[value for (kind,key),value in self.backend.records.items() if kind=="shortcut"]
        self.assertEqual(len(rows),1)
        self.assertIn("dashboard --vault-id",json.loads(rows[0])["arguments"])

    def test_requested_global_failure_is_reported_and_existing_notes_retained(self):
        self.assertTrue(self.action().success)
        before=snapshot(self.vault)
        with mock.patch.object(self.backend,"apply",side_effect=OSError("global failure")):
            result=self.action(mode="modify",desired={**self.desired,"global":True})
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.vault),before)

    def test_native_install_persists_only_stable_application_launcher(self):
        from respectedbrain.integrations.backend import NativeBackend
        self.backend = NativeBackend(self.roots.data_root)
        self.assertTrue(self.action().success)
        content=(self.vault / ".claude/settings.json").read_text(encoding="utf-8")
        self.assertIn("respectedbrain.exe",content)
        self.assertNotIn("python",content)
        self.assertNotIn(".py",content)

    def test_render_failure_rolls_back_partial_fresh_install(self):
        with mock.patch("respectedbrain.integrations.rendering.render_project_integrations",side_effect=OSError("render failed")):
            result=self.action()
        self.assertFalse(result.success)
        self.assertFalse(self.vault.exists())
        self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())

    def test_wizard_antigravity_preference_is_saved_without_provider_call(self):
        self.assertTrue(self.action(profile={"summary_provider":"antigravity"}).success)
        self.assertEqual(ConfigStore(self.roots.data_root).read()["preferences"]["summary_provider"],"antigravity")

    def test_wizard_custom_priority_is_saved_in_data_config(self):
        self.assertTrue(self.action(profile={"provider_priority":["antigravity","codex"]}).success)
        self.assertEqual(ConfigStore(self.roots.data_root).read()["preferences"]["provider_priority"],["antigravity","codex"])

    def test_wizard_single_provider_lock_retains_fail_fast_setting(self):
        self.assertTrue(self.action(profile={"summary_provider":"codex","provider_fallback":False}).success)
        preferences=ConfigStore(self.roots.data_root).read()["preferences"]
        self.assertEqual(preferences["summary_provider"],"codex")
        self.assertFalse(preferences["provider_fallback"])

    def test_gui_install_calls_same_setup_service_with_explicit_roots(self):
        with mock.patch.object(wizard,"setup",return_value=OperationResult(True,"test",())) as service:
            self.assertTrue(self.action().success)
        self.assertEqual(service.call_args.args,(self.roots,self.vault))
        self.assertEqual(service.call_args.kwargs["package"],self.package)

    def test_gui_cli_preserves_selected_vault_and_status(self):
        with mock.patch.object(cli, "_dispatch", return_value=9) as dispatch:
            self.assertEqual(cli.main(["setup", "--gui", "--vault", str(self.vault)]), 9)
        args = dispatch.call_args.args[0]
        self.assertTrue(args.gui)
        self.assertEqual(args.vault, self.vault)

    def test_wizard_mcp_registration_uses_installed_launcher_and_uuid(self):
        result=self.action(desired={**self.desired,"mcp":True})
        self.assertTrue(result.success,result.conflicts)
        records=[json.loads(value) for (kind,key),value in self.backend.records.items() if kind=="mcp" and value and "mcpServers" in json.loads(value)]
        self.assertTrue(records)
        for record in records:
            command=record["mcpServers"]["respected-vault"]
            self.assertEqual(command["command"],str(self.roots.app_root / "respectedbrain.exe"))
            self.assertEqual(command["args"][0],"mcp")
            self.assertIn("--vault-id",command["args"])

if __name__=="__main__":
    unittest.main()
