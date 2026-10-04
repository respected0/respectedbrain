"""Catch wrong vault fallback, identity collisions and lost config updates."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.foundation_support import snapshot, write_json


class VaultRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='respected-registry-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.data = self.root / 'Data'
        self.vault1 = self.root / 'Türkçe 🧠 Vault'
        self.vault2 = self.root / 'İkinci Vault'
        self.vault1.mkdir()
        self.vault2.mkdir()
        self.assertIsNotNone(importlib.util.find_spec('respectedbrain.vault'), 'Vault registry is missing')
        from respectedbrain.core.config import ConfigStore
        from respectedbrain.vault.registry import VaultRegistry
        self.store = ConfigStore(self.data)
        self.registry = VaultRegistry(self.store)

    def register_two(self):
        self.id1 = self.registry.register(self.vault1)
        self.id2 = self.registry.register(self.vault2)

    def test_selector_priority_and_invalid_explicit_path(self):
        from respectedbrain.core.errors import SelectionError
        self.register_two()
        env = {'RESPECTED_VAULT_PATH': str(self.vault1)}
        self.assertEqual(self.registry.select(vault=self.vault2, vault_id=None, env=env), (self.id2, self.vault2))
        self.assertEqual(self.registry.select(vault=None, vault_id=self.id2, env=env), (self.id2, self.vault2))
        self.assertEqual(self.registry.select(vault=None, vault_id=None, env=env), (self.id1, self.vault1))
        before = snapshot(self.root)
        for vault, identity, environment in [(self.root/'missing', None, env),
                                             (self.vault1, self.id1, {}),
                                             (None, None, {'RESPECTED_VAULT_PATH': str(self.root/'missing')}),
                                             (None, 'unknown', env)]:
            with self.subTest(vault=vault, identity=identity), self.assertRaises(SelectionError):
                self.registry.select(vault=vault, vault_id=identity, env=environment)
        self.assertEqual(snapshot(self.root), before)

    def test_move_and_copy_uuid(self):
        from respectedbrain.core.errors import IdentityConflict
        self.register_two()
        moved = self.root / 'Moved Vault'
        shutil.move(self.vault1, moved)
        self.assertEqual(self.registry.register(moved), self.id1)
        self.assertEqual(self.registry.select(vault=None, vault_id=self.id1, env={})[1], moved)
        copied = self.root / 'Copied Vault'
        shutil.copytree(moved, copied)
        before = snapshot(copied)
        with self.assertRaises(IdentityConflict):
            self.registry.register(copied)
        self.assertEqual(snapshot(copied), before)
        new_id = self.registry.register(copied, new_identity=True)
        self.assertNotEqual(new_id, self.id1)
        self.assertEqual(json.loads((moved/'.respected.json').read_text())['vault_id'], self.id1)

    def test_concurrent_config_edits_survive(self):
        self.register_two()
        self.store.update(lambda cfg: cfg.update({'custom': 7}))
        gate = self.root / 'gate'
        code = r'''
import sys, time
from pathlib import Path
from respectedbrain.core.config import ConfigStore
while not Path(sys.argv[2]).exists(): time.sleep(.01)
ConfigStore(Path(sys.argv[1])).update(lambda cfg: cfg['preferences'].update({sys.argv[3]: sys.argv[4]}))
'''
        env = dict(os.environ, PYTHONUTF8='1')
        processes = [subprocess.Popen([sys.executable, '-c', code, str(self.data), str(gate), key, value],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                     for key, value in [('theme','dark'), ('summary_provider','codex')]]
        gate.touch()
        for process in processes:
            out, err = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, (out, err))
        config = self.store.read()
        self.assertEqual(config['preferences']['theme'], 'dark')
        self.assertEqual(config['preferences']['summary_provider'], 'codex')
        self.assertEqual(config['custom'], 7)

    def test_marker_migration_preserves_unknowns_and_archives_machine_paths(self):
        original = {'runtime_path': 'C:/old/product', 'companion': 'Ada', 'custom': 7}
        write_json(self.vault1 / '.respected.json', original)
        identity = self.registry.register(self.vault1)
        marker = json.loads((self.vault1 / '.respected.json').read_text(encoding='utf-8'))
        self.assertEqual(marker['schema_version'], 3)
        self.assertEqual(marker['vault_id'], identity)
        self.assertEqual(marker['companion'], 'Ada')
        self.assertEqual(marker['custom'], 7)
        self.assertNotIn('runtime_path', marker)
        self.assertNotIn('C:/old/product', json.dumps(marker))
        backups = list((self.data/'backups').rglob('marker.json'))
        self.assertTrue(any(json.loads(file.read_text(encoding='utf-8')) == original for file in backups))
        self.assertEqual(self.store.read()['vaults'][identity]['legacy_metadata']['runtime_path'], 'C:/old/product')

    def test_read_and_discover_are_readonly_and_wrong_cwd_is_irrelevant(self):
        before = snapshot(self.root)
        self.assertEqual(self.store.read()['schema_version'], 3)
        self.assertIsNone(self.registry.discover(self.vault1))
        self.assertEqual(snapshot(self.root), before)
        self.register_two()
        nested = self.vault1/'nested'
        nested.mkdir()
        before = snapshot(self.root)
        self.assertEqual(self.registry.discover(nested), self.vault1)
        previous_cwd = Path.cwd()
        try:
            os.chdir(self.vault2)
            self.assertEqual(self.registry.select(vault=None,vault_id=None,env={}), (self.id1,self.vault1))
        finally:
            os.chdir(previous_cwd)
        self.assertEqual(snapshot(self.root), before)

    def test_explicit_path_with_unregistered_or_mismatched_marker_is_rejected(self):
        from respectedbrain.core.errors import SelectionError
        self.register_two()
        write_json(self.vault2/'.respected.json', {'schema_version':3,'vault_id':self.id1})
        with self.assertRaises(SelectionError):
            self.registry.select(vault=self.vault2,vault_id=None,env={})
        unregistered = self.root/'Unregistered'
        unregistered.mkdir()
        write_json(unregistered/'.respected.json', {'schema_version':3,'vault_id':'33333333-3333-4333-8333-333333333333'})
        with self.assertRaises(SelectionError):
            self.registry.select(vault=unregistered,vault_id=None,env={})

    def test_context_binds_selected_uuid_without_creating_state(self):
        from respectedbrain.core.paths import Roots
        from respectedbrain.vault.registry import build_context
        self.register_two()
        before = snapshot(self.root)
        ctx = build_context(Roots(self.root/'App', self.data, self.root/'Default'), self.store,
                            vault=None, vault_id=self.id2, env={})
        self.assertEqual(ctx.paths.vault_id, self.id2)
        self.assertEqual(ctx.paths.vault_root, self.vault2)
        self.assertFalse(ctx.paths.state_dir.exists())
        self.assertEqual(snapshot(self.root), before)

    def test_failed_config_commit_restores_marker(self):
        original = {'companion':'Ada','custom':7}
        marker = self.vault1/'.respected.json'
        write_json(marker, original)
        before = marker.read_bytes()
        replace = os.replace
        def fail_config(source, destination):
            if Path(destination) == self.store.path:
                raise PermissionError('Forced config activation failure')
            return replace(source, destination)
        with mock.patch('os.replace', side_effect=fail_config), self.assertRaises(PermissionError):
            self.registry.register(self.vault1)
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse(self.store.path.exists())


if __name__ == '__main__':
    unittest.main()
