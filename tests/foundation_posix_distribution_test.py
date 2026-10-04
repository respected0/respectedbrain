"""WAL metadata contracts; actual POSIX execution and symlink checks skip on Windows."""
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from respectedbrain.core.errors import OwnershipConflict
from respectedbrain.installation.transaction import Transaction, recover_transactions

class Backend:
    @contextmanager
    def quiesce(self, vault_id):
        yield

class FoundationPosixDistributionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.backend = Backend()
    def mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)
    def test_replace_journals_source_and_original_modes(self):
        source, target = self.root / "source", self.root / "target"
        source.write_bytes(b"new launcher")
        target.write_bytes(b"old launcher")
        source.chmod(0o755)
        target.chmod(0o750)
        before_mode, after_mode = self.mode(target), self.mode(source)
        with Transaction(self.data, self.backend) as tx:
            tx.replace(source, target)
            row = tx.document["files"][0]
            self.assertEqual(row.get("before_mode"), before_mode)
            self.assertEqual(row.get("after_mode"), after_mode)
        self.assertEqual(target.read_bytes(), b"old launcher")
        self.assertEqual(self.mode(target), before_mode)
    def test_write_keeps_existing_file_permissions(self):
        target = self.root / "target"
        target.write_bytes(b"before")
        target.chmod(0o750)
        before_mode = self.mode(target)
        with Transaction(self.data, self.backend) as tx:
            tx.write(target, b"after")
            self.assertEqual(tx.document["files"][0].get("after_mode"), before_mode)
            tx.commit()
        self.assertEqual(self.mode(target), before_mode)
    def test_rollback_preserves_concurrent_permission_edit(self):
        target = self.root / "target"
        target.write_bytes(b"before")
        with Transaction(self.data, self.backend) as tx:
            tx.write(target, b"before")
            target.chmod(0o444)
            try:
                result = tx.rollback()
                self.assertIn(str(target), result.conflicts)
                self.assertEqual(target.read_bytes(), b"before")
                self.assertEqual(self.mode(target) & 0o222, 0)
            finally:
                target.chmod(0o666)
                tx.commit()
    @unittest.skipIf(os.name == "nt", "Actual POSIX executable and recovery check requires POSIX")
    def test_launcher_executes_and_recovery_restores_original_mode(self):
        source, target = self.root / "source", self.root / "launcher"
        source.write_text("#!/bin/sh\nprintf new\n", encoding="utf-8")
        target.write_text("#!/bin/sh\nprintf old\n", encoding="utf-8")
        source.chmod(0o755)
        target.chmod(0o751)
        with Transaction(self.data, self.backend) as tx:
            tx.replace(source, target)
            self.assertEqual(subprocess.check_output([str(target)]), b"new")
            journal = tx.journal
            tx.commit()
        document = json.loads(journal.read_text())
        document["status"] = "active"
        journal.write_text(json.dumps(document))
        results = recover_transactions(self.data, self.backend)
        self.assertEqual(results[0].conflicts, ())
        self.assertEqual(self.mode(target), 0o751)
        self.assertEqual(subprocess.check_output([str(target)]), b"old")
    @unittest.skipIf(os.name == "nt", "POSIX same-byte mode rollback requires POSIX")
    def test_same_byte_replacement_rolls_back_permissions(self):
        source, target = self.root / "source", self.root / "target"
        source.write_bytes(b"same")
        target.write_bytes(b"same")
        source.chmod(0o755)
        target.chmod(0o640)
        with Transaction(self.data, self.backend) as tx:
            tx.replace(source, target)
            self.assertEqual(self.mode(target), 0o755)
        self.assertEqual(self.mode(target), 0o640)
    def normalizer(self):
        function = getattr(importlib.import_module("tools.build_installer"), "dereference_distribution_links", None)
        self.assertTrue(callable(function), "Safe frozen-distribution link normalization is missing")
        return function
    def test_regular_distribution_normalization_is_idempotent(self):
        app = self.root / "app"
        (app / "lib").mkdir(parents=True)
        payload = app / "lib/runtime.bin"
        payload.write_bytes(b"native library")
        before = (payload.read_bytes(), self.mode(payload))
        self.normalizer()(app)
        self.normalizer()(app)
        self.assertEqual((payload.read_bytes(), self.mode(payload)), before)
    def link(self, source, target, directory=False):
        try:
            source.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            self.skipTest("Native symlink creation unavailable: " + str(error))
    def test_internal_library_and_framework_links_flatten(self):
        app = self.root / "app"
        (app / "lib").mkdir(parents=True)
        (app / "lib/library.1.bin").write_bytes(b"library")
        self.link(app / "lib/library.bin", "library.1.bin")
        self.link(app / "framework", "lib", directory=True)
        self.normalizer()(app)
        self.assertFalse((app / "lib/library.bin").is_symlink())
        self.assertFalse((app / "framework").is_symlink())
        self.assertEqual((app / "framework/library.bin").read_bytes(), b"library")
    def test_external_link_rejection_does_not_mutate_source(self):
        app = self.root / "app"
        app.mkdir()
        outside = self.root / "secret"
        outside.write_bytes(b"do not package")
        linked = app / "external"
        self.link(linked, outside)
        with self.assertRaises((ValueError, OwnershipConflict)):
            self.normalizer()(app)
        self.assertTrue(linked.is_symlink())
        self.assertEqual(outside.read_bytes(), b"do not package")
    def test_directory_link_cycle_rejection_does_not_mutate_source(self):
        app = self.root / "app"
        (app / "a").mkdir(parents=True)
        (app / "b").mkdir()
        self.link(app / "a/to_b", "../b", directory=True)
        self.link(app / "b/to_a", "../a", directory=True)
        with self.assertRaises((ValueError, OwnershipConflict)):
            self.normalizer()(app)
        self.assertTrue((app / "a/to_b").is_symlink())


class SimulatedLinkNormalizationTest(unittest.TestCase):
    """Virtual OS-link metadata exercises the copy algorithm on hosts lacking symlink privileges."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.app = self.root / "app"
        self.app.mkdir()
    def normalize(self, links):
        from unittest.mock import patch
        original_resolve = Path.resolve
        def resolve(path, strict=False):
            return original_resolve(links.get(path, path), strict=strict)
        with patch.object(Path, "is_symlink", lambda path: path in links), patch.object(Path, "resolve", resolve):
            importlib.import_module("tools.build_installer").dereference_distribution_links(self.app)
    def test_virtual_internal_links_materialize_verified_regular_bytes(self):
        library = self.app / "library"
        library.write_bytes(b"verified library")
        linked = self.app / "library-alias"
        linked.write_bytes(b"virtual link")
        directory = self.app / "resources"
        directory.mkdir()
        (directory / "data").write_bytes(b"resource data")
        alias = self.app / "framework"
        alias.write_bytes(b"virtual directory link")
        self.normalize({linked:library, alias:directory})
        self.assertEqual(linked.read_bytes(), b"verified library")
        self.assertEqual((alias / "data").read_bytes(), b"resource data")
        self.assertFalse(linked.is_symlink())
    def test_virtual_external_link_rejects_without_mutating_source(self):
        outside = self.root / "outside"
        outside.write_bytes(b"secret")
        link = self.app / "link"
        link.write_bytes(b"virtual link")
        with self.assertRaises(ValueError):
            self.normalize({link:outside})
        self.assertEqual(link.read_bytes(), b"virtual link")
        self.assertEqual(outside.read_bytes(), b"secret")
    def test_virtual_directory_cycle_rejects_before_source_swap(self):
        a, b = self.app / "a", self.app / "b"
        a.mkdir()
        b.mkdir()
        first, second = a / "to-b", b / "to-a"
        first.write_bytes(b"first link")
        second.write_bytes(b"second link")
        with self.assertRaises(ValueError):
            self.normalize({first:b, second:a})
        self.assertEqual(first.read_bytes(), b"first link")
        self.assertEqual(second.read_bytes(), b"second link")
