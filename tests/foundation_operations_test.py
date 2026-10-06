"""Update/repair/uninstall share transaction and preserve notes and user flags."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from respectedbrain.core.config import ConfigStore
from respectedbrain.installation.setup import setup
from respectedbrain.installation.update import update
from respectedbrain.installation.repair import repair
from respectedbrain.installation.uninstall import uninstall
from respectedbrain.core.paths import Roots
from respectedbrain.vault.registry import build_context
from respectedbrain.integrations.backend import ExternalChange
from respectedbrain.installation.ownership import read_manifest, manifest_document
from tests.foundation_install_support import seed_package
from tests.foundation_support import note_hashes, snapshot
from tests.foundation_transactions_test import Backend


class FoundationOperationsTest(unittest.TestCase):
    def test_maintenance_retains_migrated_technical_ownership_without_adopting_edits(self):
        from dataclasses import replace
        from respectedbrain.installation.ownership import OwnedFile, digest
        path = self.ctx.paths.state_dir / 'migration-receipts/fixture.json'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'original-receipt')
        owned = OwnedFile(path, digest(path), 'technical')
        manifest_path = self.roots.data_root / 'install-manifest.json'
        previous = read_manifest(manifest_path)
        manifest_path.write_text(json.dumps(manifest_document(replace(previous, files=previous.files + (owned,)))), encoding='utf-8')
        path.write_bytes(b'user-edited')
        for action in (lambda: update(self.ctx, package=self.next_package, backend=self.backend),
                       lambda: repair(self.ctx, backend=self.backend),
                       lambda: setup(self.roots, self.vault, profile={}, desired=self.desired, backend=self.backend, package=self.next_package)):
            result = action()
            self.assertTrue(result.success, result.conflicts)
            self.assertIn(owned, read_manifest(manifest_path).files)
            self.assertEqual(path.read_bytes(), b'user-edited')
        result = uninstall(self.ctx, backend=self.backend, purge_data=True)
        self.assertFalse(result.success)
        self.assertEqual(path.read_bytes(), b'user-edited')

    def test_update_reads_manifest_after_interrupted_activation_is_recovered(self):
        from dataclasses import replace
        from respectedbrain.installation.ownership import digest
        from respectedbrain.installation.transaction import Transaction
        target = self.roots.app_root / 'respectedbrain.exe'
        path = self.roots.data_root / 'install-manifest.json'
        previous = read_manifest(path)
        with Transaction(self.roots.data_root, self.backend) as tx:
            tx.write(target, b'interrupted-version')
            files = tuple(replace(item, sha256=digest(target)) if item.path == target else item for item in previous.files)
            tx.write_json(path, manifest_document(replace(previous, files=files)))
            tx.commit()
        document = json.loads(tx.journal.read_text())
        document['status'] = 'active'
        tx.journal.write_text(json.dumps(document), encoding='utf-8')
        result = update(self.ctx, package=self.next_package, backend=self.backend)
        self.assertTrue(result.success, result.conflicts)
        self.assertEqual(target.read_bytes(), b'MZ-new')

    def test_update_detects_edit_after_health_and_preserves_user_bytes(self):
        from respectedbrain.installation.transaction import Transaction
        checkpoint = Transaction.checkpoint
        target = self.roots.app_root / 'respectedbrain.exe'
        def edit(tx, phase):
            checkpoint(tx, phase)
            if phase == 'cleanup':
                target.write_bytes(b'user-edited')
        with patch.object(Transaction, 'checkpoint', edit):
            result = update(self.ctx, package=self.next_package, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(target.read_bytes(), b'user-edited')
        self.assertIn(str(target), result.conflicts)

    def test_health_timeout_returns_failure_and_restores_application(self):
        import subprocess
        before = snapshot(self.roots.app_root)
        self.health.stop()
        with patch('respectedbrain.installation.payload.subprocess.run', side_effect=subprocess.TimeoutExpired('fixture', 30)):
            result = update(self.ctx, package=self.next_package, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.roots.app_root), before)

    def test_corrupt_ownership_manifest_is_controlled_failure(self):
        manifest_path = self.roots.data_root / 'install-manifest.json'
        before = snapshot(self.roots.app_root)
        for document in ([], {'schema_version': 3}, {'schema_version': 3, 'files': [None], 'external': []}):
            with self.subTest(document=document):
                manifest_path.write_text(json.dumps(document), encoding='utf-8')
                result = update(self.ctx, package=self.next_package, backend=self.backend)
                self.assertFalse(result.success)
                self.assertEqual(snapshot(self.roots.app_root), before)

    def test_distribution_member_alias_is_rejected(self):
        from respectedbrain.installation.payload import validate_package
        from respectedbrain.core.errors import OwnershipConflict
        path = self.next_package / 'distribution.json'
        document = json.loads(path.read_text())
        document['files']['./respectedbrain.exe'] = document['files']['respectedbrain.exe']
        path.write_text(json.dumps(document), encoding='utf-8')
        with self.assertRaises(OwnershipConflict):
            validate_package(self.next_package)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.vault = self.root / "Türkçe 🧠 Vault"
        self.roots = Roots(self.root / "app", self.root / "data", self.vault)
        self.backend = Backend()
        self.desired = dict.fromkeys(("global", "mcp", "schedule", "shortcut"), False)
        self.health = patch("respectedbrain.installation.payload.validate_installed_health", return_value=None)
        self.health.start()
        self.addCleanup(self.health.stop)
        package = seed_package(self.root / "package")
        self.assertTrue(setup(self.roots, self.vault, profile={}, desired=self.desired, backend=self.backend, package=package).success)
        store = ConfigStore(self.roots.data_root)
        store.update(lambda value: value["preferences"].update(summary_provider="codex"))
        self.ctx = build_context(self.roots, store, vault=self.vault, vault_id=None, env={})
        self.next_package = seed_package(self.root / "new", content=b"MZ-new")
        self.other = self.root / "İkinci Vault"
        self.other.mkdir()
        (self.other / "Core.md").write_bytes(b"other")

    def test_operations_preserve_notes_and_disabled_flags(self):
        before, other = note_hashes(self.vault), snapshot(self.other)
        self.assertTrue(update(self.ctx, package=self.next_package, backend=self.backend).success)
        self.assertTrue(repair(self.ctx, backend=self.backend).success)
        config = ConfigStore(self.roots.data_root).read()
        self.assertEqual(config["integrations"], self.desired)
        self.assertEqual(config["preferences"]["summary_provider"], "codex")
        self.assertEqual(note_hashes(self.vault), before)
        self.assertEqual(snapshot(self.other), other)

    def test_failed_update_restores_app_config_and_external_records(self):
        phases = ("backup", "stage", "activate", "config", "integrations", "health", "cleanup")
        before_app = snapshot(self.roots.app_root)
        before_config = (self.roots.data_root / "config.json").read_bytes()
        from respectedbrain.installation.transaction import Transaction
        checkpoint = Transaction.checkpoint
        for phase in phases:
            with self.subTest(phase=phase):
                def fault(tx, name):
                    checkpoint(tx, name)
                    if name == phase:
                        (self.roots.app_root / "sentinel.txt").write_bytes(b"user")
                        raise OSError("fault:" + phase)
                with patch.object(Transaction, "checkpoint", fault):
                    result = update(self.ctx, package=self.next_package, backend=self.backend)
                self.assertFalse(result.success)
                self.assertEqual((self.roots.app_root / "sentinel.txt").read_bytes(), b"user")
                (self.roots.app_root / "sentinel.txt").unlink()
                self.assertEqual(snapshot(self.roots.app_root), before_app)
                self.assertEqual((self.roots.data_root / "config.json").read_bytes(), before_config)

    def test_uninstall_preserves_data_by_default_and_unknown_files(self):
        before = note_hashes(self.vault)
        unknown = self.roots.app_root / "user.py"
        unknown.write_bytes(b"user")
        result = uninstall(self.ctx, backend=self.backend)
        self.assertTrue(result.success, result.conflicts)
        self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
        self.assertEqual(unknown.read_bytes(), b"user")
        self.assertTrue((self.roots.data_root / "config.json").exists())
        uninstall(self.ctx, backend=self.backend, purge_data=True)
        self.assertEqual(note_hashes(self.vault), before)

    def test_owned_record_changed_by_user_is_retained(self):
        manifest_path = self.roots.data_root / "install-manifest.json"
        manifest = read_manifest(manifest_path)
        from respectedbrain.installation.ownership import OwnershipManifest
        change = ExternalChange("mcp", "test", b"old", b"owned")
        manifest_path.write_text(json.dumps(manifest_document(OwnershipManifest(3, manifest.files, (change,)))), encoding="utf-8")
        self.backend.records[("mcp", "test")] = b"user"
        result = uninstall(self.ctx, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(self.backend.read("mcp", "test"), b"user")
        self.assertIn("mcp:test", result.conflicts)

    def test_active_inno_shell_handles_only_unchanged_own_uninstaller(self):
        from dataclasses import replace
        from respectedbrain.installation.ownership import OwnedFile, digest
        path = self.roots.app_root / "uninstall/unins000.exe"
        path.parent.mkdir()
        path.write_bytes(b"running-shell")
        log = path.with_suffix(".dat")
        log.write_bytes(b"Inno log")
        manifest_path = self.roots.data_root / "install-manifest.json"
        previous = read_manifest(manifest_path)
        items = tuple(OwnedFile(item, digest(item), "uninstaller") for item in (path, log))
        manifest_path.write_text(json.dumps(manifest_document(replace(previous, files=previous.files + items))), encoding="utf-8")
        result = uninstall(self.ctx, backend=self.backend, shell_active=True)
        self.assertTrue(result.success, result.conflicts)
        self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
        self.assertEqual(path.read_bytes(), b"running-shell")
        self.assertEqual(log.read_bytes(), b"Inno log")

    def test_active_shell_refuses_changed_uninstaller(self):
        from dataclasses import replace
        from respectedbrain.installation.ownership import OwnedFile, digest
        path = self.roots.app_root / "uninstall/unins000.dat"
        path.parent.mkdir()
        path.write_bytes(b"owned")
        manifest_path = self.roots.data_root / "install-manifest.json"
        previous = read_manifest(manifest_path)
        manifest_path.write_text(json.dumps(manifest_document(replace(previous, files=previous.files + (OwnedFile(path, digest(path), "uninstaller"),)))), encoding="utf-8")
        path.write_bytes(b"user-edited")
        result = uninstall(self.ctx, backend=self.backend, shell_active=True)
        self.assertFalse(result.success)
        self.assertEqual(path.read_bytes(), b"user-edited")

    def test_changed_owned_application_stops_update_before_activation(self):
        target = self.roots.app_root / "respectedbrain.exe"
        target.write_bytes(b"user-edited")
        before = snapshot(self.roots.app_root)
        result = update(self.ctx, package=self.next_package, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.roots.app_root), before)

    def test_disabled_owned_integrations_restore_original_records(self):
        from respectedbrain.installation.ownership import OwnershipManifest
        path = self.root / "home/.cursor/mcp.json"
        change = ExternalChange("mcp", str(path), b"user-original", b"managed")
        manifest_path = self.roots.data_root / "install-manifest.json"
        manifest = read_manifest(manifest_path)
        manifest_path.write_text(json.dumps(manifest_document(OwnershipManifest(3, manifest.files, (change,)))), encoding="utf-8")
        self.backend.records[(change.kind, change.key)] = change.after
        result = update(self.ctx, package=self.next_package, backend=self.backend)
        self.assertTrue(result.success, result.conflicts)
        self.assertEqual(self.backend.read(change.kind, change.key), change.before)
        self.assertEqual(read_manifest(manifest_path).external, ())

    def test_disabling_user_changed_integration_is_a_conflict(self):
        from respectedbrain.installation.ownership import OwnershipManifest
        change = ExternalChange("mcp", str(self.root / "mcp.json"), None, b"managed")
        path = self.roots.data_root / "install-manifest.json"
        previous = read_manifest(path)
        path.write_text(json.dumps(manifest_document(OwnershipManifest(3, previous.files, (change,)))), encoding="utf-8")
        self.backend.records[(change.kind, change.key)] = b"edited"
        before = snapshot(self.roots.app_root)
        result = update(self.ctx, package=self.next_package, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(self.backend.read(change.kind, change.key), b"edited")
        self.assertEqual(snapshot(self.roots.app_root), before)
