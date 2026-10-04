"""Register and select vaults by stable UUID without CWD fallback."""
from __future__ import annotations

from collections.abc import Mapping, Callable
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from respectedbrain.core.config import ConfigStore, atomic_write_bytes
from respectedbrain.core.context import AppContext
from respectedbrain.core.errors import IdentityConflict, OwnershipConflict, SelectionError
from respectedbrain.core.paths import AppPaths, Roots
from respectedbrain.core.resources import ResourceCatalog

MACHINE_FIELDS = {"runtime_path", "runtime_dir", "app_root", "app_dir", "data_root", "vault_path"}


def _identity(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SelectionError("Vault marker contains an invalid UUID") from exc


def _read_marker(path: Path) -> dict[str, Any]:
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SelectionError(f"Cannot read vault marker: {path}") from exc
    if not isinstance(marker, dict):
        raise SelectionError("Vault marker must be an object")
    return marker


class VaultRegistry:
    def __init__(self, store: ConfigStore):
        self.store = store

    def register(self, path: Path, *, new_identity: bool = False,
                 writer: Callable[[Path, dict[str, Any]], None] | None = None) -> str:
        path = path.resolve()
        if not path.is_dir():
            raise SelectionError(f"Vault directory does not exist: {path}")
        if path.is_relative_to(self.store.data_root) or self.store.data_root.is_relative_to(path):
            raise SelectionError("Vault and data root must be separate")
        marker_path = path / ".respected.json"
        assigned = []
        marker_undo = []

        def register_locked(config: dict[str, Any]) -> None:
            original = marker_path.read_bytes() if marker_path.exists() else None
            marker = _read_marker(marker_path) if original is not None else {}
            identity = str(uuid4()) if new_identity or "vault_id" not in marker else _identity(marker["vault_id"])
            current = config["vaults"].get(identity)
            if current:
                old_path = Path(current["path"]).resolve()
                if old_path != path and old_path.exists():
                    raise IdentityConflict(f"Vault UUID is already registered at {old_path}")
            for other_id, entry in config["vaults"].items():
                if Path(entry["path"]).resolve() == path and other_id != identity:
                    raise IdentityConflict("A registered vault cannot silently change identity")
            updated = copy.deepcopy(marker)
            machine = {key: updated.pop(key) for key in MACHINE_FIELDS if key in updated}
            updated.update({"schema_version": 3, "vault_id": identity})
            entry = copy.deepcopy(current) if current else {"settings": {}}
            entry["path"] = str(path)
            if machine:
                entry.setdefault("legacy_metadata", {}).update(machine)
            if updated != marker:
                if original is not None:
                    transaction = datetime.now(timezone.utc).strftime("registration-%Y%m%dT%H%M%S-") + uuid4().hex
                    backup = self.store.data_root / "backups" / transaction / "marker.json"
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    backup.write_bytes(original)
                expected = (json.dumps(updated, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
                if writer is None:
                    atomic_write_bytes(marker_path, expected)
                else:
                    writer(marker_path, updated)
                marker_undo.append((original, expected))
            config["vaults"][identity] = entry
            if config["active_vault_id"] is None:
                config["active_vault_id"] = identity
            assigned.append(identity)

        def rollback_marker() -> None:
            if not marker_undo:
                return
            original, expected = marker_undo[0]
            if not marker_path.is_file() or marker_path.read_bytes() != expected:
                raise OwnershipConflict("Vault marker changed concurrently; rollback preserved the new content")
            if original is None:
                marker_path.unlink()
            else:
                atomic_write_bytes(marker_path, original)

        self.store.update(register_locked, rollback=rollback_marker, writer=writer)
        return assigned[0]

    def list(self) -> dict[str, dict[str, Any]]:
        return self.store.read()["vaults"]

    def discover(self, start: Path) -> Path | None:
        start = start.resolve()
        if start.is_file():
            start = start.parent
        for candidate in (start, *start.parents):
            marker = candidate / ".respected.json"
            if marker.is_file():
                _read_marker(marker)
                return candidate
        return None

    def select(self, *, vault: Path | None, vault_id: str | None, env: Mapping[str, str]) -> tuple[str, Path]:
        if vault is not None and vault_id is not None:
            raise SelectionError("Choose either --vault or --vault-id")
        config = self.store.read()
        if vault is not None:
            selected = vault.resolve()
            identity = self._selected_marker(selected)
        elif vault_id is not None:
            identity = _identity(vault_id)
            selected = None
        elif "RESPECTED_VAULT_PATH" in env:
            if not env["RESPECTED_VAULT_PATH"]:
                raise SelectionError("RESPECTED_VAULT_PATH is empty")
            selected = Path(env["RESPECTED_VAULT_PATH"]).resolve()
            identity = self._selected_marker(selected)
        else:
            identity = config["active_vault_id"]
            selected = None
        entry = config["vaults"].get(identity)
        if not entry:
            raise SelectionError("Vault is not registered; run vault register or setup")
        registered = Path(entry["path"]).resolve()
        if selected is not None and selected != registered:
            raise IdentityConflict("Selected path is not the registered path for this UUID")
        if self._selected_marker(registered) != identity:
            raise IdentityConflict("Registered path has a different vault UUID")
        return identity, registered

    @staticmethod
    def _selected_marker(path: Path) -> str:
        if not path.is_dir():
            raise SelectionError(f"Vault directory does not exist: {path}")
        marker = _read_marker(path / ".respected.json")
        if marker.get("schema_version") != 3 or "vault_id" not in marker:
            raise SelectionError("Vault must be registered or migrated before use")
        return _identity(marker["vault_id"])


def build_context(roots: Roots, store: ConfigStore, *, vault: Path | None, vault_id: str | None,
                  env: Mapping[str, str]) -> AppContext:
    identity, path = VaultRegistry(store).select(vault=vault, vault_id=vault_id, env=env)
    return AppContext(AppPaths(roots.app_root, roots.data_root, path, identity), store.read(), ResourceCatalog())
