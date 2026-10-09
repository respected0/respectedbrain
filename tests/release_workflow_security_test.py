"""Contracts for strict release provenance and clean package lifecycle evidence."""
from __future__ import annotations

from pathlib import Path
from unittest import mock
import unittest

import tests.smoke.platform_smoke as platform_smoke


ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowSecurityTest(unittest.TestCase):
    def test_manifest_attestation_is_embedded_before_outer_assets(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        verifier_pin = workflow.index("Pin and verify GitHub CLI 2.102.0")
        checksum_download = workflow.index("gh_${GH_CLI_VERSION}_checksums.txt", verifier_pin)
        build = workflow.index("Build native distribution")
        self.assertIn("--no-installer", workflow[build:])
        no_installer = workflow.index("--no-installer", build)
        manifest_attestation = workflow.index("${{ matrix.distribution }}/distribution.json", no_installer)
        manifest_download = workflow.index("gh attestation download", manifest_attestation)
        manifest_rename = workflow.index("distribution.json.attestation.json", manifest_download)
        strict_manifest_verify = workflow.index("tools/verify_distribution.py", manifest_rename)
        strict_require = workflow.index("--require-provenance", strict_manifest_verify)
        windows_package = workflow.index("Package Windows installer", strict_require)
        macos_package = workflow.index("Package macOS disk image", strict_require)
        linux_package = workflow.index("Package Linux installer", strict_require)
        outer_attestation = workflow.index("Attest outer release assets", min(windows_package, macos_package, linux_package))
        outer_verify = workflow.index("Verify outer release assets", outer_attestation)
        self.assertLess(checksum_download, build)
        self.assertLess(no_installer, manifest_attestation)
        self.assertLess(manifest_rename, strict_require)
        self.assertLess(strict_require, windows_package)
        self.assertLess(strict_require, macos_package)
        self.assertLess(strict_require, linux_package)
        self.assertLess(outer_attestation, outer_verify)
        outer_section = workflow[outer_verify:]
        self.assertIn('--cert-identity', outer_section)
        self.assertNotIn('--signer-workflow', outer_section)

    def test_clean_environment_excludes_unsigned_and_provider_overrides(self):
        with mock.patch.dict(
            "os.environ",
            {
                "RESPECTED_ALLOW_UNSIGNED": "1",
                "RESPECTED_REQUIRE_PROVENANCE": "0",
                "BEYIN_LLM_COMMAND": "unsafe",
                "PYTHONPATH": "unsafe",
                "PYTHONUTF8": "0",
            },
            clear=True,
        ):
            clean_environment = getattr(platform_smoke, "clean_environment", None)
            self.assertIsNotNone(clean_environment, "clean_environment contract is missing")
            environment = clean_environment(Path("package"), Path("workspace"))
        for name in (
            "RESPECTED_ALLOW_UNSIGNED",
            "RESPECTED_REQUIRE_PROVENANCE",
            "BEYIN_LLM_COMMAND",
            "PYTHONPATH",
        ):
            self.assertNotIn(name, environment)
        self.assertEqual(environment["PYTHONUTF8"], "1")

    def test_platform_smoke_covers_strict_repair_and_deferred_update(self):
        source = (ROOT / "tests/smoke/platform_smoke.py").read_text(encoding="utf-8")
        self.assertIn('record("strict-frozen-repair"', source)
        self.assertIn('record("strict-deferred-package-update"', source)
        self.assertIn('"pending": true', source)


if __name__ == "__main__":
    unittest.main()
