"""Bound journal synchronization cost without weakening durable recovery."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from respectedbrain.installation import transaction
from tests.foundation_transactions_test import Backend


class TransactionThroughputTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / 'data'
        self.target = self.root / 'app' / 'file'
        self.target.parent.mkdir()

    def test_write_uses_one_durable_snapshot_per_file_with_existing_parent(self):
        with transaction.Transaction(self.data, Backend()) as tx:
            with mock.patch.object(tx, '_save', wraps=tx._save) as save:
                for number in range(20):
                    tx.write(self.target.with_name(str(number)), b'payload')
                self.assertLessEqual(save.call_count, 20)
            tx.commit()

    def test_before_image_and_expected_output_are_durable_before_mutation(self):
        self.target.write_bytes(b'old')
        with transaction.Transaction(self.data, Backend()) as tx:
            original = transaction._atomic_write_mode
            def check(target, payload, mode):
                persisted = json.loads(tx.journal.read_text(encoding='utf-8'))
                row = next(row for row in persisted['files'] if row['path'] == str(target))
                self.assertEqual((tx.directory / row['backup']).read_bytes(), b'old')
                self.assertEqual(row['after'], hashlib.sha256(payload).hexdigest())
                self.assertEqual(row['before'], hashlib.sha256(b'old').hexdigest())
                self.assertEqual(target.read_bytes(), b'old')
                return original(target, payload, mode)
            with mock.patch.object(transaction, '_atomic_write_mode', side_effect=check):
                tx.write(self.target, b'new')
            # rollback is intentionally exercised by leaving without commit
        self.assertEqual(self.target.read_bytes(), b'old')

    def test_nested_directory_creation_uses_one_durable_directory_plan(self):
        target = self.root / 'nested/a/b/c/d/file'
        with transaction.Transaction(self.data, Backend()) as tx:
            with mock.patch.object(tx, '_save', wraps=tx._save) as save:
                tx.write(target, b'new')
                self.assertLessEqual(save.call_count, 2)
            journal = json.loads(tx.journal.read_text(encoding='utf-8'))
            self.assertEqual(set(journal['directories']), {str(p) for p in target.parents if p != self.root and p.is_relative_to(self.root)})
        self.assertFalse((self.root / 'nested').exists())

    def test_public_backup_stays_durable_without_following_write(self):
        self.target.write_bytes(b'original')
        with transaction.Transaction(self.data, Backend()) as tx:
            tx.backup(self.target)
            row = json.loads(tx.journal.read_text(encoding='utf-8'))['files'][0]
            self.assertEqual((tx.directory / row['backup']).read_bytes(), b'original')
            tx.commit()
