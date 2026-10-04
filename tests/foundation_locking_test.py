"""A newly created empty lock file can already be locked by another writer."""
import os
from pathlib import Path
import tempfile
import unittest
from respectedbrain.core.errors import BusyError
from respectedbrain.core.locking import exclusive_lock, shared_lock


@unittest.skipUnless(os.name == "nt", "Windows byte range locking regression")
class FoundationLockingTest(unittest.TestCase):
    def test_empty_locked_file_reports_busy_instead_of_writing_locked_byte(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "writer.lock"
            descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                for lock in (exclusive_lock, shared_lock):
                    with self.subTest(lock=lock.__name__), self.assertRaises(BusyError):
                        with lock(path, timeout=0):
                            self.fail("Another handle's empty file lock was bypassed")
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                os.close(descriptor)
