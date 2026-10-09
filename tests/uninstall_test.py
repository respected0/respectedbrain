"""Uninstall restores only recorded unchanged registrations and preserves all notes."""
import json
import unittest
from unittest import mock
from respectedbrain.core.config import ConfigStore
from respectedbrain.vault.registry import build_context
from respectedbrain.installation.uninstall import uninstall
from respectedbrain.installation.ownership import OwnershipManifest,read_manifest,manifest_document
from respectedbrain.integrations.backend import ExternalChange
from tests import foundation_setup_test as setup_support
from tests.foundation_support import snapshot
from respectedbrain import cli

class TestUninstall(unittest.TestCase):
    def setUp(self):
        setup_support.FoundationSetupTest.setUp(self)
        self.assertTrue(setup_support.FoundationSetupTest.install(self).success)
        self.ctx=build_context(self.roots,ConfigStore(self.roots.data_root),vault=self.vault,vault_id=None,env={})
        self.home=self.root / "home"

    def own(self,kind,key,before,after):
        row=ExternalChange(kind,str(key),before,after)
        path=self.roots.data_root / "install-manifest.json"
        current=read_manifest(path)
        path.write_text(json.dumps(manifest_document(OwnershipManifest(3,current.files,(*current.external,row)))),encoding="utf-8")
        self.backend.records[(kind,str(key))]=after
        return row

    def test_remove_global_integrations_restores_user_configs_exactly(self):
        originals={".claude/settings.json":b'{"theme":"custom","hooks":{"SessionStart":[{"command":"other-tool"}]}}',".gemini/GEMINI.md":b"# User rules\nOther rules\n",".cursor/hooks.json":b'{"custom":true}'}
        rows=[self.own("file",self.home / key,value,b"managed bytes") for key,value in originals.items()]
        self.assertTrue(uninstall(self.ctx,backend=self.backend).success)
        for row in rows:
            self.assertEqual(self.backend.read(row.kind,row.key),row.before)

    def test_notify_without_previous_chain_removes_only_owned_registration(self):
        key=self.home / ".codex/config.toml"
        original=b'model = "my-model"\n'
        row=self.own("file",key,original,b'model = "my-model"\nnotify = ["respectedbrain.exe"]\n')
        self.assertTrue(uninstall(self.ctx,backend=self.backend).success)
        self.assertEqual(self.backend.read(row.kind,row.key),original)

    def test_notify_restores_opaque_original_outer_notifier_and_removes_owned_chain(self):
        original=json.dumps({"argv":["computer-use.exe","turn-ended","--opaque",'{"path":"C:\\literal"}']}).encode()
        row=self.own("file",self.home / ".codex/config.toml",original,b"our notifier")
        chain=self.own("file",self.ctx.paths.state_dir / "codex-notify-chain.json",None,b"chain")
        self.assertTrue(uninstall(self.ctx,backend=self.backend).success)
        self.assertEqual(self.backend.read(row.kind,row.key),original)
        self.assertIsNone(self.backend.read(chain.kind,chain.key))

    def test_remove_desktop_shortcut_uses_recorded_ownership_not_filename(self):
        ours=self.own("shortcut",self.home / "Desktop/Respected Brain.lnk",None,b"owned")
        unrelated=("shortcut",str(self.home / "Desktop/CustomBrain.lnk"))
        self.backend.records[unrelated]=b"user"
        self.assertTrue(uninstall(self.ctx,backend=self.backend).success)
        self.assertIsNone(self.backend.read(ours.kind,ours.key))
        self.assertEqual(self.backend.records[unrelated],b"user")

    def test_scheduled_tasks_are_removed_only_when_recorded_and_unchanged(self):
        row=self.own("task","respected-morning-briefing-"+self.ctx.paths.vault_id,None,b"owned")
        other=("task","respected-morning-briefing-unrecorded-user")
        self.backend.records[other]=b"user task"
        self.assertTrue(uninstall(self.ctx,backend=self.backend).success)
        self.assertIsNone(self.backend.read(row.kind,row.key))
        self.assertEqual(self.backend.records[other],b"user task")

    def test_changed_shortcut_is_retained_with_explicit_conflict(self):
        row=self.own("shortcut",self.home / "Desktop/Respected Brain.lnk",None,b"owned")
        self.backend.records[(row.kind,row.key)]=b"user changed target"
        result=uninstall(self.ctx,backend=self.backend)
        self.assertFalse(result.success)
        self.assertIn("shortcut:"+row.key,result.conflicts)
        self.assertEqual(self.backend.read(row.kind,row.key),b"user changed target")

    def test_mcp_removal_restores_other_servers_and_unknown_settings(self):
        original=json.dumps({"mcpServers":{"other":{"command":"node","args":["server.js"]}},"unknown":True}).encode()
        row=self.own("mcp",self.home / ".cursor/mcp.json",original,b"ours and original")
        self.assertTrue(uninstall(self.ctx,backend=self.backend).success)
        self.assertEqual(self.backend.read(row.kind,row.key),original)

    def test_explicit_purge_removes_owned_data_but_preserves_vault_and_unknown_data(self):
        before=snapshot(self.vault)
        unknown=self.roots.data_root / "user-file.txt"
        unknown.write_bytes(b"user")
        result=uninstall(self.ctx,backend=self.backend,purge_data=True)
        self.assertTrue(result.success,result.conflicts)
        self.assertFalse((self.roots.data_root / "config.json").exists())
        self.assertEqual(snapshot(self.vault),before)
        self.assertEqual(unknown.read_bytes(),b"user")

    def test_default_uninstall_removes_owned_technical_records_and_preserves_audit_and_unknown_data(self):
        before=snapshot(self.vault)
        unknown=self.roots.data_root / "user-file.txt"
        unknown.write_bytes(b"user")

        result=uninstall(self.ctx,backend=self.backend)

        self.assertTrue(result.success,result.conflicts)
        self.assertFalse((self.roots.data_root / "config.json").exists())
        self.assertFalse((self.roots.data_root / "install-manifest.json").exists())
        self.assertTrue((self.roots.data_root / "backups").is_dir())
        self.assertEqual(snapshot(self.vault),before)
        self.assertEqual(unknown.read_bytes(),b"user")

    def test_cli_defaults_to_technical_purge_and_keep_data_opts_out_and_repair_accepts_package(self):
        from respectedbrain.installation.transaction import OperationResult
        success = OperationResult(True, "fixture", ())
        with mock.patch("respectedbrain.cli.bootstrap", return_value=self.ctx), \
             mock.patch("respectedbrain.installation.deferred.defer_operation", return_value=None), \
             mock.patch("respectedbrain.installation.uninstall.uninstall", return_value=success) as remove, \
             mock.patch("respectedbrain.installation.repair.repair", return_value=success) as fix:
            self.assertEqual(cli.main(["uninstall"]), 0)
            self.assertTrue(remove.call_args.kwargs["purge_data"])
            self.assertEqual(cli.main(["uninstall", "--keep-data"]), 0)
            self.assertFalse(remove.call_args.kwargs["purge_data"])
            self.assertEqual(cli.main(["repair", "--package", str(self.root / "package")]), 0)
            self.assertEqual(fix.call_args.kwargs["package"], self.root / "package")

    def test_busy_writer_prevents_application_removal(self):
        before=snapshot(self.roots.app_root)
        self.backend.busy=True
        result=uninstall(self.ctx,backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.roots.app_root),before)

    def test_unrecorded_hook_config_is_never_deleted(self):
        key=("file",str(self.home / ".claude/settings.json"))
        self.backend.records[key]=b"my own hook settings"
        self.assertTrue(uninstall(self.ctx,backend=self.backend).success)
        self.assertEqual(self.backend.records[key],b"my own hook settings")

    def test_cli_rejects_retired_purge_vault_and_wsl_worker_flags(self):
        before=snapshot(self.vault)
        with mock.patch("respectedbrain.cli._dispatch",side_effect=AssertionError("mutation")):
            self.assertEqual(cli.main(["uninstall", "--purge-vault"]),2)
            self.assertEqual(cli.main(["uninstall", "--wsl-worker"]),2)
        self.assertEqual(snapshot(self.vault),before)

if __name__=="__main__":
    unittest.main()
