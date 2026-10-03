"""A serializable, side-effect-free migration plan; activation is separate."""
from __future__ import annotations
from dataclasses import dataclass
import copy
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from respectedbrain.core.config import ConfigStore
from respectedbrain.core.context import AppContext
from respectedbrain.core.errors import FoundationError, OwnershipConflict
from respectedbrain.core.paths import AppPaths, Roots
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.integrations.backend import ExternalChange, IntegrationBackend, IntegrationProfile
from .ownership import digest, encode_bytes, safe_path

@dataclass(frozen=True)
class MigrationEntry:
    source: Path
    target: Path | None
    action: str
    sha256: str | None
    ownership: str

@dataclass(frozen=True)
class MigrationPlan:
    vault_id: str
    entries: tuple[MigrationEntry, ...]
    config: dict[str, Any]
    external: tuple[ExternalChange, ...]
    conflicts: tuple[str, ...]


def _uuid(value) -> str | None:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def plan_migration(legacy_root: Path, vault: Path, *, roots: Roots, backend: IntegrationBackend,
                   profile: IntegrationProfile) -> MigrationPlan:
    from .legacy import FLAGS, inventory_legacy, _read_object
    conflicts: list[str] = []
    marker = {}
    current = None
    for path in (Path(legacy_root), Path(vault), roots.app_root, roots.data_root):
        try:
            safe_path(path)
        except (OSError, FoundationError) as error:
            conflicts.append(str(error))
    # Never read through a rejected source/root.
    if conflicts:
        return MigrationPlan(str(uuid4()), (), {}, (), tuple(conflicts))
    if not vault.is_dir():
        return MigrationPlan(str(uuid4()), (), {}, (), (f"Missing vault: {vault}",))
    marker_path = vault / ".respected.json"
    if marker_path.exists() or marker_path.is_symlink():
        try:
            marker = _read_object(marker_path)
        except (OSError, ValueError, FoundationError) as error:
            conflicts.append(f"legacy-marker:{error}")
    config_path = roots.data_root / "config.json"
    if config_path.exists() or config_path.is_symlink():
        try:
            safe_path(config_path)
            loaded = _read_object(config_path)
            if loaded.get("schema_version") == 3:
                current = ConfigStore(roots.data_root).read()
        except (OSError, ValueError, FoundationError) as error:
            conflicts.append(f"user-config:{error}")
    inventory = inventory_legacy(legacy_root, vault, roots=roots, backend=backend)
    conflicts.extend(inventory.conflicts)
    defaults = json.loads(ResourceCatalog().read_text("defaults.json"))
    config = copy.deepcopy(current) if current is not None else {"schema_version":3,"active_vault_id":None,"vaults":{},"preferences":{},"integrations":{}}
    for key, value in inventory.preferences.items():
        config["preferences"].setdefault(key, value)
    for key, value in defaults.items():
        if key != "integrations":
            config["preferences"].setdefault(key, copy.deepcopy(value))
    for key, value in inventory.desired.items():
        config["integrations"].setdefault(key, value)
    for key in FLAGS:
        config["integrations"].setdefault(key, defaults.get("integrations", {}).get(key, False))
    identity = _uuid(marker.get("vault_id"))
    matches = [key for key, row in config["vaults"].items() if isinstance(row, dict) and Path(row.get("path", "")) == vault]
    if identity is None and matches:
        identity = _uuid(matches[0])
    if marker.get("schema_version") == 3 and _uuid(marker.get("vault_id")) is None:
        conflicts.append("invalid-schema3-vault-id")
    identity = identity or str(uuid4())
    if matches and matches != [identity]:
        conflicts.append("vault-registration-identity-conflict")
    registered = config["vaults"].get(identity, {})
    if registered and Path(registered.get("path", "")) != vault and Path(registered.get("path", "")).exists():
        conflicts.append("vault-uuid-has-two-live-paths")
    record = copy.deepcopy(registered)
    record.setdefault("settings", {})
    record["path"] = str(vault)
    metadata = record.setdefault("legacy_metadata", {})
    if marker:
        metadata["marker"] = copy.deepcopy(marker)
    configs = []
    for entry in inventory.entries:
        if entry.action == "merge-config" and not (entry.source == config_path and current is not None):
            try:
                configs.append({"source":str(entry.source),"document":_read_object(entry.source)})
            except (OSError, ValueError, FoundationError) as error:
                conflicts.append(f"legacy-config:{error}")
    if configs:
        metadata["configs"] = configs
    config["vaults"][identity] = record
    if config["active_vault_id"] is None:
        config["active_vault_id"] = identity
    entries = []
    targets: dict[Path, str | None] = {}
    pending = roots.data_root / "vaults" / "_pending"
    for entry in inventory.entries:
        target = entry.target
        if target is not None and target.is_relative_to(pending):
            target = roots.data_root / "vaults" / identity / target.relative_to(pending)
        ownership = entry.ownership
        if target is not None:
            try:
                safe_path(target)
                if entry.action in ("copy-state", "preserve-override"):
                    expected = targets.setdefault(target, entry.sha256)
                    if expected != entry.sha256:
                        raise OwnershipConflict(f"conflicting-source-content:{target}")
                    if target.exists() and (not target.is_file() or digest(target) != entry.sha256):
                        raise OwnershipConflict(f"conflicting-target-content:{target}")
            except (OSError, FoundationError) as error:
                conflicts.append(str(error))
                ownership = "conflict"
        entries.append(MigrationEntry(entry.source, target, entry.action, entry.sha256, ownership))
    # These source hashes also protect config/marker races between preview and apply.
    entries = [row for row in entries if row.source not in (marker_path, config_path)]
    for path in (marker_path, config_path):
        try:
            safe_path(path)
            if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
                raise OwnershipConflict(f"Unsafe migration metadata: {path}")
            entries.append(MigrationEntry(path, path, "merge-config", digest(path) if path.exists() else None, "user"))
        except (OSError, FoundationError) as error:
            conflicts.append(str(error))
            entries.append(MigrationEntry(path, path, "merge-config", None, "conflict"))
    external: tuple[ExternalChange, ...] = ()
    try:
        paths = AppPaths(roots.app_root, roots.data_root, vault, identity)
        for target in (paths.state_dir, paths.cache_dir, paths.overrides_dir):
            safe_path(target)
        ctx = AppContext(paths, config, ResourceCatalog())
        preview = getattr(backend, "preview", None)
        if not callable(preview):
            conflicts.append("external-preview-unavailable")
        else:
            external = tuple(preview(ctx, desired=config["integrations"], profile=profile))
            inspect = getattr(backend, "inspect_legacy_registrations", None)
            if callable(inspect):
                snapshots = tuple(inspect(legacy_root, vault, roots, profile))
                changes = {(item.kind, item.key):item for item in snapshots}
                changes.update({(item.kind, item.key):item for item in external})
                external = tuple(changes.values())
    except (OSError, ValueError, TypeError, FoundationError) as error:
        conflicts.append(f"external-preview:{error}")
    return MigrationPlan(identity, tuple(entries), config, external, tuple(dict.fromkeys(conflicts)))


def plan_document(plan: MigrationPlan) -> dict[str, Any]:
    """Every source/target/hash and external before/after byte payload is visible."""
    return {"vault_id":plan.vault_id,
            "entries":[{"source":str(row.source),"target":str(row.target) if row.target else None,
                        "action":row.action,"sha256":row.sha256,"ownership":row.ownership} for row in plan.entries],
            "config":copy.deepcopy(plan.config), "desired":copy.deepcopy(plan.config.get("integrations", {})),
            "external":[{"kind":row.kind,"key":row.key,"before":encode_bytes(row.before),"after":encode_bytes(row.after)} for row in plan.external],
            "conflicts":list(plan.conflicts)}
