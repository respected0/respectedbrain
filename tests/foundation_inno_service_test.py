"""Inno stages bytes; the common service owns registration and rollback."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from respectedbrain.core.paths import Roots
from respectedbrain.installation.ownership import read_manifest
from tests.foundation_install_support import fixture_gh, seed_package
from tests.foundation_transactions_test import Backend
from respectedbrain import cli


class FoundationInnoServiceTest(unittest.TestCase):
    def test_shell_preparation_checks_release_provenance_before_writes(self):
        from respectedbrain.core.errors import OwnershipConflict
        from respectedbrain.installation.windows import prepare_shell
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = Roots(root / "app", root / "data", root / "vault")
            package = seed_package(root / "package")
            (package / "distribution.json.attestation.json").unlink()
            request = root / "prepare.json"

            with self.assertRaisesRegex(OwnershipConflict, "Missing build provenance attestation"):
                prepare_shell(
                    roots,
                    request=request,
                    registry_key="HKCU\\Software\\RespectedTest",
                    package=package,
                    backend=Backend(),
                )

            self.assertFalse(request.exists())
            self.assertFalse(roots.data_root.exists())

    def test_shell_preparation_refuses_unowned_files_and_registry_without_writes(self):
        from respectedbrain.installation.windows import prepare_shell
        from respectedbrain.core.errors import OwnershipConflict
        for artifact in ("uninstaller", "registry"):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                roots = Roots(root / "app", root / "data", root / "vault")
                backend = Backend()
                key = "HKCU\\Software\\RespectedTest"
                if artifact == "uninstaller":
                    path = roots.app_root / "uninstall/unins000.exe"
                    path.parent.mkdir(parents=True)
                    path.write_bytes(b"user-executable")
                else:
                    backend.records[("registry", key)] = b"unrelated-user-registration"
                package = seed_package(root / "package")
                request = root / "prepare.json"
                with fixture_gh(root), self.assertRaises(OwnershipConflict):
                    prepare_shell(roots, request=request, package=package, registry_key=key, backend=backend)
                self.assertFalse(request.exists())

    def test_registration_and_uninstaller_are_owned_by_shared_setup(self):
        from respectedbrain.installation.windows import prepare_shell, deploy_shell
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = Roots(root / "app", root / "data", root / "vault")
            package = seed_package(root / "package")
            backend = Backend()
            request = root / "prepare.json"
            key = "HKCU\\Software\\RespectedTest"
            with fixture_gh(root):
                prepare_shell(roots, request=request, package=package, registry_key=key, backend=backend)
            uninstall = roots.app_root / "uninstall"
            uninstall.mkdir(parents=True)
            (uninstall / "unins000.exe").write_bytes(b"MZ-Inno")
            (uninstall / "unins000.dat").write_bytes(b"Inno-log")
            with fixture_gh(root), patch("respectedbrain.installation.payload.validate_installed_health"):
                result = deploy_shell(roots, package=package, request=request, backend=backend)
            self.assertTrue(result.success, result.conflicts)
            manifest = read_manifest(roots.data_root / "install-manifest.json")
            self.assertEqual(len([item for item in manifest.files if item.role == "uninstaller"]), 2)
            owned = next(item for item in manifest.external if item.kind == "registry")
            self.assertEqual(owned.before, None)
            self.assertEqual(json.loads(owned.after)["values"]["InstallLocation"]["data"], str(roots.app_root))
            from respectedbrain.installation.windows import seal_shell
            from respectedbrain.installation.ownership import prove_ownership
            log = uninstall / "unins000.dat"
            log.write_bytes(b"Inno Setup Uninstall Log (b)\x00final")
            self.assertFalse(prove_ownership(log, manifest))
            seal_shell(roots, backend=backend)
            self.assertTrue(prove_ownership(log, read_manifest(roots.data_root / "install-manifest.json")))

    def test_failed_health_restores_pre_shell_uninstaller_bytes_and_registry(self):
        from respectedbrain.installation.windows import prepare_shell, deploy_shell
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            roots = Roots(root / "app", root / "data", root / "vault")
            package = seed_package(root / "package")
            backend = Backend()
            key = "HKCU\\Software\\RespectedTest"
            backend.records[("registry", key)] = b"old-registry"
            path = roots.app_root / "uninstall/unins000.dat"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"old-log")
            # These are prior owned shell artifacts, rather than arbitrary files.
            from respectedbrain.installation.ownership import OwnedFile, OwnershipManifest, digest, manifest_document
            from respectedbrain.integrations.backend import ExternalChange
            roots.data_root.mkdir()
            previous = OwnershipManifest(3, (OwnedFile(path, digest(path), "uninstaller"),), (ExternalChange("registry", key, None, b"old-registry"),))
            (roots.data_root / "install-manifest.json").write_text(json.dumps(manifest_document(previous)), encoding="utf-8")
            request = root / "prepare.json"
            with fixture_gh(root):
                prepare_shell(roots, request=request, package=package, registry_key=key, backend=backend)
            path.write_bytes(b"new-log")
            (path.parent / "unins000.exe").write_bytes(b"MZ-Inno")
            with fixture_gh(root), patch("respectedbrain.installation.payload.validate_installed_health", side_effect=OSError("bad-health")):
                result = deploy_shell(roots, package=package, request=request, backend=backend)
            self.assertFalse(result.success)
            self.assertEqual(path.read_bytes(), b"old-log")
            self.assertEqual(backend.read("registry", key), b"old-registry")
            self.assertFalse((roots.app_root / "respectedbrain.exe").exists())

class InnoPrepareReceiptTest(unittest.TestCase):
    """The real _inno-prepare gate must fail closed and leave a receipt."""

    def _prepare_command(self, root):
        return [
            "_inno-prepare",
            "--app-root", str(root / "app"),
            "--data-root", str(root / "data"),
            "--vault", str(root / "vault"),
            "--request", str(root / "before.json"),
            "--registry-key", "HKCU\\Software\\RespectedTest",
            "--package", str(root / "package"),
        ]

    def test_cli_prepare_fails_closed_without_attestation_and_writes_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            package = seed_package(root / "package")
            (package / "distribution.json.attestation.json").unlink()
            status = cli.main(self._prepare_command(root))
            self.assertEqual(status, 1)
            self.assertFalse((root / "before.json").exists())
            self.assertFalse((root / "app").exists())
            self.assertFalse((root / "vault").exists())
            receipt = root / "data/logs/inno-prepare-result.json"
            self.assertTrue(receipt.is_file())
            document = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertFalse(document["success"])
            self.assertIn("Missing build provenance attestation", " ".join(document["errors"]))

    def test_cli_prepare_requires_package_argument(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            argv = self._prepare_command(root)
            argv = argv[: argv.index("--package")]
            # main() converts argparse SystemExit into the numeric exit code.
            status = cli.main(argv)
            self.assertNotEqual(status, 0)
            self.assertFalse((root / "data/logs/inno-prepare-result.json").exists())

    def test_cli_prepare_passes_with_fixture_provenance_and_writes_success_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            seed_package(root / "package")
            with fixture_gh(root):
                status = cli.main(self._prepare_command(root))
            self.assertEqual(status, 0)
            self.assertTrue((root / "before.json").is_file())
            receipt = root / "data/logs/inno-prepare-result.json"
            self.assertTrue(receipt.is_file())
            document = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertTrue(document["success"])
