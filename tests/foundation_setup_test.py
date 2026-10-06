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
                       backend=self.backend, package=self.package)
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
