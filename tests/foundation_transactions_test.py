"""Real-file rollback, cross-process exclusion and user edits during rollback."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.foundation_support import snapshot
from respectedbrain.core.errors import BusyError
from respectedbrain.installation.transaction import Transaction, recover_transactions
from respectedbrain.installation.ownership import OwnedFile, OwnershipManifest, prove_ownership


class Backend:
    def __init__(self):
        self.records = {}
        self.busy = False

    def read(self, kind, key):
        return self.records.get((kind, key))

    def apply(self, change):
        if self.read(change.kind, change.key) != change.before:
            raise ValueError("external-conflict")
        self.records[(change.kind, change.key)] = change.after

    def restore(self, change):
        if self.read(change.kind, change.key) != change.after:
            raise ValueError("external-conflict")
        self.records[(change.kind, change.key)] = change.before

    def quiesce(self, vault_id):
        from contextlib import contextmanager
        @contextmanager
        def quiet():
            if self.busy:
                raise BusyError("writer-active")
            yield
        return quiet()


class FoundationTransactionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.target = self.root / "app/product"
        self.target.parent.mkdir()
        self.target.write_bytes(b"old")
        self.source = self.root / "stage"
        self.source.write_bytes(b"new")
        self.backend = Backend()

    def test_fault_rolls_back_exact_file_and_external_bytes(self):
        from types import SimpleNamespace
        change = SimpleNamespace(kind="mcp", key="test", before=None, after=b"new")
        with self.assertRaisesRegex(RuntimeError, "fault"):
            with Transaction(self.data, self.backend) as tx:
                tx.replace(self.source, self.target)
                tx.apply_external(change)
                raise RuntimeError("fault")
        self.assertEqual(self.target.read_bytes(), b"old")
        self.assertIsNone(self.backend.read("mcp", "test"))
        journals = list((self.data / "backups").glob("*/journal.json"))
        self.assertEqual(len(journals), 1)
        self.assertIn('"status": "rolled-back"', journals[0].read_text())

    def test_rollback_preserves_concurrent_user_edit_and_new_sentinel(self):
        sentinel = self.target.parent / "user.txt"
        with self.assertRaises(RuntimeError):
            with Transaction(self.data, self.backend) as tx:
                tx.replace(self.source, self.target)
                self.target.write_bytes(b"user-edited")
                sentinel.write_bytes(b"user")
                raise RuntimeError("fault")
        self.assertEqual(self.target.read_bytes(), b"user-edited")
        self.assertEqual(sentinel.read_bytes(), b"user")
        self.assertIn(str(self.target), tx.result.conflicts)

    def test_restart_recovery_restores_only_unchanged_outputs(self):
        # A real child exits without __exit__, leaving a durable activated journal.
        program = "from pathlib import Path; import os; from tests.foundation_transactions_test import Backend; from respectedbrain.installation.transaction import Transaction; tx=Transaction(Path(%r),Backend()); tx.__enter__(); tx.replace(Path(%r),Path(%r)); os._exit(0)" % (str(self.data), str(self.source), str(self.target))
        child = subprocess.run([sys.executable, "-c", program], cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(self.target.read_bytes(), b"new")
        results = recover_transactions(self.data, self.backend)
        self.assertEqual(len(results), 1)
        self.assertEqual(self.target.read_bytes(), b"old")
        self.assertEqual(recover_transactions(self.data, self.backend), ())

    def test_another_process_blocks_operation_before_target_changes(self):
        ready = self.root / "ready"
        release = self.root / "release"
        program = "from pathlib import Path; import time; from respectedbrain.core.locking import exclusive_lock;\nwith exclusive_lock(Path(%r)):\n Path(%r).touch()\n while not Path(%r).exists(): time.sleep(.02)" % (str(self.data / ".operation.lock"), str(ready), str(release))
        child = subprocess.Popen([sys.executable, "-c", program])
        try:
            import time
            for _ in range(500):
                if ready.exists():
                    break
                time.sleep(.01)
            self.assertTrue(ready.exists())
            with self.assertRaises(BusyError):
                with Transaction(self.data, self.backend) as tx:
                    tx.replace(self.source, self.target)
            self.assertEqual(self.target.read_bytes(), b"old")
        finally:
            release.touch()
            child.wait(timeout=10)

    def test_writer_quiesce_blocks_mutation(self):
        self.backend.busy = True
        with self.assertRaises(BusyError):
            with Transaction(self.data, self.backend) as tx:
                tx.replace(self.source, self.target)
        self.assertEqual(self.target.read_bytes(), b"old")

    def test_hash_ownership_rejects_user_changed_file(self):
        import hashlib
        item = OwnedFile(self.target, hashlib.sha256(b"old").hexdigest(), "application")
        manifest = OwnershipManifest(3, (item,), ())
        self.assertTrue(prove_ownership(self.target, manifest))
        self.target.write_bytes(b"user")
        self.assertFalse(prove_ownership(self.target, manifest))
