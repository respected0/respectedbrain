"""Cryptographic build provenance and SLSA attestation verifier for release binaries."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable


class ProvenanceVerificationError(Exception):
    """Raised when release artifact provenance fails verification."""
    pass


def _load_bundle_entries(text: str) -> list[dict[str, Any]]:
    trimmed = text.strip()
    if not trimmed:
        return []
    try:
        document = json.loads(trimmed)
    except json.JSONDecodeError:
        entries = []
        decoder = json.JSONDecoder()
        offset = 0
        while offset < len(trimmed):
            while offset < len(trimmed) and trimmed[offset].isspace():
                offset += 1
            if offset >= len(trimmed):
                break
            item, offset = decoder.raw_decode(trimmed, offset)
            if isinstance(item, dict):
                entries.append(item)
        return entries
    if isinstance(document, list):
        return [item for item in document if isinstance(item, dict)]
    if isinstance(document, dict):
        return [document]
    return []


@dataclass(frozen=True)

class TrustedProvenancePolicy:
    """Official release verification policy constraints."""
    expected_repo: str = "respected0/respectedbrain"
    expected_workflow: str = ".github/workflows/release.yml"
    expected_ref_prefix: str = "refs/tags/v"
    expected_ref: str | None = None
    expected_subject_name: str = "distribution.json"
    expected_predicate_type: str = "https://slsa.dev/provenance/v1"
    expected_issuer: str = "https://token.actions.githubusercontent.com"
    enforce_provenance: bool = True
    verifier_callable: Callable[[Path, Path, "TrustedProvenancePolicy"], tuple[bool, str]] | None = None


def verify_release_provenance(
    package_path: Path,
    attestation_bundle_path: Path | None = None,
    *,
    policy: TrustedProvenancePolicy | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Verify cryptographic provenance and SLSA build attestation against a trusted policy.

    Fails-closed on missing provenance, hash mismatch, untrusted repo/workflow/ref, or invalid signatures.
    Returns:
        (verified: bool, reason: str, details: dict[str, Any])
    """
    if policy is None:
        policy = TrustedProvenancePolicy()

    pkg = Path(package_path)
    if not pkg.is_file():
        return False, f"Target package not found: {pkg}", {}

    actual_sha256 = hashlib.sha256(pkg.read_bytes()).hexdigest()

    # Determine bundle file path
    bundle_file = attestation_bundle_path
    if bundle_file is None:
        candidates = [
            pkg.with_name(f"{pkg.name}.attestation.json"),
            pkg.with_name(f"{pkg.name}.bundle.jsonl"),
            pkg.with_name("attestation.json"),
        ]
        for c in candidates:
            if c.is_file():
                bundle_file = c
                break

    if bundle_file is None or not Path(bundle_file).is_file():
        return False, "Missing build provenance attestation file; fail-closed", {}

    try:
        entries = _load_bundle_entries(Path(bundle_file).read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Failed to parse attestation bundle: {exc}", {}
    if len(entries) != 1:
        return False, "Attestation bundle must contain exactly one DSSE envelope", {}
    raw_bundle = entries[0]

    # Disallow bare unsigned in-toto statements: attestation must be wrapped in a cryptographic envelope
    if isinstance(raw_bundle, dict) and raw_bundle.get("_type") == "https://in-toto.io/Statement/v1":
        return False, "Unsigned in-toto statement rejected: cryptographic attestation envelope required", {}

    payload: dict[str, Any] = {}
    if isinstance(raw_bundle, dict) and "dsseEnvelope" in raw_bundle:
        envelope = raw_bundle["dsseEnvelope"]
        sigs = envelope.get("signatures", [])
        if not sigs or not any(s.get("sig") for s in sigs):
            return False, "Missing cryptographic signature in DSSE envelope", {}

        # 1. Cryptographic signature and attestation verification
        if policy.verifier_callable is not None:
            ok, verifier_msg = policy.verifier_callable(pkg, Path(bundle_file), policy)
            if not ok:
                return False, f"Cryptographic attestation verification failed: {verifier_msg}", {}
        else:
            verifier_bin = shutil.which("gh")
            if verifier_bin is None or not policy.expected_ref:
                return False, "Cryptographic attestation verifier not available (pinned gh required); fail-closed", {}
            signer_identity = f"https://github.com/{policy.expected_repo}/{policy.expected_workflow}@{policy.expected_ref}"
            cmd = [
                verifier_bin, "attestation", "verify", str(pkg),
                "--repo", policy.expected_repo,
                "--bundle", str(bundle_file),
                "--cert-identity", signer_identity,
                "--cert-oidc-issuer", policy.expected_issuer,
                "--source-ref", policy.expected_ref,
                "--predicate-type", policy.expected_predicate_type,
                "--deny-self-hosted-runners",
                "--limit", "1",
                "--format", "json",
            ]
            try:
                version_proc = subprocess.run([verifier_bin, "--version"], capture_output=True, text=True, timeout=10, check=False)
                if version_proc.returncode != 0 or "gh version 2.102.0" not in version_proc.stdout:
                    return False, "Unsupported gh verifier version; pinned 2.102.0 required", {}
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
                if proc.returncode != 0 or not isinstance(json.loads(proc.stdout), list) or not json.loads(proc.stdout):
                    return False, f"Cryptographic verifier rejected attestation: {proc.stderr.strip()}", {}
            except Exception as exc:
                return False, f"Cryptographic verifier execution error: {exc}", {}

        try:
            payload_str = base64.b64decode(envelope["payload"]).decode("utf-8")
            payload = json.loads(payload_str)
        except Exception as exc:
            return False, f"Corrupted DSSE envelope payload: {exc}", {}
    else:
        return False, "Unsupported attestation bundle structure", {}

    # 2. Subject digest matching (cryptographic link between artifact SHA-256 and attestation)
    if payload.get("predicateType") != policy.expected_predicate_type:
        return False, f"Provenance predicate type mismatch ({payload.get('predicateType')})", {}
    subjects = payload.get("subject", [])
    matching_subject = None
    for s in subjects:
        digest_dict = s.get("digest", {})
        if s.get("name") == policy.expected_subject_name and digest_dict.get("sha256", "").lower() == actual_sha256.lower():
            matching_subject = s
            break

    if not matching_subject:
        return False, f"Package SHA-256 ({actual_sha256}) hash mismatch with provenance subject digest", {}

    # 3. SLSA Predicate build definition inspection
    predicate = payload.get("predicate", {})
    build_def = predicate.get("buildDefinition", {})
    ext_params = build_def.get("externalParameters", {})
    workflow_info = ext_params.get("workflow", {})

    # Repository validation (strictly match expected repo on trusted GitHub origin, reject foreign origins)
    repo_uri = str(workflow_info.get("repository", "")).strip().rstrip("/")
    trusted_repos = {
        f"https://github.com/{policy.expected_repo.lower()}",
        f"git+https://github.com/{policy.expected_repo.lower()}",
        policy.expected_repo.lower(),
    }
    if repo_uri.lower() not in trusted_repos:
        return False, f"Provenance repository mismatch ({repo_uri} does not match trusted {policy.expected_repo})", {}

    # Workflow path validation (exact match)
    workflow_path = str(workflow_info.get("path", "")).strip()
    if policy.expected_workflow and workflow_path != policy.expected_workflow:
        return False, f"Provenance workflow mismatch ({workflow_path} != {policy.expected_workflow})", {}

    # Ref prefix validation
    ref = str(workflow_info.get("ref", "")).strip()
    if policy.expected_ref and ref != policy.expected_ref:
        return False, f"Provenance ref mismatch ({ref} != {policy.expected_ref})", {}
    if not policy.expected_ref and policy.expected_ref_prefix and not ref.startswith(policy.expected_ref_prefix):
        return False, f"Provenance ref mismatch ({ref} does not start with {policy.expected_ref_prefix})", {}

    return True, "Provenance verified successfully", {
        "repo": policy.expected_repo,
        "workflow": policy.expected_workflow,
        "ref": ref,
        "sha256": actual_sha256,
        "subject_name": matching_subject.get("name"),
    }
