"""Only recorded, unchanged application files are owned by the product."""
from __future__ import annotations
from dataclasses import dataclass
import base64
import hashlib
import re
import stat
from pathlib import Path
from typing import Any

from respectedbrain.core import platform
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
    try:
        document = json.loads(safe_path(path).read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema_version") != 3:
            raise ValueError("Ownership manifest requires schema 3")
        if not isinstance(document["files"], list) or not isinstance(document["external"], list):
            raise ValueError("Invalid ownership collections")
        files, external = [], []
        file_paths, external_keys = set(), set()
        for row in document["files"]:
            target = Path(row["path"])
            mode = row.get("mode")
            if (not target.is_absolute() or ".." in target.parts
                    or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                    or row["role"] not in ("application", "technical", "uninstaller", "launcher")
                    or mode is not None and (type(mode) is not int or not 0 <= mode <= 0o7777)
                    or target in file_paths):
                raise ValueError("Invalid or duplicate owned file")
            file_paths.add(target)
            files.append(OwnedFile(target, row["sha256"], row["role"], mode))
        for row in document["external"]:
            if (row["kind"] not in ("file", "mcp", "task", "shortcut", "registry")
                    or not isinstance(row["key"], str) or not row["key"] or "\0" in row["key"]
                    or (row["kind"], row["key"]) in external_keys
                    or any(value is not None and not isinstance(value, str) for value in (row["before"], row["after"]))):
                raise ValueError("Invalid or duplicate external ownership")
            external_keys.add((row["kind"], row["key"]))
            external.append(ExternalChange(row["kind"], row["key"], decode_bytes(row["before"]), decode_bytes(row["after"])))
        return OwnershipManifest(3, tuple(files), tuple(external))
    except (KeyError, TypeError, ValueError) as error:
        raise OwnershipConflict(f"Invalid ownership manifest: {error}") from error
