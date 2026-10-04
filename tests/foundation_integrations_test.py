"""Existing integration behavior behind explicit immutable-package/data/vault context."""
from __future__ import annotations
import contextlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from respectedbrain.core.context import AppContext
from respectedbrain.core.paths import AppPaths
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.core.errors import OwnershipConflict
from respectedbrain.integrations.backend import ExternalChange, IntegrationProfile
from tests.foundation_support import snapshot


class IntegrationFixture:

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app, self.data, self.vault, self.home = [self.root / name for name in ('app', 'data', 'Türkçe 🧠 Vault', 'home')]
        for path in (self.app, self.vault, self.home):
            path.mkdir()
        self.ctx = AppContext(AppPaths(self.app, self.data, self.vault, '93e9e921-3334-4a6a-a381-1d4c42a9d405'), {'integrations': {}, 'preferences': {'summary_provider': 'codex'}}, ResourceCatalog())
        self.profile = IntegrationProfile('windows-native', (str(self.app / 'respectedbrain.exe'),), self.home)

    def wsl_registry_output(self):
        from respectedbrain.integrations.rendering import wsl_path
        return json.dumps({self.ctx.paths.vault_id: {"path": wsl_path(self.vault)}})

    def backend(self):
        module = importlib.import_module('respectedbrain.integrations.backend')
        return module.NativeBackend(self.data, user_home=self.home)



class FoundationIntegrationsTest(IntegrationFixture, unittest.TestCase):
    def test_disabled_options_produce_no_new_registration(self):
        renderer = importlib.import_module('respectedbrain.integrations.rendering')
        before = snapshot(self.root)
        changes = renderer.plan_integrations(self.ctx, self.profile, {'global': False, 'mcp': False, 'schedule': False, 'shortcut': False}, self.backend())
        self.assertEqual(changes, ())
        self.assertEqual(snapshot(self.root), before)

    def test_native_hooks_and_notify_preserve_existing_user_data(self):
        renderer = importlib.import_module('respectedbrain.integrations.rendering')
        codex = self.home / '.codex'
        codex.mkdir()
        original = 'My own rules\n'
        (codex / 'AGENTS.md').write_text(original, encoding='utf-8')
        (codex / 'config.toml').write_text('model = "custom"\nnotify = ["other-notifier.exe", "turn-ended"]\n', encoding='utf-8')
        before = snapshot(self.root)
        changes = renderer.plan_integrations(self.ctx, self.profile, {'global': True}, self.backend())
        self.assertEqual(snapshot(self.root), before)
        after = {row.key: row.after.decode('utf-8') for row in changes if row.after is not None}
        self.assertTrue(after[str(codex / 'AGENTS.md')].startswith(original))
        hooks = json.loads(after[str(codex / 'hooks.json')])
        command = hooks['hooks']['SessionStart'][-1]['hooks'][0]['command']
        self.assertIn(str(self.app / 'respectedbrain.exe'), command)
        self.assertIn(self.ctx.paths.vault_id, command)
        self.assertNotIn('.py', command)
        self.assertNotIn('python', command)
        self.assertIn('model = "custom"', after[str(codex / 'config.toml')])
        chain = self.ctx.paths.state_dir / 'codex-notify-chain.json'
        self.assertEqual(json.loads(after[str(chain)])['argv'], ['other-notifier.exe', 'turn-ended'])

    def test_native_mcp_preserves_unknown_servers_and_settings(self):
        renderer = importlib.import_module('respectedbrain.integrations.rendering')
        path = self.home / '.cursor/mcp.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'mcpServers': {'other': {'command': 'other.exe'}}, 'setting': {'keep': True}}), encoding='utf-8')
        changes = renderer.plan_integrations(self.ctx, self.profile, {'mcp': True}, self.backend())
        row = next(row for row in changes if row.key == str(path))
        document = json.loads(row.after)
        self.assertEqual(document['mcpServers']['other'], {'command': 'other.exe'})
        self.assertEqual(document['setting'], {'keep': True})
        entry = document['mcpServers']['respected-vault']
        self.assertEqual(entry['command'], str(self.app / 'respectedbrain.exe'))
        self.assertEqual(entry['args'], ['mcp', '--vault-id', self.ctx.paths.vault_id])

    def test_backend_cas_restore_does_not_overwrite_user_changed_record(self):
        backend = self.backend()
        path = self.home / 'settings.json'
        path.write_bytes(b'original')
        change = ExternalChange('file', str(path), b'original', b'ours')
        backend.apply(change)
        self.assertEqual(backend.read('file', str(path)), b'ours')
        path.write_bytes(b'user edit')
        with self.assertRaises(OwnershipConflict):
            backend.restore(change)
        self.assertEqual(path.read_bytes(), b'user edit')

    def test_backend_rejects_stale_plan_before_write(self):
        backend = self.backend()
        path = self.home / 'settings.json'
        path.write_bytes(b'user edit')
        with self.assertRaises(OwnershipConflict):
            backend.apply(ExternalChange('file', str(path), b'old', b'ours'))
        self.assertEqual(path.read_bytes(), b'user edit')

    def test_uuid_instruction_override_precedes_package_defaults(self):
        renderer = importlib.import_module('respectedbrain.integrations.rendering')
        override = self.ctx.paths.overrides_dir / 'instructions.md'
        override.parent.mkdir(parents=True)
        override.write_text('My personalized instructions', encoding='utf-8')
        changes = renderer.plan_integrations(self.ctx, self.profile, {'global': True}, self.backend())
        agents = next(row for row in changes if row.key == str(self.home / '.codex/AGENTS.md'))
        self.assertIn('My personalized instructions', agents.after.decode('utf-8'))

    def test_hook_protocol_uses_selected_uuid_state_and_stable_session_id(self):
        bridge = importlib.import_module('respectedbrain.integrations.hooks.bridge')
        before_app = snapshot(self.app)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = bridge.dispatch(self.ctx, provider='cursor', event='prompt', argv=[], stdin=json.dumps({'conversationId': 'session-one', 'cwd': str(self.root / 'project')}))
        self.assertEqual(json.loads(result), {})
        self.assertEqual(stdout.getvalue(), '')
        counts = [p for p in self.ctx.paths.state_dir.glob('prompt_count.*') if not p.name.endswith('.lock')]
        self.assertEqual(len(counts), 1)
        self.assertEqual(counts[0].read_text(encoding='utf-8').strip(), '1')
        self.assertEqual(snapshot(self.app), before_app)
        self.assertFalse((self.vault / '.beyin').exists())

    def test_mcp_stdout_is_protocol_only(self):
        module = importlib.import_module('respectedbrain.integrations.mcp.server')
        output = io.StringIO()
        incoming = io.StringIO(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}) + '\n')
        with mock.patch('sys.stdin', incoming), contextlib.redirect_stdout(output):
            result = module.serve(self.ctx)
        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload['jsonrpc'], '2.0')
        self.assertEqual(payload['id'], 1)
        self.assertNotIn('DEBUG', output.getvalue())
        self.assertFalse((self.vault / '.beyin').exists())

    def test_schedule_uses_stable_uuid_and_provider_free_launcher(self):
        from respectedbrain.integrations.scheduling.service import plan_schedule
        backend = mock.Mock()
        backend.read.return_value = None
        changes = plan_schedule(self.ctx, self.profile, backend)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].kind, "task")
        self.assertIn(self.ctx.paths.vault_id, changes[0].key)
        text = changes[0].after.decode("utf-8")
        self.assertIn("respectedbrain.exe", text)
        self.assertIn("briefing --vault-id", text)
        self.assertNotIn("python", text)
        self.assertNotIn(".py", text)
        self.assertIn("IgnoreNew", text)
        self.assertIn("StartWhenAvailable", text)

    def test_codex_notify_preserves_chained_json_argument_without_path_rewrite(self):
        from respectedbrain.integrations.hooks.codex_notify import dispatch
        chain = self.ctx.paths.state_dir / "codex-notify-chain.json"
        chain.parent.mkdir(parents=True)
        chain.write_text(json.dumps({"argv": ["other.exe", "turn-ended"]}), encoding="utf-8")
        payload = json.dumps({"thread-id": "session", "client": "codex_exec", "cwd": "C:\\project"})
        with mock.patch("respectedbrain.integrations.hooks.codex_notify.subprocess.Popen") as spawn:
            result = dispatch(self.ctx, argv=["--chain-file", str(chain), payload], stdin="")
        self.assertEqual(result, "")
        self.assertEqual(spawn.call_args.args[0], ["other.exe", "turn-ended", payload])

    def test_mcp_antigravity_schemas_are_planned_without_search_cache_creation(self):
        from respectedbrain.integrations.rendering import plan_integrations
        (self.home / ".gemini").mkdir()
        before = snapshot(self.root)
        changes = plan_integrations(self.ctx, self.profile, {"mcp": True}, self.backend())
        names = {Path(row.key).name for row in changes}
        self.assertIn("instructions.md", names)
        self.assertIn("respected_search.json", names)
        self.assertEqual(snapshot(self.root), before)

    def test_legacy_inspection_never_claims_unknown_mcp_command(self):
        path = self.home / ".cursor/mcp.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"mcpServers": {"respected-vault": {"command": "third-party.exe"}}}), encoding="utf-8")
        backend = self.backend()
        self.assertTrue(hasattr(backend, "inspect_legacy_registrations"))
        with self.assertRaises(OwnershipConflict):
            backend.inspect_legacy_registrations(self.root / "legacy", self.vault, self.ctx.paths, self.profile)

    def test_wsl_profile_validates_launcher_inside_wsl(self):
        from respectedbrain.integrations.rendering import plan_integrations
        from respectedbrain.core.errors import FoundationError
        profile = IntegrationProfile("windows-wsl", ("/opt/respectedbrain",), self.home)
        with mock.patch("respectedbrain.integrations.rendering.subprocess.run", return_value=mock.Mock(returncode=1)) as runner:
            with self.assertRaises(FoundationError):
                plan_integrations(self.ctx, profile, {"global": True}, self.backend())
        argv = runner.call_args.args[0]
        self.assertEqual(argv[:4], ["wsl.exe", "--", "sh", "-c"])
        self.assertEqual(argv[-1], "/opt/respectedbrain")

    @unittest.skipUnless(__import__("os").name == "nt", "Windows native registration")
    def test_native_task_and_shortcut_roundtrip_canonical_ownership(self):
        import uuid
        from respectedbrain.integrations.backend import ExternalChange, canonical_json, canonical_task_xml
        from respectedbrain.integrations.scheduling.service import _windows_xml
        backend = self.backend()
        key = "RespectedBrain-FoundationTest-" + str(uuid.uuid4())
        after = canonical_task_xml(_windows_xml(str(self.app / "respectedbrain.exe"), "briefing --vault-id " + self.ctx.paths.vault_id))
        try:
            backend.apply(ExternalChange("task", key, None, after))
            self.assertEqual(backend.read("task", key), after)
            backend.restore(ExternalChange("task", key, None, after))
            self.assertIsNone(backend.read("task", key))
        finally:
            if backend.read("task", key) is not None:
                backend._write("task", key, None)
        path = self.home / "Desktop/test.lnk"
        descriptor = canonical_json({"target": str(self.app / "respectedbrain.exe"), "arguments": "serve --vault-id " + self.ctx.paths.vault_id, "working_directory": str(self.app), "description": "test", "icon_location": "", "window_style": 1, "hotkey": ""})
        try:
            backend.apply(ExternalChange("shortcut", str(path), None, descriptor))
            self.assertEqual(backend.read("shortcut", str(path)), descriptor)
            backend.restore(ExternalChange("shortcut", str(path), None, descriptor))
        finally:
            path.unlink(missing_ok=True)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows native registration")
    def test_native_registry_preserves_unknown_typed_values_and_children(self):
        import uuid
        import winreg
        from respectedbrain.integrations.backend import ExternalChange, canonical_json
        backend = self.backend()
        key = "HKCU\\Software\\RespectedBrain-FoundationTest-" + str(uuid.uuid4())
        value = {"values": {"Unknown": {"type": winreg.REG_DWORD, "data": 17}}, "subkeys": {"User": {"values": {"Binary": {"type": winreg.REG_BINARY, "data": {"base64": "AAEC"}}}, "subkeys": {}}}}
        after = canonical_json(value)
        try:
            backend.apply(ExternalChange("registry", key, None, after))
            self.assertEqual(backend.read("registry", key), after)
            backend.restore(ExternalChange("registry", key, None, after))
            self.assertIsNone(backend.read("registry", key))
        finally:
            if backend.read("registry", key) is not None:
                backend._write("registry", key, None)

    def test_systemd_backend_read_reports_actual_activation_and_propagates_failure(self):
        from respectedbrain.integrations.backend import canonical_json
        from respectedbrain.core.errors import FoundationError
        backend = self.backend()
        outputs = [mock.Mock(returncode=0, stdout=b"enabled\n", stderr=b""), mock.Mock(returncode=0, stdout=b"active\n", stderr=b"")]
        with mock.patch("respectedbrain.integrations.backend.subprocess.run", side_effect=outputs):
            self.assertEqual(backend.read("task", "systemd:respected-test.timer"), canonical_json({"enabled": True, "active": True}))
        with mock.patch("respectedbrain.integrations.backend.subprocess.run", return_value=mock.Mock(returncode=1, stdout=b"", stderr=b"activation failed")):
            with self.assertRaises(FoundationError):
                backend._write("task", "systemd:respected-test.timer", canonical_json({"enabled": True, "active": True}))

    def test_legacy_inspection_rejects_script_name_as_unrelated_command_argument(self):
        source = self.root / "legacy"
        script = source / "scripts/vault_mcp_server.py"
        script.parent.mkdir(parents=True)
        script.write_text("legacy", encoding="utf-8")
        path = self.home / ".cursor/mcp.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"mcpServers": {"respected-vault": {"command": "third-party.exe", "args": [str(script)]}}}), encoding="utf-8")
        backend = self.backend()
        with mock.patch.object(backend, "_task_read", return_value=None), mock.patch.object(backend, "_shortcut_read", return_value=None), mock.patch.object(backend, "_registry_read", return_value=None):
            with self.assertRaises(OwnershipConflict):
                backend.inspect_legacy_registrations(source, self.vault, self.ctx.paths, self.profile)

    def test_managed_identity_uses_registered_uppercase_settings(self):
        from respectedbrain.core.context import AppContext
        from respectedbrain.integrations.rendering import managed_rule
        ctx = AppContext(self.ctx.paths, {"vaults": {self.ctx.paths.vault_id: {"settings": {"OS_NAME": "AdaOS", "COMPANION": "AdaCompanion", "USER_NAME": "Ada", "USER_BIO": "Researcher"}}}}, self.ctx.resources)
        text = managed_rule(ctx)
        self.assertIn("# AdaOS", text)
        self.assertIn("Sen AdaCompanion, Ada", text)
        self.assertIn("Researcher", text)
        self.assertNotIn("{{", text)

    def test_persistent_posix_registration_rejects_python_launcher(self):
        from respectedbrain.integrations.rendering import plan_integrations
        profile = IntegrationProfile("posix", ("python3", "-m", "respectedbrain"), self.home)
        with self.assertRaises(ValueError):
            plan_integrations(self.ctx, profile, {"global": True}, self.backend())

    def test_reentrant_hook_does_not_create_any_technical_state(self):
        from respectedbrain.integrations.hooks.bridge import dispatch
        before = snapshot(self.root)
        with mock.patch.dict("os.environ", {"BEYIN_INVOKED_BY": "codex"}):
            self.assertEqual(dispatch(self.ctx, provider="cursor", event="prompt", argv=[], stdin="{}"), "")
        self.assertEqual(snapshot(self.root), before)

    def test_schedule_planner_refuses_unknown_record_at_uuid_task_name(self):
        from respectedbrain.integrations.scheduling.service import plan_schedule, _windows_xml
        from respectedbrain.integrations.backend import canonical_task_xml
        backend = mock.Mock()
        backend.read.return_value = canonical_task_xml(_windows_xml("third-party.exe", "user task"))
        with self.assertRaises(OwnershipConflict):
            plan_schedule(self.ctx, self.profile, backend)

    def test_shortcut_planner_refuses_unrelated_existing_user_shortcut(self):
        from respectedbrain.integrations.rendering import plan_integrations
        from respectedbrain.integrations.backend import canonical_json
        backend = mock.Mock()
        backend.read.return_value = canonical_json({"target": "third-party.exe", "arguments": "user shortcut"})
        with self.assertRaises(OwnershipConflict):
            plan_integrations(self.ctx, self.profile, {"shortcut": True}, backend)

    def test_migration_preview_removes_only_proven_disabled_global_sections(self):
        source = self.root / "legacy"
        script = source / "hooks/bridge.py"
        script.parent.mkdir(parents=True)
        script.write_text("legacy", encoding="utf-8")
        path = self.home / ".codex/AGENTS.md"
        path.parent.mkdir()
        path.write_text("User before\n<!-- RESPECTED-GLOBAL:BEGIN -->\nVault " + str(self.vault) + "\n<!-- RESPECTED-GLOBAL:END -->\nUser after\n", encoding="utf-8")
        backend = self.backend()
        self.assertTrue(hasattr(backend, "preview_migration"))
        before = snapshot(self.root)
        with mock.patch.object(backend, "_task_read", return_value=None), mock.patch.object(backend, "_shortcut_read", return_value=None), mock.patch.object(backend, "_registry_read", return_value=None):
            rows = backend.preview_migration(self.ctx, legacy_root=source, vault=self.vault, roots=self.ctx.paths, profile=self.profile, desired={"global": False, "mcp": False, "schedule": False, "shortcut": False})
        row = next(row for row in rows if row.key == str(path))
        self.assertIn(b"User before", row.after)
        self.assertIn(b"User after", row.after)
        self.assertNotIn(b"RESPECTED-GLOBAL", row.after)
        self.assertEqual(snapshot(self.root), before)

    def test_mcp_registration_preserves_unknown_entry_fields(self):
        from respectedbrain.integrations.rendering import plan_integrations
        path = self.home / ".cursor/mcp.json"
        path.parent.mkdir()
        entry = {"command": str(self.app / "respectedbrain.exe"), "args": ["mcp", "--vault-id", self.ctx.paths.vault_id], "env": {"USER_SETTING": "keep"}, "disabled": False}
        path.write_text(json.dumps({"mcpServers": {"respected-vault": entry}}), encoding="utf-8")
        rows = plan_integrations(self.ctx, self.profile, {"mcp": True}, self.backend())
        row = next(row for row in rows if row.key == str(path))
        self.assertEqual(json.loads(row.after)["mcpServers"]["respected-vault"]["env"], {"USER_SETTING": "keep"})

    def test_enabled_migration_preserves_original_codex_notify_chain(self):
        import sys
        source = self.root / "legacy"
        script = source / "hooks/codex_notify.py"
        script.parent.mkdir(parents=True)
        script.write_text("legacy", encoding="utf-8")
        codex = self.home / ".codex"
        codex.mkdir()
        chain = codex / "respected-notify-chain.json"
        chain.write_text(json.dumps({"argv": ["original.exe", "turn-ended"]}), encoding="utf-8")
        old_notify = [sys.executable, str(script), "--chain-file", str(chain)]
        (codex / "config.toml").write_text("notify = " + json.dumps(old_notify), encoding="utf-8")
        backend = self.backend()
        with mock.patch.object(backend, "_task_read", return_value=None), mock.patch.object(backend, "_shortcut_read", return_value=None), mock.patch.object(backend, "_registry_read", return_value=None):
            rows = backend.preview_migration(self.ctx, legacy_root=source, vault=self.vault, roots=self.ctx.paths, profile=self.profile, desired={"global": True})
        target = str(self.ctx.paths.state_dir / "codex-notify-chain.json")
        self.assertIn(target, {row.key for row in rows})
        row = next(row for row in rows if row.key == target)
        self.assertEqual(json.loads(row.after)["argv"], ["original.exe", "turn-ended"])

    def test_legacy_native_records_need_exact_executable_proof_not_path_mention(self):
        from respectedbrain.integrations.backend import canonical_json, canonical_task_xml
        import hashlib
        source = self.root / "legacy/runtime"
        source.mkdir(parents=True)
        (source / "morning_briefing.py").write_text("old", encoding="utf-8")
        name = "respected-morning-briefing-" + hashlib.sha256(str(self.vault).encode()).hexdigest()[:12]
        xml = '<Task><Actions><Exec><Command>third-party.exe</Command><Arguments>' + source.as_posix() + '</Arguments></Exec></Actions></Task>'
        backend = self.backend()
        for kind in ("task", "shortcut"):
            with self.subTest(kind=kind), mock.patch.object(backend, "_registry_read", return_value=None), mock.patch.object(backend, "_task_read", side_effect=lambda key: canonical_task_xml(xml) if kind == "task" and key == name else None), mock.patch.object(backend, "_shortcut_read", return_value=canonical_json({"target":"third-party.exe", "arguments":source.as_posix()}) if kind == "shortcut" else None):
                with self.assertRaises(OwnershipConflict):
                    backend.inspect_legacy_registrations(source, self.vault, self.ctx.paths, self.profile)

    def test_legacy_inno_snapshot_parses_quoted_exact_uninstaller_path(self):
        from respectedbrain.integrations.backend import canonical_json
        source = self.root / "Old Install/runtime"
        source.mkdir(parents=True)
        uninstaller = source.parent / "unins000.exe"
        uninstaller.write_bytes(b"MZ")
        record = canonical_json({"values":{"InstallLocation":{"type":1,"data":str(source.parent)},"UninstallString":{"type":1,"data":'"' + str(uninstaller) + '"'}},"subkeys":{}})
        backend = self.backend()
        with mock.patch.object(backend, "_registry_read", return_value=record), mock.patch.object(backend, "_task_read", return_value=None), mock.patch.object(backend, "_shortcut_read", return_value=None):
            rows = backend.inspect_legacy_registrations(source, self.vault, self.ctx.paths, self.profile)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].kind, rows[0].before, rows[0].after), ("registry", record, record))

    def test_disabled_legacy_hook_cleanup_preserves_existing_empty_user_hook(self):
        import sys
        source = self.root / "legacy"
        script = source / "hooks/bridge.py"
        script.parent.mkdir(parents=True)
        script.write_text("old", encoding="utf-8")
        path = self.home / ".claude/settings.json"
        path.parent.mkdir()
        user = {"matcher":"user-owned-empty", "hooks":[]}
        old = {"type":"command", "command":__import__("subprocess").list2cmdline([sys.executable,str(script),"--global-hook"])}
        path.write_text(json.dumps({"hooks":{"SessionStart":[{"hooks":[old]},user]},"custom":True}), encoding="utf-8")
        backend = self.backend()
        with mock.patch.object(backend, "_registry_read", return_value=None), mock.patch.object(backend, "_task_read", return_value=None), mock.patch.object(backend, "_shortcut_read", return_value=None):
            rows = backend.preview_migration(self.ctx,legacy_root=source,vault=self.vault,roots=self.ctx.paths,profile=self.profile,desired={})
        after = json.loads(next(row.after for row in rows if row.key == str(path)))
        self.assertEqual(after["hooks"]["SessionStart"], [user])
        self.assertTrue(after["custom"])

    def test_global_skills_never_replace_unowned_or_user_changed_content(self):
        from respectedbrain.integrations.rendering import plan_integrations
        from respectedbrain.installation.ownership import OwnershipManifest, manifest_document
        path = self.home / ".agents/skills/beyin-doktor/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"user custom skill")
        for owned in (False, True):
            if owned:
                self.data.mkdir(parents=True,exist_ok=True)
                record = ExternalChange("file",str(path),None,b"previous owned")
                (self.data / "install-manifest.json").write_text(json.dumps(manifest_document(OwnershipManifest(3,(),(record,)))),encoding="utf-8")
            before = snapshot(self.root)
            with self.subTest(owned=owned), self.assertRaises(OwnershipConflict):
                plan_integrations(self.ctx,self.profile,{"global":True},self.backend())
            self.assertEqual(snapshot(self.root),before)

    def test_skill_upgrade_accepts_unchanged_recorded_ownership_and_package_baseline(self):
        from respectedbrain.integrations.rendering import plan_integrations
        from respectedbrain.installation.ownership import OwnershipManifest, manifest_document
        path = self.home / ".agents/skills/beyin-doktor/SKILL.md"
        path.parent.mkdir(parents=True)
        baseline = self.ctx.resources.read_text("skills/beyin-doktor/SKILL.md").encode()
        path.write_bytes(baseline)
        rows = plan_integrations(self.ctx,self.profile,{"global":True},self.backend())
        self.assertNotIn(str(path),{row.key for row in rows})
        path.write_bytes(b"previous owned version")
        self.data.mkdir(parents=True,exist_ok=True)
        record=ExternalChange("file",str(path),None,b"previous owned version")
        (self.data / "install-manifest.json").write_text(json.dumps(manifest_document(OwnershipManifest(3,(),(record,)))),encoding="utf-8")
        rows=plan_integrations(self.ctx,self.profile,{"global":True},self.backend())
        self.assertEqual(next(row.after for row in rows if row.key==str(path)),baseline)

    def test_global_hooks_refuse_spoofed_managed_flags_and_preserve_empty_user_groups(self):
        from respectedbrain.integrations.rendering import plan_integrations
        path=self.home / ".claude/settings.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"hooks":{"SessionStart":[{"hooks":[{"command":"third-party.exe --global-hook --provider claude"}]}]}}),encoding="utf-8")
        with self.assertRaises(OwnershipConflict):
            plan_integrations(self.ctx,self.profile,{"global":True},self.backend())
        user={"matcher":"user-empty","hooks":[]}
        path.write_text(json.dumps({"hooks":{"SessionStart":[user]},"custom":True}),encoding="utf-8")
        rows=plan_integrations(self.ctx,self.profile,{"global":True},self.backend())
        after=json.loads(next(row.after for row in rows if row.key==str(path)))
        self.assertIn(user,after["hooks"]["SessionStart"])
        self.assertTrue(after["custom"])

    def test_generated_mcp_tool_files_cannot_replace_unowned_content(self):
        from respectedbrain.integrations.rendering import plan_integrations
        path=self.home / ".gemini/antigravity-ide/mcp/respected-vault/instructions.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"my own MCP instructions")
        before=snapshot(self.root)
        with self.assertRaises(OwnershipConflict):
            plan_integrations(self.ctx,self.profile,{"mcp":True},self.backend())
        self.assertEqual(snapshot(self.root),before)

    def test_native_shortcut_uses_public_dashboard_command(self):
        from respectedbrain.integrations.rendering import plan_integrations
        backend=mock.Mock()
        backend.read.return_value=None
        rows=plan_integrations(self.ctx,self.profile,{"shortcut":True},backend)
        descriptor=json.loads(rows[0].after)
        self.assertEqual(descriptor["arguments"],"dashboard --vault-id " + self.ctx.paths.vault_id)

    def test_legacy_external_rollback_bytes_are_separate_from_uninstall_baseline(self):
        from respectedbrain.installation.ownership import OwnershipManifest,manifest_document,decode_bytes
        from respectedbrain.installation.transaction import Transaction
        from tests.foundation_transactions_test import Backend
        source=self.root / "legacy"
        source.mkdir()
        path=self.home / ".codex/AGENTS.md"
        path.parent.mkdir()
        original=("User before\n<!-- RESPECTED-GLOBAL:BEGIN -->\nVault " + str(self.vault) + "\n<!-- RESPECTED-GLOBAL:END -->\nUser after\n").encode()
        path.write_bytes(original)
        backend=self.backend()
        with mock.patch.object(backend,"_task_read",return_value=None),mock.patch.object(backend,"_shortcut_read",return_value=None),mock.patch.object(backend,"_registry_read",return_value=None):
            rows=backend.preview_migration(self.ctx,legacy_root=source,vault=self.vault,roots=self.ctx.paths,profile=self.profile,desired={"global":True})
        row=next(item for item in rows if item.key==str(path))
        self.assertEqual(row.before,original)
        self.assertTrue(row.has_uninstall_baseline)
        self.assertIn(b"User before",row.uninstall_before)
        self.assertIn(b"User after",row.uninstall_before)
        self.assertNotIn(b"RESPECTED-GLOBAL",row.uninstall_before)
        document=manifest_document(OwnershipManifest(3,(),(row,)))
        self.assertEqual(decode_bytes(document["external"][0]["before"]),row.uninstall_before)
        fake=Backend()
        fake.records[(row.kind,row.key)]=original
        with self.assertRaisesRegex(RuntimeError,"fault"):
            with Transaction(self.data,fake) as transaction:
                transaction.apply_external(row)
                raise RuntimeError("fault")
        self.assertEqual(fake.read(row.kind,row.key),original)

    def test_retired_legacy_native_task_has_no_uninstall_resurrection_baseline(self):
        import hashlib,sys,subprocess
        from respectedbrain.integrations.backend import canonical_task_xml
        from respectedbrain.integrations.scheduling.service import _windows_xml
        source=self.root / "legacy"
        source.mkdir()
        script=source / "morning_briefing.py"
        script.write_text("old",encoding="utf-8")
        name="respected-morning-briefing-"+hashlib.sha256(str(self.vault).encode()).hexdigest()[:12]
        task=canonical_task_xml(_windows_xml(sys.executable,subprocess.list2cmdline([str(script),"--vault-root",str(self.vault),"--if-due"])))
        backend=self.backend()
        with mock.patch.object(backend,"_task_read",side_effect=lambda key: task if key==name else None),mock.patch.object(backend,"_shortcut_read",return_value=None),mock.patch.object(backend,"_registry_read",return_value=None):
            rows=backend.preview_migration(self.ctx,legacy_root=source,vault=self.vault,roots=self.ctx.paths,profile=self.profile,desired={})
        row=next(item for item in rows if item.kind=="task")
        self.assertEqual(row.before,task)
        self.assertIsNone(row.after)
        self.assertTrue(row.has_uninstall_baseline)
        self.assertIsNone(row.uninstall_before)


if __name__ == '__main__':
    unittest.main()
