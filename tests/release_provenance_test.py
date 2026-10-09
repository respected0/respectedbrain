"""Tests for release provenance verification, SLSA attestations, and fail-closed release gates."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from respectedbrain.installation.provenance import (
    _load_bundle_entries,
    ProvenanceVerificationError,
    TrustedProvenancePolicy,
    verify_release_provenance,
)
from respectedbrain.installation.payload import validate_package


def _synthetic_slsa_bundle(
    *,
    subject_name: str,
    subject_sha256: str,
    repo: str = "https://github.com/respected0/respectedbrain",
    workflow: str = ".github/workflows/release.yml",
    ref: str = "refs/tags/v0.0.1",
    signature_str: str = "test_trusted_crypto_signature",
) -> dict:
    payload = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": "distribution.json", "digest": {"sha256": subject_sha256}},
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://actions.github.com/buildtypes/runner/v1",
                "externalParameters": {
                    "workflow": {"ref": ref, "path": workflow, "repository": repo},
                },
            },
            "runDetails": {
                "builder": {"id": "https://github.com/actions/runner"},
                "metadata": {
                    "invocationId": "https://github.com/respected0/respectedbrain/actions/runs/123456",
                },
            },
        },
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    return {
        "mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.2",
        "dsseEnvelope": {
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
            "payloadType": "application/vnd.in-toto+json",
            "signatures": [
                {
                    "sig": signature_str,
                    "keyid": "sigstore-oidc-key",
                }
            ],
        },
    }


class ReleaseProvenanceVerificationTest(unittest.TestCase):
    def setUp(self):
        # Seam test fixture: validates policy contract wiring and envelope parsing without relying on external host binary
        def offline_verifier(pkg_path, bundle_path, policy):
            raw = json.loads(bundle_path.read_text(encoding="utf-8"))
            sigs = raw.get("dsseEnvelope", {}).get("signatures", [])
            for s in sigs:
                if s.get("sig") == "test_trusted_crypto_signature":
                    return True, "signature valid"
            return False, "invalid cryptographic signature"

        self.offline_verifier = offline_verifier
        self.policy = TrustedProvenancePolicy(
            expected_repo="respected0/respectedbrain",
            expected_workflow=".github/workflows/release.yml",
            expected_ref_prefix="refs/tags/v",
            verifier_callable=self.offline_verifier,
        )

    def test_multiline_jsonl_bundle_entries_are_parsed(self):
        first = _synthetic_slsa_bundle(subject_name="first", subject_sha256="11")
        second = _synthetic_slsa_bundle(subject_name="second", subject_sha256="22")
        entries = _load_bundle_entries(json.dumps(first) + "\n" + json.dumps(second))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], first)
        self.assertEqual(entries[1], second)

    def test_pinned_gh_cli_help_declares_required_verifier_contract(self):
        executable = shutil.which("gh")
        if executable is None:
            self.skipTest("pinned gh verifier is not installed")
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
        self.assertIn("gh version 2.102.0", version.stdout)
        verify_help = subprocess.run([executable, "attestation", "verify", "--help"], capture_output=True, text=True, timeout=10).stdout
        for flag in (
            "--bundle",
            "--cert-identity",
            "--cert-oidc-issuer",
            "--deny-self-hosted-runners",
            "--predicate-type",
            "--signer-workflow",
            "--source-ref",
        ):
            self.assertIn(flag, verify_help)
        download_help = subprocess.run([executable, "attestation", "download", "--help"], capture_output=True, text=True, timeout=10).stdout
        self.assertIn("--limit", download_help)
        self.assertIn("--predicate-type", download_help)

    def test_trusted_fixture_passes_verification(self):
        """Policy contract test: a valid artifact with matching envelope policy passes via test verifier seam."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "RespectedBrain-Windows-Setup.exe"
            pkg.write_bytes(b"MZ_SAMPLE_BINARY_CONTENT_2026")
            pkg_hash = hashlib.sha256(pkg.read_bytes()).hexdigest()

            bundle_data = _synthetic_slsa_bundle(
                subject_name=pkg.name,
                subject_sha256=pkg_hash,
                repo="https://github.com/respected0/respectedbrain",
                workflow=".github/workflows/release.yml",
                ref="refs/tags/v0.0.1",
                signature_str="test_trusted_crypto_signature",
            )
            bundle_file = root / "RespectedBrain-Windows-Setup.exe.attestation.json"
            bundle_file.write_text(json.dumps(bundle_data), encoding="utf-8")

            ok, reason, details = verify_release_provenance(pkg, bundle_file, policy=self.policy)
            self.assertTrue(ok, f"Verification should pass: {reason}")
            self.assertEqual(details.get("repo"), "respected0/respectedbrain")
            self.assertEqual(details.get("ref"), "refs/tags/v0.0.1")

    def test_unsigned_statement_is_rejected(self):
        """Bare unsigned in-toto statements without DSSE envelope must be rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "artifact.bin"
            pkg.write_bytes(b"some-bytes")
            pkg_hash = hashlib.sha256(pkg.read_bytes()).hexdigest()

            statement = {
                "_type": "https://in-toto.io/Statement/v1",
                "subject": [{"name": pkg.name, "digest": {"sha256": pkg_hash}}],
                "predicateType": "https://slsa.dev/provenance/v1",
                "predicate": {"buildDefinition": {"externalParameters": {"workflow": {
                    "repository": "https://github.com/respected0/respectedbrain",
                    "path": ".github/workflows/release.yml",
                    "ref": "refs/tags/v0.0.1",
                }}}},
            }
            bundle = root / "untrusted.json"
            bundle.write_text(json.dumps(statement), encoding="utf-8")

            ok, reason, _ = verify_release_provenance(pkg, bundle, policy=self.policy)
            self.assertFalse(ok)
            self.assertIn("unsigned", reason.lower())

    def test_fake_signature_is_rejected(self):
        """Envelope with made-up signature or untrusted material must fail verification."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "artifact.bin"
            pkg.write_bytes(b"some-bytes")
            pkg_hash = hashlib.sha256(pkg.read_bytes()).hexdigest()

            bundle_data = _synthetic_slsa_bundle(
                subject_name=pkg.name,
                subject_sha256=pkg_hash,
                signature_str="made-up-not-a-signature",
            )
            bundle = root / "attestation.json"
            bundle.write_text(json.dumps(bundle_data), encoding="utf-8")

            ok, reason, _ = verify_release_provenance(pkg, bundle, policy=self.policy)
            self.assertFalse(ok)
            self.assertIn("signature", reason.lower())

    def test_foreign_origin_or_domain_is_rejected(self):
        """Provenance from an attacker domain (e.g. attacker.example/.../respected0/respectedbrain) is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "artifact.bin"
            pkg.write_bytes(b"some-bytes")
            pkg_hash = hashlib.sha256(pkg.read_bytes()).hexdigest()

            bundle_data = _synthetic_slsa_bundle(
                subject_name=pkg.name,
                subject_sha256=pkg_hash,
                repo="https://attacker.example/unrelated/respected0/respectedbrain",
            )
            bundle = root / "attestation.json"
            bundle.write_text(json.dumps(bundle_data), encoding="utf-8")

            ok, reason, _ = verify_release_provenance(pkg, bundle, policy=self.policy)
            self.assertFalse(ok)
            self.assertIn("repository mismatch", reason.lower())

    def test_missing_host_verifier_fails_closed(self):
        """When no cryptographic verifier is available on the host, verification must fail-closed."""
        default_policy = TrustedProvenancePolicy(
            expected_repo="respected0/respectedbrain",
            expected_workflow=".github/workflows/release.yml",
            verifier_callable=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "artifact.bin"
            pkg.write_bytes(b"some-bytes")
            pkg_hash = hashlib.sha256(pkg.read_bytes()).hexdigest()

            bundle_data = _synthetic_slsa_bundle(
                subject_name=pkg.name,
                subject_sha256=pkg_hash,
            )
            bundle = root / "attestation.json"
            bundle.write_text(json.dumps(bundle_data), encoding="utf-8")

            with mock.patch("shutil.which", return_value=None):
                ok, reason, _ = verify_release_provenance(pkg, bundle, policy=default_policy)
                self.assertFalse(ok)
                self.assertIn("verifier not available", reason.lower())

    def test_tampered_package_fails_verification(self):
        """If package content is modified after provenance generation, verification must fail-closed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "RespectedBrain-Windows-Setup.exe"
            pkg.write_bytes(b"MZ_ORIGINAL")
            original_hash = hashlib.sha256(pkg.read_bytes()).hexdigest()

            bundle_data = _synthetic_slsa_bundle(
                subject_name=pkg.name,
                subject_sha256=original_hash,
            )
            bundle_file = root / "RespectedBrain-Windows-Setup.exe.attestation.json"
            bundle_file.write_text(json.dumps(bundle_data), encoding="utf-8")

            # Tamper with the package
            pkg.write_bytes(b"MZ_TAMPERED_PAYLOAD")

            ok, reason, _ = verify_release_provenance(pkg, bundle_file, policy=self.policy)
            self.assertFalse(ok)
            self.assertIn("hash mismatch", reason.lower())

    def test_untrusted_git_ref_is_rejected(self):
        """Provenance built from an untrusted branch instead of official release tag must be rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "RespectedBrain-Setup.exe"
            pkg.write_bytes(b"PACKAGE")
            pkg_hash = hashlib.sha256(pkg.read_bytes()).hexdigest()

            bundle_data = _synthetic_slsa_bundle(
                subject_name=pkg.name,
                subject_sha256=pkg_hash,
                ref="refs/heads/feature-unreviewed",
            )
            bundle_file = root / "attestation.json"
            bundle_file.write_text(json.dumps(bundle_data), encoding="utf-8")

            ok, reason, _ = verify_release_provenance(pkg, bundle_file, policy=self.policy)
            self.assertFalse(ok)
            self.assertIn("ref mismatch", reason.lower())

    def test_missing_provenance_fails_closed(self):
        """Missing attestation file must fail-closed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "RespectedBrain-Setup.exe"
            pkg.write_bytes(b"PACKAGE")

            ok, reason, _ = verify_release_provenance(pkg, root / "nonexistent.json", policy=self.policy)
            self.assertFalse(ok)
            self.assertIn("missing", reason.lower())


if __name__ == "__main__":
    unittest.main()
