"""Prove the distributable package works without its source checkout."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class PackageContractTest(unittest.TestCase):
    def test_resources_and_import_are_independent_of_checkout(self):
        self.assertTrue((ROOT / 'pyproject.toml').is_file(), 'An installable product package is required')
        with tempfile.TemporaryDirectory(prefix='respected-wheel-') as temporary:
            home = Path(temporary)
            wheels = home / 'wheels'
            build_env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
            build = subprocess.run([sys.executable, '-m', 'build', '--wheel', '--no-isolation', '--outdir', str(wheels)],
                                   cwd=ROOT, env=build_env, capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            wheel = next(wheels.glob('*.whl'))
            with zipfile.ZipFile(wheel) as archive:
                files = archive.namelist()
                self.assertIn('respectedbrain/resources/vault-template/🔮 850-Companion/Core.md', files)
                self.assertIn('respectedbrain/resources/vault-template/.obsidian/snippets/secondbrain-layout.css', files)
                self.assertNotIn('respectedbrain/resources/vault-template/.respectedbrain-version', files)
                self.assertFalse(any('/__pycache__/' in item or '/.state/' in item for item in files))
            isolated = home / 'isolated'
            isolated_env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
            # Source PYTHONPATH can make pip think the target already has this
            # version installed through checkout egg-info, skipping the wheel.
            for name in ('PYTHONPATH', 'PYTHONHOME'):
                isolated_env.pop(name, None)
            result = subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(isolated)],
                                    env=isolated_env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            python = isolated / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            install = subprocess.run([sys.executable, '-m', 'pip', '--python', str(python), 'install', '--no-deps', str(wheel)],
                                     env=isolated_env, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            user = home / 'user'
            user.mkdir()
            config = user / 'config.json'
            config.write_text('{"sentinel": true}', encoding='utf-8')
            env = dict(isolated_env, PYTHONDONTWRITEBYTECODE='1', RESPECTED_DATA_DIR=str(user),
                       RESPECTED_VAULT_PATH=str(home / 'never-discover'))
            probe = r'''
import json, sys
from pathlib import Path
blocked = Path(sys.argv[1]).resolve()
def audit(event, args):
    if event in ('os.mkdir', 'subprocess.Popen'):
        raise AssertionError('Import side effect: ' + event)
    if event == 'open' and isinstance(args[0], (str, bytes)) and Path(args[0]).resolve() == blocked:
        raise AssertionError('Import accessed user config')
sys.addaudithook(audit)
import respectedbrain
from respectedbrain.core.resources import ResourceCatalog
catalog = ResourceCatalog()
assert respectedbrain.__version__ == '0.0.1'
assert '🔮 850-Companion/Core.md' in catalog.iter_files('vault-template')
assert 'SKILL.md' in catalog.iter_files('skills/beyin-doktor')
assert json.loads(catalog.read_text('defaults.json'))['summary_provider'] == 'auto'
print(respectedbrain.__version__)
'''
            checked = subprocess.run([str(python), '-c', probe, str(config)], cwd=home, env=env,
                                     capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(checked.stdout.strip(), '0.0.1')
            self.assertEqual(config.read_text(encoding='utf-8'), '{"sentinel": true}')
            module = subprocess.run([str(python), '-m', 'respectedbrain', '--version'], cwd=home, env=env,
                                    capture_output=True, text=True, encoding='utf-8')
            launcher = isolated / ('Scripts/respectedbrain.exe' if os.name == 'nt' else 'bin/respectedbrain')
            entry = subprocess.run([str(launcher), '--version'], cwd=home, env=env,
                                   capture_output=True, text=True, encoding='utf-8')
            self.assertEqual((module.returncode, module.stdout), (0, '0.0.1\n'))
            self.assertEqual((entry.returncode, entry.stdout), (module.returncode, module.stdout))

    def test_resource_names_cannot_escape_package(self):
        self.assertIsNotNone(importlib.util.find_spec('respectedbrain'), 'Installable package is missing')
        from respectedbrain.core.resources import ResourceCatalog
        catalog = ResourceCatalog()
        for name in ('../config.json', '/config.json', 'C:/config.json', '..\\config.json', 'a/../../config.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                catalog.read_text(name)

    def test_materialized_template_is_temporary_and_complete(self):
        self.assertIsNotNone(importlib.util.find_spec('respectedbrain'), 'Installable package is missing')
        from respectedbrain.core.resources import ResourceCatalog
        with ResourceCatalog().materialize('vault-template') as directory:
            self.assertTrue((directory / '🔮 850-Companion/Core.md').is_file())
            self.assertTrue((directory / '.obsidian/snippets/secondbrain-layout.css').is_file())
            self.assertFalse((directory / '.respectedbrain-version').exists())
        self.assertFalse(directory.exists())


if __name__ == '__main__':
    unittest.main()
