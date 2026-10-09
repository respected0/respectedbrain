"""Strict fixture lifecycle proves the manifest attestation reaches every consumer."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from respectedbrain import __version__
from respectedbrain.core.config import ConfigStore
from respectedbrain.core.paths import Roots
from respectedbrain.installation.deferred import defer_operation, resume_operation
from respectedbrain.installation.ownership import digest, read_manifest
from respectedbrain.installation.provenance import TrustedProvenancePolicy
from respectedbrain.installation.repair import repair
from respectedbrain.installation.setup import setup
from respectedbrain.installation.update import update
from respectedbrain.vault.registry import build_context
from tests.foundation_install_support import seed_package
from tests.foundation_transactions_test import Backend


ATTESTATION = "distribution.json.attestation.json"


def attach_attestation(package: Path) -> Path:
    manifest = package / "distribution.json"
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{
            "name": "distribution.json",
            "digest": {"sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()},
        }],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {"buildDefinition": {"externalParameters": {"workflow": {
            "repository": "https://github.com/respected0/respectedbrain",
            "path": ".github/workflows/release.yml",
            "ref": f"refs/tags/v{__version__}",
        }}}},
    }
    bundle = {
        "mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.2",
        "dsseEnvelope": {
            "payload": base64.b64encode(json.dumps(statement).encode()).decode(),
            "payloadType": "application/vnd.in-toto+json",
            "signatures": [{"sig": "fixture-policy"}],
        },
    }
    target = package / ATTESTATION
    target.write_text(json.dumps(bundle), encoding="utf-8")
    return target


class ProvenanceLifecycleTransportTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "deferred activation is Windows-only")
    def test_attestation_survives_setup_update_repair_and_deferred_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            roots = Roots(root / "app", root / "data", root / "vault")
            home = root / "home"
            home.mkdir()
            backend = Backend()
            packages = [seed_package(root / f"package-{index}", content=f"MZ-{index}".encode()) for index in range(3)]
            for package in packages:
                attach_attestation(package)
            policy = TrustedProvenancePolicy(
                expected_ref=f"refs/tags/v{__version__}",
                verifier_callable=lambda *_: (True, "explicit fixture policy"),
            )
            policy_patch = mock.patch(
                "respectedbrain.installation.provenance.TrustedProvenancePolicy",
                return_value=policy,
            )
            health_patch = mock.patch(
                "respectedbrain.installation.payload.validate_installed_health",
                return_value=None,
            )
            with policy_patch, health_patch:
                result = setup(
                    roots,
                    roots.default_vault,
                    profile={"platform": "windows-native", "user_home": str(home)},
                    desired={"global": False, "mcp": False, "schedule": False, "shortcut": False},
                    backend=backend,
                    package=packages[0],
                    require_provenance=True,
                )
                self.assertTrue(result.success, result.conflicts)
                self.assertTrue((roots.app_root / ATTESTATION).is_file())
                self.assertIn(roots.app_root / ATTESTATION, {item.path for item in read_manifest(roots.data_root / "install-manifest.json").files})
                store = ConfigStore(roots.data_root)
                ctx = build_context(roots, store, vault=roots.default_vault, vault_id=None, env={})
                result = update(ctx, package=packages[1], backend=backend, require_provenance=True)
                self.assertTrue(result.success, result.conflicts)
                self.assertTrue((roots.app_root / ATTESTATION).is_file())
                result = repair(ctx, backend=backend, require_provenance=True)
                self.assertTrue(result.success, result.conflicts)

                captured = []

                def capture(*command, **kwargs):
                    captured.append(command[0])
                    return mock.Mock()

                launcher = roots.app_root / "respectedbrain.exe"
                with (
                    mock.patch("respectedbrain.installation.deferred.sys.frozen", True, create=True),
                    mock.patch("respectedbrain.installation.deferred.sys.executable", str(launcher)),
                    mock.patch("respectedbrain.installation.deferred.subprocess.Popen", side_effect=capture),
                    mock.patch("respectedbrain.installation.deferred._wait_parent", return_value=None),
                ):
                    pending = defer_operation(ctx, mode="update", package=packages[2], require_provenance=True)
                self.assertTrue(pending.pending)
                request = Path(captured[-1][captured[-1].index("--request") + 1])
                with mock.patch("respectedbrain.installation.deferred._wait_parent", return_value=None):
                    self.assertEqual(resume_operation(request, expected_hash=digest(request), require_provenance=True), 0)
            self.assertTrue((roots.app_root / ATTESTATION).is_file())
            self.assertIn(roots.app_root / ATTESTATION, {item.path for item in read_manifest(roots.data_root / "install-manifest.json").files})


if __name__ == "__main__":
    unittest.main()
