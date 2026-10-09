"""Native artifacts must exist and run without checkout/Python on PATH."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FoundationDistributionTest(unittest.TestCase):
    def test_frozen_runs_without_checkout_or_python(self):
        from respectedbrain.installation.payload import validate_package
        platform = "windows" if os.name == "nt" else "macos" if __import__("sys").platform == "darwin" else "linux"
        distribution = ROOT / "dist" / ("RespectedBrain.app" if platform == "macos" else "RespectedBrain")
        document = validate_package(distribution, require_provenance=False)
        with tempfile.TemporaryDirectory(prefix="Türkçe 🧠 ") as temporary:
            env = {**os.environ, "PATH": str(Path(os.environ["SystemRoot"]) / "System32") if os.name == "nt" else "/usr/bin:/bin", "RESPECTED_APP_DIR": str(distribution), "RESPECTED_DATA_DIR": str(Path(temporary) / "data"), "PYTHONPATH": ""}
            result = subprocess.run([str(distribution / document["launcher"]), "--version"], cwd=temporary, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual((result.returncode, result.stdout.strip()), (0, document["version"]), result.stderr)
            self.assertFalse((Path(temporary) / "data").exists())
        self.assertFalse((distribution / "runtime").exists())
        resources = [name for name in document["files"] if name.endswith("respectedbrain/resources/defaults.json")]
        self.assertEqual(len(resources), 1)

    def test_inno_does_not_reuse_old_vault_as_app_dir(self):
        source = (ROOT / "packaging/windows/respected_setup.iss").read_text(encoding="utf-8")
        self.assertIn("UsePreviousAppDir=no", source)
        self.assertIn("DefaultDirName={localappdata}\\Programs\\RespectedBrain", source)
        self.assertIn("UninstallFilesDir={app}\\uninstall", source)
        self.assertIn('DestDir: "{tmp}\\payload"', source)
        self.assertNotIn('DestDir: "{app}', source)
        self.assertNotIn("[UninstallDelete]", source)
        self.assertNotIn("DelTree", source)

    def test_distribution_tampering_fails_before_launcher(self):
        from respectedbrain.installation.payload import validate_package
        from respectedbrain.core.errors import OwnershipConflict
        from tests.foundation_install_support import seed_package
        with tempfile.TemporaryDirectory() as temporary:
            package = seed_package(Path(temporary))
            (package / "respectedbrain.exe").write_bytes(b"changed")
            with self.assertRaises(OwnershipConflict):
                validate_package(package, require_provenance=False)
