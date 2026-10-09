"""Repair coordinates every vault writer before mutating the shared app root.

The reported F1 finding: repair built its mutation transaction scoped to the
selected vault UUID while it replaces shared AppRoot files, the shared
``install-manifest.json`` and shared integration records. A writer lease held by
any other vault must therefore block the mutation, exactly as update/setup/
uninstall already require.
"""
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from respectedbrain.core.config import ConfigStore
from respectedbrain.core.coordination import writer_lease, quiesce_writers
from respectedbrain.core.errors import BusyError
from respectedbrain.core.paths import Roots
from respectedbrain.vault.registry import VaultRegistry, build_context
from respectedbrain.installation.setup import setup as production_setup
from respectedbrain.installation.repair import repair as production_repair
from respectedbrain.installation.transaction import Transaction, recover_transactions
from tests.foundation_install_support import seed_package
from tests.foundation_support import snapshot
from tests.foundation_transactions_test import Backend


def setup(*args, **kwargs):
    kwargs.setdefault("require_provenance", False)
    return production_setup(*args, **kwargs)


def repair(*args, **kwargs):
    kwargs.setdefault("require_provenance", False)
    return production_repair(*args, **kwargs)


class RepairWriterCoordinationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.vault = self.root / "Vault A"
        self.vault.mkdir()
        self.roots = Roots(self.root / "app", self.root / "data", self.vault)
        self.backend = Backend()
        self.desired = dict.fromkeys(("global", "mcp", "schedule", "shortcut"), False)
        self.health = patch("respectedbrain.installation.payload.validate_installed_health", return_value=None)
        self.health.start()
        self.addCleanup(self.health.stop)
        package = seed_package(self.root / "package")
        self.assertTrue(setup(self.roots, self.vault, profile={}, desired=self.desired,
                              backend=self.backend, package=package).success)
        store = ConfigStore(self.roots.data_root)
        self.ctx_a = build_context(self.roots, store, vault=self.vault, vault_id=None, env={})
        self.other = self.root / "Vault B"
        self.other.mkdir()
        (self.other / "Core.md").write_bytes(b"other")
        VaultRegistry(store).register(self.other)
        self.ctx_b = build_context(self.roots, store, vault=self.other, vault_id=None, env={})
        # Real cross-process locks; the default test backend has a stubbed quiesce.
        self.backend.quiesce = lambda identity: quiesce_writers(self.roots.data_root, identity)
        self.next_package = seed_package(self.root / "next", content=b"MZ-new")

    def manifest(self) -> bytes:
        return (self.roots.data_root / "install-manifest.json").read_bytes()

    def test_repair_mutation_transaction_quiesces_every_vault(self):
        calls = []
        delegate = self.backend.quiesce

        def recording(vault_id):
            calls.append(vault_id)
            return delegate(vault_id)

        self.backend.quiesce = recording
        result = repair(self.ctx_a, backend=self.backend, package=self.next_package)
        self.assertTrue(result.success, result.conflicts)
        self.assertTrue(calls, "repair must quiesce writers before mutating shared roots")
        self.assertEqual(set(calls), {None}, "repair must coordinate every vault, not only the selected UUID")

    def test_repair_for_one_vault_is_blocked_by_writer_in_another_vault(self):
        # Drop the recovery fast path so this isolates the mutation transaction:
        # with no backups directory recover_transactions returns without quiescing.
        shutil.rmtree(self.roots.data_root / "backups")
        app_before = snapshot(self.roots.app_root)
        manifest_before = self.manifest()
        config_before = (self.roots.data_root / "config.json").read_bytes()
        with writer_lease(self.ctx_b):
            result = repair(self.ctx_a, backend=self.backend, package=self.next_package)
        self.assertFalse(result.success)
        self.assertFalse(result.pending)
        self.assertIn("lock", " ".join(result.conflicts).lower())
        self.assertEqual(snapshot(self.roots.app_root), app_before)
        self.assertEqual(self.manifest(), manifest_before)
        self.assertEqual((self.roots.data_root / "config.json").read_bytes(), config_before)

    def test_repair_succeeds_and_verifies_after_other_vault_writer_is_released(self):
        target = self.roots.app_root / "respectedbrain.exe"
        target.write_bytes(b"corrupt-owned")
        with writer_lease(self.ctx_b):
            blocked = repair(self.ctx_a, backend=self.backend, package=self.next_package)
        self.assertFalse(blocked.success)
        self.assertEqual(target.read_bytes(), b"corrupt-owned")
        restored = repair(self.ctx_a, backend=self.backend, package=self.next_package)
        self.assertTrue(restored.success, restored.conflicts)
        self.assertEqual(target.read_bytes(), b"MZ-new")

    def test_recovery_coordinates_every_vault_and_rolls_back_interrupted_repair(self):
        target = self.roots.app_root / "respectedbrain.exe"
        with Transaction(self.roots.data_root, self.backend) as tx:
            tx.write(target, b"interrupted")
            tx.commit()
        document = json.loads(tx.journal.read_text(encoding="utf-8"))
        document["status"] = "active"
        tx.journal.write_text(json.dumps(document), encoding="utf-8")
        with writer_lease(self.ctx_b):
            with self.assertRaises(BusyError):
                recover_transactions(self.roots.data_root, self.backend)
        self.assertEqual(target.read_bytes(), b"interrupted")
        recover_transactions(self.roots.data_root, self.backend)
        self.assertEqual(target.read_bytes(), b"MZ-fixture")


if __name__ == "__main__":
    unittest.main()
