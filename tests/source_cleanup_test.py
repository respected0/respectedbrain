"""Guard the single source tree and the native release entrypoint contract."""
from pathlib import Path
import os
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class SourceCleanupTest(unittest.TestCase):
    def test_macos_smoke_uses_app_bundle_for_source_and_install_destination(self):
        spec = importlib.util.spec_from_file_location('platform_smoke', ROOT / 'tests/smoke/platform_smoke.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        root = Path('/isolated-smoke')
        with mock.patch.object(tool.sys, 'platform', 'darwin'):
            self.assertEqual(tool.distribution_name(), 'RespectedBrain.app')
            self.assertEqual(tool.workspace_paths(root)[1], root / 'RespectedBrain.app')
        with mock.patch.object(tool.sys, 'platform', 'linux'):
            self.assertEqual(tool.distribution_name(), 'RespectedBrain')
            self.assertEqual(tool.workspace_paths(root)[1], root / 'app')

    def test_native_verification_stage_labels_handle_single_argument_version(self):
        from tests.foundation_install_support import seed_package
        spec = importlib.util.spec_from_file_location('native_verifier', ROOT / 'tools/verify_distribution.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as temporary:
            package = seed_package(Path(temporary) / 'package')
            def reply(argv, **kwargs):
                command = argv[1:]
                output = '0.0.1\n' if command == ['--version'] else 'identity\n' if command[:2] == ['vault', 'register'] else '{"identity": {}}' if command == ['vault', 'list'] else '{"id": 1}' if command[0] == 'mcp' else ''
                return subprocess.CompletedProcess(argv, 0, output, '')
            with mock.patch.object(tool.subprocess, 'run', side_effect=reply):
                self.assertEqual(tool.verify(package, platform='windows'), 0)

    def test_frozen_verification_failure_publishes_diagnostic_annotation(self):
        from tests.foundation_install_support import seed_package
        with tempfile.TemporaryDirectory() as temporary:
            package = seed_package(Path(temporary) / 'package')
            result = subprocess.run([sys.executable, str(ROOT / 'tools/verify_distribution.py'),
                                     '--platform', 'macos', '--distribution', str(package)],
                                    env={**os.environ, 'GITHUB_ACTIONS': 'true'},
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('::error title=Native distribution verification::stage=manifest; code=platform-mismatch',
                          result.stdout)
            self.assertNotIn(str(package), result.stdout)

    def test_retired_source_entrypoints_are_absent(self):
        for name in ("runtime", "installer", "template", "setup.py", "setup", "setup.command"):
            with self.subTest(name=name):
                self.assertFalse((ROOT / name).exists(), f"Retired source remains: {name}")

    def test_release_builds_and_verifies_native_distributions(self):
        text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("python tools/build_installer.py", text)
        self.assertIn("python tools/verify_distribution.py", text)
        self.assertNotIn("cp -r template", text)
        self.assertNotIn("installer\\respected_setup.iss", text)
        self.assertNotIn("Move-Item setup.exe", text)


if __name__ == "__main__":
    unittest.main()
