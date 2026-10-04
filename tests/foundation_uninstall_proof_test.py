"""Locked Inno log is accepted only with an unchanged prelaunch attestation."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from respectedbrain.core.errors import OwnershipConflict
from respectedbrain.installation.ownership import OwnedFile, digest, read_manifest, manifest_document
from tests import foundation_operations_test as operation_fixture


class FoundationUninstallProofTest(unittest.TestCase):
    setUp = operation_fixture.FoundationOperationsTest.setUp
    def seed_shell(self):
        folder = self.roots.app_root / "uninstall"
        folder.mkdir()
        for name in ("unins000.exe", "unins000.dat"):
            (folder / name).write_bytes(b"owned-shell-" + name.encode())
        path = self.roots.data_root / "install-manifest.json"
        previous = read_manifest(path)
        records = tuple(OwnedFile(item, digest(item), "uninstaller") for item in folder.iterdir())
        path.write_text(json.dumps(manifest_document(replace(previous, files=previous.files + records))), encoding="utf-8")
        return folder

    def test_locked_dat_requires_unchanged_prelaunch_proof(self):
        from respectedbrain.installation.windows import prepare_uninstall, validate_uninstall_proof
        self.seed_shell()
        request = self.root / "proof.json"
        proof_hash = prepare_uninstall(self.ctx, request=request)
        self.assertTrue(validate_uninstall_proof(self.roots, request=request, expected_hash=proof_hash))
        original = Path.read_bytes
        def locked(path):
            if path.name == "unins000.dat":
                raise PermissionError("Inno exclusive lock")
            return original(path)
        with patch.object(Path, "read_bytes", locked):
            self.assertTrue(validate_uninstall_proof(self.roots, request=request, expected_hash=proof_hash))

    def test_changed_dat_or_manifest_cannot_use_old_attestation(self):
        from respectedbrain.installation.windows import prepare_uninstall, validate_uninstall_proof
        shell = self.seed_shell()
        request = self.root / "proof.json"
        proof_hash = prepare_uninstall(self.ctx, request=request)
        (shell / "unins000.dat").write_bytes(b"user-changed")
        with self.assertRaises(OwnershipConflict):
            validate_uninstall_proof(self.roots, request=request, expected_hash=proof_hash)
        with self.assertRaises(OwnershipConflict):
            validate_uninstall_proof(self.roots, request=request, expected_hash="0" * 64)
