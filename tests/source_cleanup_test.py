"""Guard the single source tree and the native release entrypoint contract."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceCleanupTest(unittest.TestCase):
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
