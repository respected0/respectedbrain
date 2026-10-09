"""Fifth-review hardening: provenance fail-closed on every consumer path.

These tests prove that update, repair, deferred activation, copy_helper and
prepare_shell all fail-closed when the staged package is missing or carries a
corrupt attestation, and that a tampered source package can never seed a helper.
A dedicated encoding regression guards the fixed wizard text.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from respectedbrain import __version__
from respectedbrain.core.config import ConfigStore
from respectedbrain.core.errors import OwnershipConflict
from respectedbrain.core.paths import Roots
from respectedbrain.installation.deferred import defer_operation
from respectedbrain.installation.payload import validate_package
from respectedbrain.installation.provenance import TrustedProvenancePolicy, verify_release_provenance
from respectedbrain.installation.repair import repair
from respectedbrain.installation.setup import setup
from respectedbrain.installation.update import update
from respectedbrain.vault.registry import build_context
from tests.foundation_install_support import fixture_gh, seed_package
from tests.foundation_transactions_test import Backend


ATTESTATION = "distribution.json.attestation.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
DESIRED = {"global": False, "mcp": False, "schedule": False, "shortcut": False}


def break_attestation(package: Path) -> None:
    """Replace the attestation envelope with an unusable, non-empty document."""
    (package / ATTESTATION).write_text(json.dumps({"dsseEnvelope": {"signatures": []}}), encoding="utf-8")


def drop_attestation(package: Path) -> None:
    (package / ATTESTATION).unlink()


class ProvenanceFailClosedTest(unittest.TestCase):
    """A missing or corrupt attestation must stop every consumer before writes."""

    def _install(self, root: Path):
        roots = Roots(root / "app", root / "data", root / "vault")
        home = root / "home"
        home.mkdir()
        backend = Backend()
        package = seed_package(root / "package", content=b"MZ-installed")
        with fixture_gh(root), mock.patch("respectedbrain.installation.payload.validate_installed_health", return_value=None):
            result = setup(
                roots,
                roots.default_vault,
                profile={"platform": "windows-native", "user_home": str(home)},
                desired=dict(DESIRED),
                backend=backend,
                package=package,
                require_provenance=True,
            )
        self.assertTrue(result.success, result.conflicts)
        ctx = build_context(roots, ConfigStore(roots.data_root), vault=roots.default_vault, vault_id=None, env={})
        return roots, backend, ctx

    def test_update_rejects_missing_attestation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots, backend, ctx = self._install(root)
            before = (roots.app_root / "respectedbrain.exe").read_bytes()
            bad = seed_package(root / "update-package", content=b"MZ-update")
            drop_attestation(bad)
            result = update(ctx, package=bad, backend=backend)
            self.assertFalse(result.success)
            self.assertEqual((roots.app_root / "respectedbrain.exe").read_bytes(), before)

    def test_update_rejects_corrupt_attestation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots, backend, ctx = self._install(root)
            bad = seed_package(root / "update-package", content=b"MZ-update")
            break_attestation(bad)
            result = update(ctx, package=bad, backend=backend)
            self.assertFalse(result.success)

    def test_repair_rejects_missing_attestation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots, backend, ctx = self._install(root)
            drop_attestation(roots.app_root)
            result = repair(ctx, backend=backend)
            self.assertFalse(result.success)

    def test_repair_rejects_corrupt_attestation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots, backend, ctx = self._install(root)
            break_attestation(roots.app_root)
            result = repair(ctx, backend=backend)
            self.assertFalse(result.success)

    @unittest.skipUnless(sys.platform == "win32", "deferred activation is Windows-only")
    def test_deferred_update_rejects_missing_attestation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots, backend, ctx = self._install(root)
            bad = seed_package(root / "update-package", content=b"MZ-update")
            drop_attestation(bad)
            with (
                mock.patch("respectedbrain.installation.deferred.sys.frozen", True, create=True),
                mock.patch("respectedbrain.installation.deferred.sys.executable", str(roots.app_root / "respectedbrain.exe")),
                mock.patch("respectedbrain.installation.deferred.sys.platform", "win32"),
            ):
                with self.assertRaises(OwnershipConflict):
                    defer_operation(ctx, mode="update", package=bad, require_provenance=True)

    def test_prepare_shell_requires_a_package_argument(self):
        from respectedbrain.installation.windows import prepare_shell
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = Roots(root / "app", root / "data", root / "vault")
            with self.assertRaises(TypeError):
                prepare_shell(roots, request=root / "prepare.json", backend=Backend())

    def test_prepare_shell_rejects_missing_attestation_without_writes(self):
        from respectedbrain.installation.windows import prepare_shell
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = Roots(root / "app", root / "data", root / "vault")
            package = seed_package(root / "package")
            drop_attestation(package)
            request = root / "prepare.json"
            with self.assertRaises(OwnershipConflict):
                prepare_shell(roots, request=request, package=package, backend=Backend())
            self.assertFalse(request.exists())
            self.assertFalse(roots.data_root.exists())


class CopyHelperProvenanceTest(unittest.TestCase):
    """The helper must be derived only from a provenance-verified source."""

    def test_copy_helper_requires_source_attestation(self):
        from respectedbrain.installation.windows import copy_helper
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = seed_package(root / "source")
            drop_attestation(source)
            output = Path(tempfile.gettempdir()) / "respected-helper-missing-attestation"
            with self.assertRaises(OwnershipConflict):
                copy_helper(source, output)

    def test_copy_helper_rejects_tampered_source_file(self):
        from respectedbrain.installation.windows import copy_helper
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = seed_package(root / "source")
            (source / "respectedbrain.exe").write_bytes(b"MZ-tampered-after-manifest")
            output = root / "helper"
            with self.assertRaises(OwnershipConflict):
                copy_helper(source, output)
            self.assertFalse((output / "distribution.json").exists())

    def test_copy_helper_derives_helper_from_verified_source(self):
        from respectedbrain.installation.windows import copy_helper
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = seed_package(root / "source")
            output = root / "helper"
            with fixture_gh(root):
                copy_helper(source, output)
            document = validate_package(output, require_provenance=False)
            self.assertEqual(document["version"], __version__)
            self.assertTrue((output / "respectedbrain.exe").is_file())
            # The derived helper intentionally carries no attestation bundle.
            self.assertFalse((output / ATTESTATION).exists())


class InnoPrepareReceiptGatewayTest(unittest.TestCase):
    """The real CLI gate must reject a package-less prepare and leave no receipt."""

    def test_cli_prepare_without_package_argument_fails(self):
        from respectedbrain import cli
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            seed_package(root / "package")
            argv = [
                "_inno-prepare",
                "--app-root", str(root / "app"),
                "--data-root", str(root / "data"),
                "--vault", str(root / "vault"),
                "--request", str(root / "before.json"),
                "--registry-key", "HKCU\\Software\\RespectedTest",
            ]
            status = cli.main(argv)
            self.assertNotEqual(status, 0)
            self.assertFalse((root / "data/logs/inno-prepare-result.json").exists())
            self.assertFalse((root / "before.json").exists())


class ReleaseSignatureSeparationTest(unittest.TestCase):
    """Fixture provenance is a test seam; the real release path stays fail-closed."""

    def test_fixture_envelope_without_verifier_seam_fails_closed(self):
        import base64
        import hashlib
        policy = TrustedProvenancePolicy(expected_ref=f"refs/tags/v{__version__}")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            payload = {
                "_type": "https://in-toto.io/Statement/v1",
                "subject": [{"name": "distribution.json", "digest": {"sha256": hashlib.sha256(b"x").hexdigest()}}],
                "predicateType": "https://slsa.dev/provenance/v1",
                "predicate": {"buildDefinition": {"externalParameters": {"workflow": {
                    "repository": "https://github.com/respected0/respectedbrain",
                    "path": ".github/workflows/release.yml",
                    "ref": f"refs/tags/v{__version__}",
                }}}},
            }
            bundle = {
                "dsseEnvelope": {
                    "payload": base64.b64encode(json.dumps(payload).encode()).decode(),
                    "payloadType": "application/vnd.in-toto+json",
                    "signatures": [{"sig": "fixture-policy"}],
                },
            }
            artifact = root / "distribution.json"
            artifact.write_bytes(b"x")
            bundle_file = root / "distribution.json.attestation.json"
            bundle_file.write_text(json.dumps(bundle), encoding="utf-8")
            with mock.patch("shutil.which", return_value=None):
                ok, reason, _ = verify_release_provenance(artifact, bundle_file, policy=policy)
            self.assertFalse(ok)
            self.assertIn("verifier not available", reason.lower())


class WizardEncodingRegressionTest(unittest.TestCase):
    """User-facing Turkish text must stay valid UTF-8 with no mojibake."""

    MOJIBAKE = set("\u00c3\u00c4\u00c5\u00c2\u00e2\u20ac\u0161\u0178\u02c6\u2039\u203a")

    def _assert_clean(self, relative: str) -> str:
        path = REPO_ROOT / relative
        text = path.read_bytes().decode("utf-8")
        suspicious = sorted({character for character in text if character in self.MOJIBAKE})
        self.assertEqual(suspicious, [], f"{relative} contains mojibake characters")
        controls = sorted({character for character in text if 0x80 <= ord(character) <= 0x9f})
        self.assertEqual(controls, [], f"{relative} contains C1 control characters from bad decoding")
        return text

    def test_wizard_source_is_clean_utf8(self):
        text = self._assert_clean("src/respectedbrain/installation/wizard.py")
        for expected in (
            "Güncelleme için doğrulanmış yeni paket seçilmeli",
            "Programı Kaldır",
            "Kurulum & Bakım",
            "İşlem tamamlandı",
        ):
            self.assertIn(expected, text)

    def test_cli_source_is_clean_utf8(self):
        self._assert_clean("src/respectedbrain/cli.py")


class PackagingIncludesProvenanceTest(unittest.TestCase):
    """The provenance verifier must ship in the package and the frozen build."""

    def test_provenance_module_is_part_of_installation_package(self):
        import respectedbrain.installation.provenance as module
        module_path = Path(module.__file__).resolve()
        self.assertEqual(module_path.name, "provenance.py")
        self.assertEqual(module_path.parent.name, "installation")
        self.assertEqual(module_path.parent.parent.name, "respectedbrain")

    def test_frozen_build_collects_all_respectedbrain_submodules(self):
        build_source = (REPO_ROOT / "tools/build_installer.py").read_text(encoding="utf-8")
        self.assertIn('--collect-submodules', build_source)
        self.assertIn('respectedbrain', build_source)

    def test_setuptools_discovers_the_installation_package(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[tool.setuptools.packages.find]", pyproject)
        self.assertIn('where = ["src"]', pyproject)


class InnoReceiptRobustnessTest(unittest.TestCase):
    """_inno_receipt must record every failure class and never exit zero silently."""

    def _roots(self, root: Path):
        return Roots(root / "app", root / "data", root / "vault")

    def test_timeout_error_is_recorded_in_receipt(self):
        import subprocess
        from respectedbrain import cli
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = self._roots(root)

            def action():
                raise subprocess.TimeoutExpired(cmd="gh attestation verify", timeout=30)

            status = cli._inno_receipt(roots, "prepare", action)
            self.assertEqual(status, 1)
            receipt = root / "data/logs/inno-prepare-result.json"
            document = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertFalse(document["success"])
            self.assertTrue(any("Process failure" in item for item in document["errors"]))

    def test_unexpected_runtime_error_is_recorded_in_receipt(self):
        from respectedbrain import cli
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = self._roots(root)

            def action():
                raise RuntimeError("verifier crashed unexpectedly")

            status = cli._inno_receipt(roots, "prepare", action)
            self.assertEqual(status, 1)
            document = json.loads((root / "data/logs/inno-prepare-result.json").read_text(encoding="utf-8"))
            self.assertFalse(document["success"])
            self.assertTrue(any("Unexpected RuntimeError" in item for item in document["errors"]))

    def test_unwritable_receipt_still_fails_the_operation(self):
        from respectedbrain import cli
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = self._roots(root)
            with mock.patch("respectedbrain.core.config.atomic_write_json", side_effect=OSError("disk full")):
                status = cli._inno_receipt(roots, "prepare", lambda: None)
            self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()

