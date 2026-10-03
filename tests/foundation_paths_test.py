"""Verify platform roots without touching live config or discovering a vault."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest

from tests.foundation_support import snapshot

UUID = '11111111-1111-4111-8111-111111111111'


class FoundationPathsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / 'Home'
        self.home.mkdir()
        self.local = self.root / 'Redirected Local'
        self.docs = self.root / 'Türkçe 🧠 Belgeler'

    def paths_module(self):
        self.assertIsNotNone(importlib.util.find_spec('respectedbrain.core.paths'), 'Pure paths contract is missing')
        from respectedbrain.core import paths
        return paths

    def test_redirected_documents_and_separate_roots(self):
        paths = self.paths_module()
        before = snapshot(self.root)
        roots = paths.resolve_roots(platform='win32', home=self.home, env={},
            known_folder={'LocalAppData': self.local, 'Documents': self.docs}.__getitem__)
        self.assertEqual(roots.app_root, self.local / 'Programs/RespectedBrain')
        self.assertEqual(roots.data_root, self.local / 'RespectedBrain')
        self.assertEqual(roots.default_vault, self.docs / 'RespectedOS')
        bound = paths.AppPaths(roots.app_root, roots.data_root, roots.default_vault, UUID)
        self.assertEqual(bound.state_dir, roots.data_root / 'vaults' / UUID / 'state')
        self.assertEqual(bound.cache_dir, roots.data_root / 'vaults' / UUID / 'cache')
        self.assertEqual(bound.log_dir, roots.data_root / 'logs')
        self.assertEqual(bound.backup_dir, roots.data_root / 'backups')
        self.assertEqual(snapshot(self.root), before)

    def test_other_platform_roots(self):
        paths = self.paths_module()
        xdg = self.root / 'Custom Data'
        linux = paths.resolve_roots(platform='linux', home=self.home, env={'XDG_DATA_HOME': str(xdg)}, known_folder=lambda _: None)
        self.assertEqual(linux.app_root, self.home / '.local/lib/respectedbrain')
        self.assertEqual(linux.data_root, xdg / 'respectedbrain')
        self.assertEqual(linux.default_vault, self.home / 'RespectedOS')
        mac = paths.resolve_roots(platform='darwin', home=self.home, env={}, known_folder=lambda _: None)
        self.assertEqual(mac.app_root, self.home / 'Applications/RespectedBrain.app')
        self.assertEqual(mac.data_root, self.home / 'Library/Application Support/RespectedBrain')
        (self.home / 'Documents').mkdir()
        fallback = paths.resolve_roots(platform='linux', home=self.home, env={}, known_folder=lambda _: None)
        self.assertEqual(fallback.default_vault, self.home / 'Documents/RespectedOS')
        self.assertEqual(fallback.data_root, self.home / '.local/share/respectedbrain')

    def test_overrides_do_not_use_legacy_runtime_dir(self):
        paths = self.paths_module()
        roots = paths.resolve_roots(platform='win32', home=self.home,
            env={'RESPECTED_APP_DIR': str(self.root / 'App'), 'RESPECTED_DATA_DIR': str(self.root / 'Data'),
                 'RESPECTED_RUNTIME_DIR': str(self.root / 'Wrong Legacy')},
            known_folder={'LocalAppData': self.local, 'Documents': self.docs}.__getitem__)
        self.assertEqual(roots.app_root, self.root / 'App')
        self.assertEqual(roots.data_root, self.root / 'Data')
        self.assertFalse(roots.data_root.exists())

    def test_overlapping_paths_and_bad_identity_are_rejected(self):
        paths = self.paths_module()
        from respectedbrain.core.errors import SelectionError
        for app, data, vault, identity in [(self.root/'Same', self.root/'Same', self.docs, UUID),
                                          (self.root/'App', self.root/'App/Data', self.docs, UUID),
                                          (self.root/'App', self.root/'Data', self.docs, '../escape')]:
            with self.subTest(identity=identity), self.assertRaises(SelectionError):
                paths.AppPaths(app, data, vault, identity)
        with self.assertRaises(SelectionError):
            paths.resolve_roots(platform='linux', home=self.home, env={'RESPECTED_DATA_DIR': 'relative'}, known_folder=lambda _: None)


if __name__ == '__main__':
    unittest.main()
