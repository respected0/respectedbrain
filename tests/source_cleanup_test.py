"""Guard the single source tree and the native release entrypoint contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceCleanupTest(unittest.TestCase):
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
