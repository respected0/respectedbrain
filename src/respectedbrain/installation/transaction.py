"""Write-ahead file/external journal with compare-and-swap rollback."""
from __future__ import annotations
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Callable
from uuid import uuid4

from respectedbrain.core.config import atomic_write_bytes
from respectedbrain.core.errors import FoundationError, OwnershipConflict
from respectedbrain.core.locking import exclusive_lock
from .ownership import safe_path, digest, encode_bytes, decode_bytes


def _file_mode(path: Path) -> int | None:
    return stat.S_IMODE(path.stat().st_mode) if path.is_file() else None


def _mode_matches(row: dict, name: str, actual: int | None) -> bool:
    # Existing journals predate mode metadata; retain their byte-only recovery.
    return name not in row or row[name] == actual


def _validate_journal(document: dict, directory: Path) -> None:
    """Reject malformed recovery evidence before restoring any target."""
    try:
        if (not isinstance(document, dict) or document.get("schema_version") != 3
                or document["tx_id"] != directory.name
                or document["status"] not in ("active", "rollback-conflict", "rolled-back", "committed")):
            raise ValueError("Invalid transaction identity or status")
        if any(not isinstance(document[name], list) for name in ("files", "external", "directories")):
            raise ValueError("Invalid journal collections")
        seen = set()
        for row in document["files"]:
            name = row["path"]
            path = Path(name)
            if not isinstance(name, str) or not path.is_absolute() or ".." in path.parts or path in seen:
                raise ValueError("Invalid or duplicate journal target")
            seen.add(path)
            for field in ("before", "after"):
                value = row[field]
                if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)):
                    raise ValueError("Invalid journal hash")
            backup = row["backup"]
            if (backup is not None and (not isinstance(backup, str) or not re.fullmatch(r"file-[0-9]+\.bin", backup))
                    or (backup is None) != (row["before"] is None)):
                raise ValueError("Invalid before-image reference")
            for field in ("before_mode", "after_mode"):
                value = row.get(field)
                if value is not None and (type(value) is not int or not 0 <= value <= 0o7777):
                    raise ValueError("Invalid journal mode")
        for row in document["external"]:
            if (row["kind"] not in ("file", "mcp", "task", "shortcut", "registry")
                    or not isinstance(row["key"], str) or not row["key"] or "\0" in row["key"]):
                raise ValueError("Invalid journal external record")
            for field in ("before", "after"):
                value = row[field]
                if value is not None and not isinstance(value, str):
                    raise ValueError("Invalid external before-image")
                decode_bytes(value)
        for name in document["directories"]:
            if not isinstance(name, str) or not Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("Invalid journal directory")
    except (KeyError, TypeError, ValueError) as error:
        raise OwnershipConflict(f"Invalid transaction journal: {error}") from error


def _atomic_write_mode(path: Path, payload: bytes, mode: int | None) -> None:
    if mode is None:
        atomic_write_bytes(path, payload)
        return
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fchmod(handle.fileno(), mode) if hasattr(os, "fchmod") else os.chmod(temporary, mode)
            os.fsync(handle.fileno())
        os.replace(temporary, safe_path(path))
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class OperationResult:
    success: bool
    tx_id: str
    conflicts: tuple[str, ...]
    pending: bool = False


class Transaction:
    def __init__(self, data_root: Path, backend, *, vault_id: str | None = None,
                 fault: Callable[[str], None] | None = None):
        self.data_root = safe_path(data_root)
        self.backend, self.vault_id, self.fault = backend, vault_id, fault
        self.tx_id = "tx-" + str(uuid4())
        self.directory = data_root / "backups" / self.tx_id
        self.journal = self.directory / "journal.json"
        self.document = {"schema_version": 3, "tx_id": self.tx_id, "vault_id": vault_id,
                         "status": "active", "files": [], "external": [], "directories": []}
        self._stack = ExitStack()
        self._committed = False
        self.result = OperationResult(False, self.tx_id, ())

    def __enter__(self):
        try:
            safe_path(self.journal)
            self._stack.enter_context(exclusive_lock(safe_path(self.data_root / ".operation.lock"), timeout=0))
            self._stack.enter_context(self.backend.quiesce(self.vault_id))
            safe_path(self.directory).mkdir(parents=True, exist_ok=False)
            self._save()
            return self
        except BaseException:
            self._stack.close()
            raise

    def _save(self):
        # An unindented snapshot uses the JSON encoder's fast path. Keep schema
        # 3 and the same fsync + atomic replacement durability contract.
        payload = (json.dumps(self.document, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        atomic_write_bytes(safe_path(self.journal), payload)

    def checkpoint(self, phase: str):
        self.document["phase"] = phase
        self._save()
        if self.fault is not None:
            self.fault(phase)

    def _parent(self, path: Path):
        missing = []
        parent = path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        if not missing:
            return
        directories = list(reversed(missing))
        for directory in directories:
            safe_path(directory)
            self.document["directories"].append(str(directory))
        # Persist every planned directory before creating any. Recovery can
        # safely ignore absent directories if creation was interrupted.
        self._save()
        for directory in directories:
            safe_path(directory).mkdir()

    def backup(self, path: Path) -> None:
        self._capture_before(path, persist=True)

    def _capture_before(self, path: Path, *, persist: bool) -> dict:
        safe_path(path)
        existing = next((row for row in self.document["files"] if row["path"] == str(path)), None)
        if existing is not None:
            return existing
        if path.exists() and not path.is_file():
            raise OwnershipConflict(f"Expected regular file: {path}")
        payload = path.read_bytes() if path.exists() else None
        mode = _file_mode(path)
        backup = None
        if payload is not None:
            backup = f"file-{len(self.document['files'])}.bin"
            atomic_write_bytes(safe_path(self.directory / backup), payload)
        row = {"path": str(path), "backup": backup,
                                       "before": hashlib.sha256(payload).hexdigest() if payload is not None else None,
                                       "after": hashlib.sha256(payload).hexdigest() if payload is not None else None,
                                       "before_mode": mode, "after_mode": mode}
        self.document["files"].append(row)
        if persist:
            self._save()
        return row

    def adopt_before(self, path: Path, before: bytes | None):
        """Journal an Inno artifact whose pre-install bytes were captured earlier."""
        safe_path(path)
        if any(row["path"] == str(path) for row in self.document["files"]):
            raise OwnershipConflict("Shell artifact already journaled")
        backup = None
        if before is not None:
            backup = f"file-{len(self.document['files'])}.bin"
            atomic_write_bytes(safe_path(self.directory / backup), before)
        self.document["files"].append({"path": str(path), "backup": backup,
                                       "before": hashlib.sha256(before).hexdigest() if before is not None else None,
                                       "after": digest(path) if path.exists() else None})
        self._save()

    def write(self, target: Path, payload: bytes, *, mode: int | None = None) -> None:
        # The before-image is fsynced first; its record and expected output
        # share one durable snapshot before target mutation.
        row = self._capture_before(target, persist=False)
        actual = digest(target) if target.exists() else None
        if actual != row["after"] or not _mode_matches(row, "after_mode", _file_mode(target)):
            raise OwnershipConflict(f"Target changed during transaction: {target}")
        self._parent(target)
        row["after"] = hashlib.sha256(payload).hexdigest()
        if mode is not None and os.name == "nt":
            mode = (0o666 if mode & stat.S_IWRITE else 0o444) | (0o111 if target.suffix.casefold() in (".exe", ".com", ".bat", ".cmd") else 0)
        row["after_mode"] = mode if mode is not None else _file_mode(target)
        if row["after_mode"] is None:
            row["after_mode"] = 0o666 if os.name == "nt" else 0o600
        self._save()  # durable expected result before the filesystem mutation
        _atomic_write_mode(safe_path(target), payload, row["after_mode"])

    def write_json(self, target: Path, document: dict) -> None:
        self.write(target, (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))

    def replace(self, source: Path, target: Path) -> None:
        safe_path(source)
        if source.is_dir():
            if target.exists() and not target.is_dir():
                raise OwnershipConflict(f"Expected directory: {target}")
            for item in sorted(source.rglob("*")):
                safe_path(item)
                if item.is_file():
                    self.write(target / item.relative_to(source), item.read_bytes(), mode=_file_mode(item))
                elif not item.is_dir():
                    raise OwnershipConflict(f"Unexpected payload: {item}")
        else:
            self.write(target, source.read_bytes(), mode=_file_mode(source))

    def remove(self, target: Path, *, expected_hash: str) -> None:
        safe_path(target)
        if not target.is_file() or digest(target) != expected_hash:
            raise OwnershipConflict(f"Changed owned target: {target}")
        self.backup(target)
        row = next(row for row in self.document["files"] if row["path"] == str(target))
        row["after"] = None
        row["after_mode"] = None
        self._save()
        safe_path(target).unlink()

    def apply_external(self, change) -> None:
        if self.backend.read(change.kind, change.key) != change.before:
            raise OwnershipConflict(f"External record changed: {change.kind}:{change.key}")
        self.document["external"].append({"kind": change.kind, "key": change.key,
                                           "before": encode_bytes(change.before), "after": encode_bytes(change.after)})
        self._save()
        if change.kind in ("file", "mcp", "shortcut"):
            target = Path(change.key)
            if target.is_absolute():
                self._parent(safe_path(target))
        self.backend.apply(change)
        if self.backend.read(change.kind, change.key) != change.after:
            raise OwnershipConflict(f"External readback mismatch: {change.kind}:{change.key}")

    def commit(self) -> OperationResult:
        for row in self.document["files"]:
            path = safe_path(Path(row["path"]))
            actual = digest(path) if path.is_file() else None
            if (actual != row["after"] or not _mode_matches(row, "after_mode", _file_mode(path))
                    or path.exists() and not path.is_file()):
                raise OwnershipConflict(f"Target changed before commit: {path}")
        checked = set()
        for row in reversed(self.document["external"]):
            key = (row["kind"], row["key"])
            if key not in checked and self.backend.read(*key) != decode_bytes(row["after"]):
                raise OwnershipConflict(f"External record changed before commit: {key[0]}:{key[1]}")
            checked.add(key)
        self.document["status"] = "committed"
        self._save()
        self._committed = True
        self.result = OperationResult(True, self.tx_id, ())
        return self.result

    def rollback(self) -> OperationResult:
        _validate_journal(self.document, self.directory)
        conflicts = []
        for row in reversed(self.document["external"]):
            change = SimpleNamespace(kind=row["kind"], key=row["key"], before=decode_bytes(row["before"]), after=decode_bytes(row["after"]))
            try:
                current = self.backend.read(change.kind, change.key)
                if current == change.before:
                    continue
                if current != change.after:
                    raise OwnershipConflict("External record changed")
                self.backend.restore(change)
            except (OSError, ValueError, FoundationError):
                conflicts.append(change.kind + ":" + change.key)
        for row in reversed(self.document["files"]):
            path = Path(row["path"])
            try:
                safe_path(path)
                actual = digest(path) if path.is_file() else None
                mode = _file_mode(path)
                if actual == row["before"] and _mode_matches(row, "before_mode", mode):
                    continue
                if actual != row["after"] or not _mode_matches(row, "after_mode", mode) or (path.exists() and not path.is_file()):
                    raise OwnershipConflict("Rollback target changed")
                if row["backup"] is None:
                    path.unlink(missing_ok=True)
                else:
                    backup = safe_path(self.directory / row["backup"])
                    if digest(backup) != row["before"]:
                        raise OwnershipConflict("Backup changed")
                    _atomic_write_mode(path, backup.read_bytes(), row.get("before_mode"))
            except (OSError, ValueError, OwnershipConflict):
                conflicts.append(str(path))
        for name in reversed(self.document["directories"]):
            directory = Path(name)
            try:
                safe_path(directory)
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            except (OSError, OwnershipConflict):
                conflicts.append(name)
        self.document.update(status="rollback-conflict" if conflicts else "rolled-back", conflicts=conflicts)
        self._save()
        self.result = OperationResult(False, self.tx_id, tuple(conflicts))
        return self.result

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if not self._committed:
                self.rollback()
        finally:
            self._stack.close()
        return False


def recover_transactions(data_root: Path, backend) -> tuple[OperationResult, ...]:
    safe_path(data_root)
    backups = safe_path(data_root / "backups")
    if not backups.is_dir():
        return ()
    results = []
    with exclusive_lock(safe_path(data_root / ".operation.lock"), timeout=0), backend.quiesce(None):
        for journal in sorted(backups.glob("tx-*/journal.json")):
            document = json.loads(safe_path(journal).read_text(encoding="utf-8"))
            _validate_journal(document, journal.parent)
            if document["status"] not in ("active", "rollback-conflict"):
                continue
            tx = Transaction(data_root, backend, vault_id=document.get("vault_id"))
            tx.document, tx.directory, tx.journal, tx.tx_id = document, journal.parent, journal, document["tx_id"]
            results.append(tx.rollback())
    return tuple(results)
