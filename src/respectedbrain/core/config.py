"""Schema 3 user configuration, with atomic writes and no lost updates."""
from __future__ import annotations

from collections.abc import Callable
import copy
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from .errors import SelectionError
from .locking import exclusive_lock
from .resources import ResourceCatalog


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    payload = (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    atomic_write_bytes(path, payload)


def validate_config(document: dict[str, Any]) -> None:
    if not isinstance(document, dict) or document.get("schema_version") != 3:
        raise SelectionError("User configuration requires schema 3; migrate the legacy configuration first")
    for field in ("vaults", "preferences", "integrations"):
        if not isinstance(document.get(field), dict):
            raise SelectionError(f"Config {field} must be an object")
    active = document.get("active_vault_id")
    if active is not None and active not in document["vaults"]:
        raise SelectionError("The active vault is not registered")


class ConfigStore:
    def __init__(self, data_root: Path):
        if not data_root.is_absolute():
            raise SelectionError("Config data root must be absolute")
        self.data_root = data_root.resolve()
        self.path = self.data_root / "config.json"
        self.lock_path = self.data_root / ".config.lock"

    def read(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                document = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise SelectionError(f"Cannot read user configuration: {self.path}") from exc
        else:
            defaults = json.loads(ResourceCatalog().read_text("defaults.json"))
            document = {"schema_version": 3, "active_vault_id": None, "vaults": {},
                        "preferences": {key: value for key, value in defaults.items() if key != "integrations"},
                        "integrations": defaults.get("integrations", {})}
        validate_config(document)
        return copy.deepcopy(document)

    def update(self, mutator: Callable[[dict[str, Any]], None], *, rollback: Callable[[], None] | None = None,
               writer: Callable[[Path, dict[str, Any]], None] | None = None) -> dict[str, Any]:
        with exclusive_lock(self.lock_path):
            document = self.read()
            try:
                mutator(document)
                validate_config(document)
                (writer or atomic_write_json)(self.path, document)
            except Exception:
                if rollback is not None:
                    rollback()
                raise
            return copy.deepcopy(document)
