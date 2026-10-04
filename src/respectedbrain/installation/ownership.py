"""Only recorded, unchanged application files are owned by the product."""
from __future__ import annotations
from dataclasses import dataclass
import base64
import hashlib
import stat
from pathlib import Path
from typing import Any

from respectedbrain.core import platform
from respectedbrain.core.config import atomic_write_json
from respectedbrain.core.errors import OwnershipConflict


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise OwnershipConflict(f"Unsafe absolute target: {path}")
    if not platform.path_within_vault(path, Path(path.anchor)):
        raise OwnershipConflict(f"Link or reparse target: {path}")
    return path


@dataclass(frozen=True)
class OwnedFile:
    path: Path
    sha256: str
    role: str
    mode: int | None = None


@dataclass(frozen=True)
class OwnershipManifest:
    schema_version: int
    files: tuple[OwnedFile, ...]
    external: tuple[Any, ...]


def prove_ownership(path: Path, manifest: OwnershipManifest) -> bool:
    try:
        safe_path(path)
        return path.is_file() and any(item.path == path and item.sha256 == digest(path)
                                      and item.role in ("application", "technical", "uninstaller", "launcher")
                                      and (item.mode is None and item.role != "launcher" or item.mode == stat.S_IMODE(path.stat().st_mode))
                                      for item in manifest.files)
    except (OSError, OwnershipConflict):
        return False


def encode_bytes(value: bytes | None) -> str | None:
    return None if value is None else base64.b64encode(value).decode("ascii")


def decode_bytes(value: str | None) -> bytes | None:
    return None if value is None else base64.b64decode(value, validate=True)


def baseline_change(change):
    """Separate committed uninstall baseline from the rollback before-image."""
    from respectedbrain.integrations.backend import ExternalChange
    before = change.uninstall_before if getattr(change, "has_uninstall_baseline", False) else change.before
    return ExternalChange(change.kind, change.key, before, change.after)


def manifest_document(manifest: OwnershipManifest) -> dict:
    return {"schema_version": manifest.schema_version,
            "files": [{"path": str(item.path), "sha256": item.sha256, "role": item.role, **({"mode": item.mode} if item.mode is not None else {})} for item in manifest.files],
            "external": [{"kind": item.kind, "key": item.key, "before": encode_bytes(baseline_change(item).before), "after": encode_bytes(item.after)} for item in manifest.external]}


def read_manifest(path: Path) -> OwnershipManifest:
    import json
    from respectedbrain.integrations.backend import ExternalChange
    document = json.loads(safe_path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") != 3:
        raise OwnershipConflict("Ownership manifest requires schema 3")
    files = tuple(OwnedFile(Path(row["path"]), row["sha256"], row["role"], row.get("mode")) for row in document["files"])
    external = tuple(ExternalChange(row["kind"], row["key"], decode_bytes(row["before"]), decode_bytes(row["after"])) for row in document["external"])
    return OwnershipManifest(3, files, external)
