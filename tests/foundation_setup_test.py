"""Setup creates a pure vault once and never templates over registered notes."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from respectedbrain.core.paths import Roots
from respectedbrain.core.config import ConfigStore
from respectedbrain.installation.setup import setup
from respectedbrain.installation.ownership import read_manifest
from tests.foundation_install_support import seed_package
from tests.foundation_support import snapshot, note_hashes
from tests.foundation_transactions_test import Backend


class FoundationSetupTest(unittest.TestCase):
    def test_repeated_setup_refuses_manifest_file_outside_program_root(self):
        from dataclasses import replace
        from respectedbrain.installation.ownership import OwnedFile, digest, manifest_document
        self.assertTrue(self.install().success)
        sentinel = self.root / 'human-note.md'
        sentinel.write_bytes(b'user')
        manifest_path = self.roots.data_root / 'install-manifest.json'
        manifest = read_manifest(manifest_path)
        manifest_path.write_text(json.dumps(manifest_document(replace(manifest, files=manifest.files + (OwnedFile(sentinel, digest(sentinel), 'application'),)))), encoding='utf-8')
        before = snapshot(self.roots.app_root)
        result = self.install()
        self.assertFalse(result.success)
        self.assertEqual(sentinel.read_bytes(), b'user')
        self.assertEqual(snapshot(self.roots.app_root), before)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "home").mkdir()
        self.vault = self.root / "Türkçe 🧠 Vault"
        self.roots = Roots(self.root / "app", self.root / "data", self.vault)
        self.package = seed_package(self.root / "package")
        self.backend = Backend()
        self.desired = dict.fromkeys(("global", "mcp", "schedule", "shortcut"), False)
        self.health = patch("respectedbrain.installation.payload.validate_installed_health", return_value=None)
        self.health.start()
        self.addCleanup(self.health.stop)

    def install(self, **kwargs):
        kwargs.setdefault("require_provenance", False)
        return setup(self.roots, self.vault, profile={"OS_NAME": "RespectedOS", "USER_NAME": "Ada", "USER_BIO": "Test", "COMPANION": "Atlas", "platform": "windows-native", "user_home": str(self.root / "home")}, desired=self.desired, backend=self.backend, package=kwargs.pop("package", self.package), **kwargs)

    def test_fresh_setup_is_pure_vault(self):
        result = self.install()
        self.assertTrue(result.success, result.conflicts)
        marker = json.loads((self.vault / ".respected.json").read_text())
        config = ConfigStore(self.roots.data_root).read()
        self.assertEqual(marker["schema_version"], 3)
        self.assertEqual(config["active_vault_id"], marker["vault_id"])
        self.assertFalse(config["integrations"]["schedule"])
        self.assertFalse((self.vault / ".beyin").exists())
        self.assertFalse((self.vault / "unins000.exe").exists())
        self.assertFalse(any(self.vault.rglob("*.db")))
        self.assertIn("Atlas", (self.vault / "🔮 850-Companion/Core.md").read_text(encoding="utf-8"))
        self.assertNotIn("{{", (self.vault / "🔮 850-Companion/Core.md").read_text(encoding="utf-8"))

    def test_nonempty_unregistered_target_is_untouched(self):
        self.vault.mkdir()
        (self.vault / "keep.py").write_bytes(b"user")
        before = snapshot(self.root)
        result = self.install()
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.root), before)

    def test_manifest_does_not_own_user_notes_and_repeat_preserves_edits(self):
        self.assertTrue(self.install().success)
        core = self.vault / "🔮 850-Companion/Core.md"
        core.write_text("# Kullanıcı\nÖzel kimlik.", encoding="utf-8")
        before = note_hashes(self.vault)
        self.assertTrue(self.install(package=None).success)
        self.assertEqual(note_hashes(self.vault), before)
        manifest = read_manifest(self.roots.data_root / "install-manifest.json")
        self.assertTrue(manifest.files)
        self.assertFalse(any(item.path.is_relative_to(self.vault) or item.role == "note" for item in manifest.files))

    def test_missing_or_changed_application_is_not_success(self):
        self.assertFalse(self.install(package=None).success)
        self.assertTrue(self.install().success)
        (self.roots.app_root / "respectedbrain.exe").write_bytes(b"changed")
        before = note_hashes(self.vault)
        self.assertFalse(self.install(package=None).success)
        self.assertEqual(note_hashes(self.vault), before)

    def test_busy_writer_blocks_activation(self):
        self.backend.busy = True
        before = snapshot(self.roots.app_root)
        result = self.install()
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.roots.app_root), before)
        self.assertFalse(self.vault.exists())

    def test_profile_provider_is_saved_and_repeat_preserves_preference(self):
        result = setup(self.roots, self.vault, profile={"summary_provider": "codex"}, desired=self.desired,
                       backend=self.backend, package=self.package, require_provenance=False)
        self.assertTrue(result.success, result.conflicts)
        self.assertEqual(ConfigStore(self.roots.data_root).read()["preferences"]["summary_provider"], "codex")
        self.assertTrue(self.install(package=None).success)
        self.assertEqual(ConfigStore(self.roots.data_root).read()["preferences"]["summary_provider"], "codex")

    def test_gui_and_cli_use_shared_setup_service(self):
        from respectedbrain.installation import wizard
        from respectedbrain.installation.transaction import OperationResult
        with patch.object(wizard, "setup", return_value=OperationResult(False, "test", ("injected",))) as service:
            result = wizard.run_action("install", self.roots, self.vault, profile={"USER_NAME": "Ada"}, desired=self.desired, backend=self.backend, package=self.package)
        self.assertFalse(result.success)
        self.assertEqual(service.call_args.args, (self.roots, self.vault))
        self.assertEqual(service.call_args.kwargs["package"], self.package)

    def test_local_hooks_are_owned_through_maintenance_and_removed_without_notes(self):
        from respectedbrain.integrations.backend import NativeBackend
        from respectedbrain.installation.update import update
        from respectedbrain.installation.repair import repair
        from respectedbrain.installation.uninstall import uninstall
        from respectedbrain.vault.registry import build_context
        names = ('.agents/hooks.json', '.claude/settings.json', '.codex/hooks.json',
                 '.cursor/hooks.json', '.gemini/settings.json')
        for purge in (True, False):
            with self.subTest(purge=purge):
                root = self.root / str(purge)
                home = root / 'home'
                home.mkdir(parents=True)
                roots = Roots(root / 'app', root / 'data', root / 'vault')
                backend = NativeBackend(roots.data_root)
                result = setup(roots, roots.default_vault, profile={'platform': 'windows-native',
                    'user_home': str(home)}, desired=self.desired, backend=backend,
                    package=self.package, require_provenance=False)
                self.assertTrue(result.success, result.conflicts)
                ctx = build_context(roots, ConfigStore(roots.data_root), vault=roots.default_vault, vault_id=None, env={})
                notes = note_hashes(roots.default_vault)
                expected = {str(roots.default_vault / name) for name in names}
                for operation in (lambda: update(ctx, package=self.package, backend=backend, require_provenance=False),
                                  lambda: repair(ctx, backend=backend, require_provenance=False)):
                    result = operation()
                    self.assertTrue(result.success, result.conflicts)
                    manifest = read_manifest(roots.data_root / 'install-manifest.json')
                    self.assertTrue(expected.issubset({item.key for item in manifest.external}))
                    self.assertTrue(all((roots.default_vault / name).exists() for name in names))
                result = uninstall(ctx, backend=backend, purge_data=purge)
                self.assertTrue(result.success, result.conflicts)
                self.assertTrue(all(not (roots.default_vault / name).exists() for name in names))
                self.assertEqual(note_hashes(roots.default_vault), notes)

    def test_uninstall_preserves_changed_local_hook_and_reports_conflict(self):
        from respectedbrain.integrations.backend import NativeBackend
        from respectedbrain.installation.uninstall import uninstall
        from respectedbrain.vault.registry import build_context
        self.backend = NativeBackend(self.roots.data_root)
        self.assertTrue(self.install().success)
        ctx = build_context(self.roots, ConfigStore(self.roots.data_root), vault=self.vault, vault_id=None, env={})
        path = self.vault / '.claude/settings.json'
        document = json.loads(path.read_text(encoding='utf-8'))
        document['user-setting'] = 'preserve this'
        path.write_text(json.dumps(document), encoding='utf-8')
        before = path.read_bytes()
        notes = note_hashes(self.vault)
        result = uninstall(ctx, backend=self.backend)
        self.assertFalse(result.success)
        self.assertIn('file:' + str(path), result.conflicts)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(note_hashes(self.vault), notes)

    def test_local_hook_registration_rolls_back_when_install_health_fails(self):
        from respectedbrain.integrations.backend import NativeBackend
        self.backend = NativeBackend(self.roots.data_root)
        with patch('respectedbrain.installation.payload.validate_installed_health', side_effect=OSError('health failure')):
            result = self.install()
        self.assertFalse(result.success)
        self.assertEqual(result.conflicts, ('health failure',))
        self.assertFalse(self.vault.exists())
