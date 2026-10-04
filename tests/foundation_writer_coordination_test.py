"""Product writers and installation share an admission gate."""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from respectedbrain.core.coordination import writer_lease, quiesce_writers
from respectedbrain.core.errors import BusyError
from respectedbrain.installation.transaction import Transaction
from tests.foundation_support import make_context
from tests.foundation_transactions_test import Backend


class FoundationWriterCoordinationTest(unittest.TestCase):
    def test_standalone_maps_obeys_operation_admission(self):
        from unittest.mock import patch
        from respectedbrain.core.locking import exclusive_lock
        from respectedbrain.vault.maps import rebuild_maps
        with tempfile.TemporaryDirectory() as temporary:
            ctx = make_context(Path(temporary))
            with exclusive_lock(ctx.paths.data_root / ".operation.lock", timeout=0):
                with patch("respectedbrain.core.coordination.writer_lease", lambda ctx, timeout: writer_lease(ctx, timeout=0)):
                    with self.assertRaises(BusyError):
                        rebuild_maps(ctx)
            self.assertFalse((ctx.paths.vault_root / "🎯 100-Command-Center/Vault-Map.md").exists())

    def test_live_writer_blocks_installation_and_operation_blocks_new_writer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ctx = make_context(root)
            backend = Backend()
            backend.quiesce = lambda identity: quiesce_writers(ctx.paths.data_root, identity)
            ready, release = root / "ready", root / "release"
            code = "from pathlib import Path; import time; from tests.foundation_support import make_context; from respectedbrain.core.coordination import writer_lease;\nctx=make_context(Path(%r));\nwith writer_lease(ctx):\n Path(%r).touch()\n while not Path(%r).exists(): time.sleep(.02)" % (str(root), str(ready), str(release))
            child = subprocess.Popen([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1])
            try:
                for _ in range(500):
                    if ready.exists():
                        break
                    time.sleep(.01)
                self.assertTrue(ready.exists())
                with self.assertRaises(BusyError):
                    with Transaction(ctx.paths.data_root, backend, vault_id=ctx.paths.vault_id):
                        self.fail("Activation reached while a writer was active")
            finally:
                release.touch()
                child.wait(timeout=10)
            with Transaction(ctx.paths.data_root, backend, vault_id=ctx.paths.vault_id):
                with self.assertRaises(BusyError):
                    with writer_lease(ctx):
                        self.fail("A new writer entered while activation held admission")

    def test_nested_services_share_one_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx = make_context(Path(temporary))
            with writer_lease(ctx):
                with writer_lease(ctx):
                    self.assertTrue((ctx.paths.state_dir / "writer.lock").is_file())

    def test_independent_writers_can_overlap_while_activation_is_excluded(self):
        import threading
        with tempfile.TemporaryDirectory() as temporary:
            ctx = make_context(Path(temporary))
            ready, release = threading.Event(), threading.Event()
            def other():
                with writer_lease(ctx, timeout=2):
                    ready.set()
                    release.wait(4)
            with writer_lease(ctx):
                thread = threading.Thread(target=other)
                thread.start()
                try:
                    self.assertTrue(ready.wait(2))
                finally:
                    release.set()
                    thread.join(4)

    def test_background_orchestration_holds_a_writer_lease(self):
        import threading
        from types import SimpleNamespace
        from respectedbrain.orchestration.runner import execute_owned_worker
        with tempfile.TemporaryDirectory() as temporary:
            ctx = make_context(Path(temporary))
            ready, release = threading.Event(), threading.Event()
            backend = Backend()
            backend.quiesce = lambda identity: quiesce_writers(ctx.paths.data_root, identity)
            execution = SimpleNamespace(execute_worker=lambda: (ready.set(), release.wait(5)))
            thread = threading.Thread(target=execute_owned_worker, args=(ctx, execution))
            thread.start()
            try:
                self.assertTrue(ready.wait(5))
                with self.assertRaises(BusyError):
                    with Transaction(ctx.paths.data_root, backend):
                        self.fail("Activation entered during background worker")
            finally:
                release.set()
                thread.join(5)
