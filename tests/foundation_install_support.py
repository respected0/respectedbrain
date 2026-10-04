"""Small hash-verified payload fixtures; executable health is tested natively later."""
from pathlib import Path
import hashlib
import json
from respectedbrain import __version__


def seed_package(path: Path, *, content: bytes = b"MZ-fixture") -> Path:
    files = {"respectedbrain.exe": content, "app/respectedbrain/resources/defaults.json": b'{"summary_provider":"auto"}'}
    for relative, payload in files.items():
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (path / "distribution.json").write_text(json.dumps({"schema_version": 3, "version": __version__, "platform": "windows", "launcher": "respectedbrain.exe", "files": {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}}), encoding="utf-8")
    return path
