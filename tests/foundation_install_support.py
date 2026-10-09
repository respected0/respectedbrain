from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
from unittest import mock

from respectedbrain import __version__


ATTESTATION_NAME = "distribution.json.attestation.json"


def write_fixture_attestation(package: Path) -> Path:
    manifest = package / "distribution.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
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
            "ref": f"refs/tags/v{document['version']}",
        }}}},
    }
    bundle = {
        "mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.2",
        "dsseEnvelope": {
            "payload": base64.b64encode(json.dumps(statement).encode("utf-8")).decode("ascii"),
            "payloadType": "application/vnd.in-toto+json",
            "signatures": [{"sig": "fixture-policy"}],
        },
    }
    target = package / ATTESTATION_NAME
    target.write_text(json.dumps(bundle), encoding="utf-8")
    return target


def fixture_gh_path(root: Path) -> Path:
    bin_dir = root / "fixture-gh"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        executable = bin_dir / "gh.cmd"
        executable.write_text(
            '@echo off\r\n'
            'if "%~1"=="--version" (\r\n'
            '  echo gh version 2.102.0\r\n'
            '  exit /b 0\r\n'
            ')\r\n'
            'if "%~1"=="attestation" if "%~2"=="verify" (\r\n'
            '  echo [{"fixture":"verified"}]\r\n'
            '  exit /b 0\r\n'
            ')\r\n'
            'exit /b 2\r\n',
            encoding="utf-8",
        )
    else:
        executable = bin_dir / "gh"
        executable.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = "--version" ]; then\n'
            "  printf '%s\\n' 'gh version 2.102.0'\n"
            '  exit 0\n'
            'fi\n'
            'if [ "$1" = "attestation" ] && [ "$2" = "verify" ]; then\n'
            "  printf '%s\\n' '[{\"fixture\":\"verified\"}]'\n"
            '  exit 0\n'
            'fi\n'
            'exit 2\n',
            encoding="utf-8",
        )
        executable.chmod(0o755)
    return bin_dir


@contextmanager
def fixture_gh(root: Path):
    bin_dir = fixture_gh_path(root)
    with mock.patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}):
        yield bin_dir


def seed_package(path: Path, *, content: bytes = b"MZ-fixture") -> Path:
    files = {"respectedbrain.exe": content, "app/respectedbrain/resources/defaults.json": b'{"summary_provider":"auto"}'}
    for relative, payload in files.items():
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (path / "distribution.json").write_text(json.dumps({"schema_version": 3, "version": __version__, "platform": "windows", "launcher": "respectedbrain.exe", "files": {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}}), encoding="utf-8")
    write_fixture_attestation(path)
    return path
