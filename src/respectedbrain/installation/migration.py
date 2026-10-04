"""A serializable, side-effect-free migration plan; activation is separate."""
from __future__ import annotations
from dataclasses import dataclass
import copy
import json
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .transaction import OperationResult
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


class _PlannedResources(ResourceCatalog):
    def __init__(self, base, overlays):
        self.base, self.overlays = base, overlays
    def read_text(self, relative):
        return self.overlays[relative] if relative in self.overlays else self.base.read_text(relative)
    def iter_files(self, relative):
        prefix = relative.rstrip("/") + "/"
        return tuple(sorted(set(self.base.iter_files(relative)) | {name[len(prefix):] for name in self.overlays if name.startswith(prefix)}))


def _planned_resources(paths, entries):
    overrides = {}
    for row in entries:
        if row.action == "preserve-override":
            if row.target is None or not row.target.is_relative_to(paths.overrides_dir) or _regular_hash(row.source) != row.sha256:
                raise OwnershipConflict(f"Planned override changed or escaped UUID: {row.source}")
            overrides[row.target.relative_to(paths.overrides_dir).as_posix()] = row.source.read_text(encoding="utf-8")
    return _PlannedResources(ResourceCatalog(), overrides)


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
    record["settings"].setdefault("platform", profile.platform)
    record["settings"].setdefault("user_home", str(profile.user_home))
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
        ctx = AppContext(paths, config, _planned_resources(paths, entries))
        migration_preview = getattr(backend, "preview_migration", None)
        preview = getattr(backend, "preview", None)
        if callable(migration_preview):
            external = tuple(migration_preview(ctx, legacy_root=legacy_root, vault=vault, roots=roots, desired=config["integrations"], profile=profile))
        elif not callable(preview):
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
            "external":[{"kind":row.kind,"key":row.key,"before":encode_bytes(row.before),"after":encode_bytes(row.after), **({"has_uninstall_baseline":True,"uninstall_before":encode_bytes(row.uninstall_before)} if getattr(row,"has_uninstall_baseline",False) else {})} for row in plan.external],
            "conflicts":list(plan.conflicts)}


# Apply is deliberately separate from readonly planning.
def _regular_hash(path: Path) -> str | None:
    import stat
    safe_path(path)
    if not path.exists():
        return None
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise OwnershipConflict(f"Unsafe migration file: {path}")
    return digest(path)


def _plan_id(plan: MigrationPlan) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(plan_document(plan), sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _check_source(entry: MigrationEntry, expected: str | None) -> None:
    if _regular_hash(entry.source) != expected:
        raise OwnershipConflict(f"Migration source changed: {entry.source}")


def _validate_targets(plan: MigrationPlan, ctx: AppContext) -> None:
    actions = {"copy-state", "preserve-override", "retain-user", "rebuild-cache", "merge-config", "remove-owned", "replace-registration"}
    for row in plan.entries:
        if row.action not in actions or row.ownership == "conflict":
            raise OwnershipConflict(f"Invalid migration entry: {row.source}")
        safe_path(row.source)
        if row.target is not None:
            safe_path(row.target)
        root = ctx.paths.state_dir if row.action == "copy-state" else ctx.paths.overrides_dir
        if row.action in ("copy-state", "preserve-override"):
            if row.target is None or not row.target.is_relative_to(root):
                raise OwnershipConflict(f"Migration target exceeds UUID boundary: {row.target}")
            current = _regular_hash(row.target)
            if current is not None and current != row.sha256:
                raise OwnershipConflict(f"Migration target changed: {row.target}")
        if row.action == "remove-owned" and row.source.is_relative_to(ctx.paths.vault_root):
            relative = row.source.relative_to(ctx.paths.vault_root)
            if len(relative.parts) > 1 and relative.parts[0] not in (".beyin", ".claude"):
                raise OwnershipConflict(f"Migration cleanup exceeds legacy boundary: {row.source}")


def _cleanup_manifest_proof(entry: MigrationEntry) -> bool:
    from .ownership import read_manifest, prove_ownership
    for parent in entry.source.parents:
        candidate = parent / "install-manifest.json"
        if candidate.exists():
            _regular_hash(candidate)
            manifest = read_manifest(candidate)
            if prove_ownership(entry.source, manifest):
                return True
    return False


def _inno_value(document: bytes, name: str):
    values = json.loads(document).get("values", {})
    row = values.get(name)
    return row.get("data", row.get("value")) if isinstance(row, dict) else row


def _verify_inno_cleanup(plan: MigrationPlan, ctx: AppContext, backend, entry: MigrationEntry) -> None:
    from .legacy import INNO_KEY
    if entry.source.suffix.casefold() not in (".exe", ".dat"):
        raise OwnershipConflict("Only exact Inno exe/dat artifacts may be removed")
    changes = [row for row in plan.external if row.kind == "registry" and row.key == INNO_KEY]
    if len(changes) != 1 or changes[0].before is None or changes[0].after is None:
        raise OwnershipConflict("Old uninstaller cleanup requires exact registry replacement")
    change = changes[0]
    old_command = _inno_value(change.before, "UninstallString")
    old = Path(old_command.strip().strip('"')) if isinstance(old_command, str) else None
    location = _inno_value(change.before, "InstallLocation")
    if old is None or not old.is_absolute() or entry.source.with_suffix(".exe") != old or Path(location or "") != old.parent:
        raise OwnershipConflict("Old uninstaller registry proof changed")
    current = backend.read("registry", INNO_KEY)
    if current != change.after:
        raise OwnershipConflict("New uninstall registration is not active")
    command = _inno_value(current, "UninstallString")
    if not isinstance(command, str):
        raise OwnershipConflict("New uninstall registration has no command")
    # Windows command lines quote executable paths; arguments may follow.
    executable = command.split('"', 2)[1] if command.startswith('"') and command.count('"') >= 2 else command.split(" ", 1)[0]
    launcher = safe_path(Path(executable))
    if not launcher.is_relative_to(ctx.paths.app_root) or not launcher.is_file():
        raise OwnershipConflict("New uninstall command does not point to AppRoot")


def _completed_receipt(plan: MigrationPlan, ctx: AppContext, previous, backend):
    from .ownership import prove_ownership, decode_bytes
    path = ctx.paths.state_dir / "migration-receipts" / (_plan_id(plan) + ".json")
    if not path.exists():
        return None
    _regular_hash(path)
    if not prove_ownership(path, previous):
        raise OwnershipConflict("Migration receipt is not hash-owned")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("plan_id") != _plan_id(plan) or document.get("vault_id") != plan.vault_id:
        raise OwnershipConflict("Migration receipt identity changed")
    journal = ctx.paths.data_root / "backups" / document["tx_id"] / "journal.json"
    _regular_hash(journal)
    transaction = json.loads(journal.read_text(encoding="utf-8"))
    if transaction.get("status") != "committed" or transaction.get("tx_id") != document["tx_id"]:
        raise OwnershipConflict("Migration receipt has no committed journal")
    expected_entries = [{"source":str(row.source), "target":str(row.target) if row.target else None,
                         "action":row.action, "sha256":row.sha256, "ownership":row.ownership} for row in plan.entries]
    completed = document.get("completed", [])
    if [row.get("entry") for row in completed] != expected_entries:
        raise OwnershipConflict("Migration receipt does not cover the exact plan")
    for row, outcome in zip(plan.entries, completed):
        _check_source(row, outcome["source_after"])
        if row.action in ("copy-state", "preserve-override") and _regular_hash(row.target) != row.sha256:
            raise OwnershipConflict(f"Completed migration target changed: {row.target}")
    for row in document.get("external", []):
        if backend.read(row["kind"], row["key"]) != decode_bytes(row["after"]):
            raise OwnershipConflict("Completed migration external record changed")
    return document


def _verify_outputs(files, copied, external, backend) -> None:
    for item in (*files, *copied):
        if _regular_hash(item.path) != item.sha256:
            raise OwnershipConflict(f"Migration output changed: {item.path}")
    for change in external:
        if change.kind in ("file", "mcp", "shortcut"):
            _regular_hash(Path(change.key))
        if backend.read(change.kind, change.key) != change.after:
            raise OwnershipConflict(f"Migration external changed before commit: {change.kind}:{change.key}")


def apply_migration(plan: MigrationPlan, *, roots: Roots, package: Path,
                    backend: IntegrationBackend, fault: Callable[[str], None] | None = None, shell=None) -> OperationResult:
    """Activate a verified distribution and migrate approved hashes with WAL rollback."""
    from respectedbrain.vault.registry import VaultRegistry, MACHINE_FIELDS
    from . import payload
    from .operations import activate_package, validate_manifest_roots
    from .ownership import OwnedFile, OwnershipManifest, read_manifest, manifest_document, baseline_change
    from .transaction import Transaction, OperationResult, recover_transactions
    if plan.conflicts:
        return OperationResult(False, "", plan.conflicts)
    tx = None
    try:
        identity = _uuid(plan.vault_id)
        if identity != plan.vault_id:
            raise OwnershipConflict("Invalid planned vault UUID")
        config = copy.deepcopy(plan.config)
        record = config["vaults"][identity]
        vault = safe_path(Path(record["path"]))
        for path in (roots.app_root, roots.data_root, vault):
            safe_path(path)
        if roots.app_root.is_relative_to(vault) or roots.data_root.is_relative_to(vault) or vault.is_relative_to(roots.app_root) or vault.is_relative_to(roots.data_root) or roots.app_root.is_relative_to(roots.data_root) or roots.data_root.is_relative_to(roots.app_root):
            raise OwnershipConflict("Application, data and vault roots must be separate")
        ctx = AppContext(AppPaths(roots.app_root, roots.data_root, vault, identity), config, ResourceCatalog())
        _validate_targets(plan, ctx)
        _regular_hash(package / "distribution.json")
        document = payload.validate_package(package)
        for name in (*document["files"], "distribution.json"):
            _regular_hash(package / name)
            _regular_hash(roots.app_root / name)
        manifest_path = roots.data_root / "install-manifest.json"
        _regular_hash(manifest_path)
        previous = read_manifest(manifest_path) if manifest_path.exists() else OwnershipManifest(3, (), ())
        validate_manifest_roots(ctx, previous)
        if any(result.conflicts for result in recover_transactions(roots.data_root, backend)):
            raise OwnershipConflict("Unfinished rollback conflict")
        # All vault writers must be quiet while the shared application is replaced.
        with Transaction(roots.data_root, backend, fault=fault) as tx:
            if shell is not None:
                shell.prepare(tx)
            tx.checkpoint("lock")
            completed = _completed_receipt(plan, ctx, previous, backend)
            if completed is not None:
                # This is an exact completed replay, not a new migration or hash bypass.
                tx.commit()
                return OperationResult(True, completed["tx_id"], ())
            for row in plan.entries:
                _check_source(row, row.sha256)
                if row.action == "remove-owned" and row.ownership not in ("manifest-match", "registry-match"):
                    raise OwnershipConflict(f"Cleanup lacks ownership: {row.source}")
                if row.action == "remove-owned" and row.ownership == "manifest-match" and not _cleanup_manifest_proof(row):
                    raise OwnershipConflict(f"Cleanup manifest proof changed: {row.source}")
            for change in plan.external:
                if change.kind in ("file", "mcp", "shortcut"):
                    _regular_hash(Path(change.key))
                if backend.read(change.kind, change.key) != change.before:
                    raise OwnershipConflict(f"External record changed: {change.kind}:{change.key}")
            _validate_targets(plan, ctx)
            for row in plan.entries:
                if row.action in ("copy-state", "preserve-override", "merge-config", "remove-owned"):
                    tx.backup(row.source)
                    if row.target is not None:
                        tx.backup(row.target)
            for item in previous.files:
                _regular_hash(item.path)
                tx.backup(item.path)
            tx.backup(manifest_path)
            tx.checkpoint("backup")
            staged = tx.directory / "stage"
            for name in (*document["files"], "distribution.json"):
                tx.replace(package / name, staged / name)
            payload.validate_package(staged)
            tx.checkpoint("stage")
            document, files = activate_package(roots, staged, tx, previous)
            tx.checkpoint("activate")
            copied = []
            for row in plan.entries:
                if row.action in ("copy-state", "preserve-override"):
                    _check_source(row, row.sha256)
                    payload_bytes = row.source.read_bytes()
                    if _regular_hash(row.target) is None:
                        tx.write(row.target, payload_bytes)
                    if _regular_hash(row.target) != row.sha256:
                        raise OwnershipConflict(f"Copied migration hash mismatch: {row.target}")
                    copied.append(OwnedFile(row.target, row.sha256, "technical"))
            tx.checkpoint("state")
            marker_path = vault / ".respected.json"
            # Recheck sources at the write boundary; normalization cannot hide a race.
            for row in plan.entries:
                if row.source in (marker_path, roots.data_root / "config.json"):
                    _check_source(row, row.sha256)
            marker = json.loads(marker_path.read_text(encoding="utf-8")) if marker_path.exists() else {}
            machine = {key:marker.pop(key) for key in MACHINE_FIELDS if key in marker}
            marker.update(schema_version=3, vault_id=identity)
            record.setdefault("legacy_metadata", {}).update(machine)
            tx.write_json(roots.data_root / "config.json", config)
            tx.write_json(marker_path, marker)
            assigned = VaultRegistry(ConfigStore(roots.data_root)).register(vault, writer=tx.write_json)
            if assigned != identity:
                raise OwnershipConflict("Registered migration UUID changed")
            config = ConfigStore(roots.data_root).read()
            ctx = AppContext(ctx.paths, config, ctx.resources)
            from .common import ensure_linux_launcher, installed_profile
            settings = config["vaults"][identity].get("settings", {})
            launchers = ensure_linux_launcher(ctx, installed_profile(roots, settings), tx, previous)
            files = (*files, *launchers)
            tx.checkpoint("config")
            owned_external = {(row.kind,row.key):row for row in previous.external}
            for change in plan.external:
                if change.kind in ("file", "mcp", "shortcut"):
                    _regular_hash(Path(change.key))
                tx.apply_external(change)
                if change.before != change.after:
                    prior = owned_external.get((change.kind, change.key))
                    baseline = baseline_change(change)
                    owned_external[(change.kind,change.key)] = ExternalChange(change.kind, change.key, baseline.before if getattr(change,"has_uninstall_baseline",False) else prior.before if prior else change.before, change.after)
            if shell is not None:
                registration = shell.registration
                already_applied = any((row.kind,row.key,row.after) == (registration.kind,registration.key,registration.after) for row in plan.external)
                if not already_applied or backend.read(registration.kind, registration.key) != registration.after:
                    tx.apply_external(registration)
                owned_external[(registration.kind, registration.key)] = shell.owned_registration(previous)
            tx.checkpoint("integrations")
            tx.checkpoint("health")
            for name in (*document["files"], "distribution.json"):
                _regular_hash(roots.app_root / name)
            payload.validate_package(roots.app_root)
            payload.validate_installed_health(roots.app_root, document, roots.data_root)
            tx.checkpoint("cleanup")
            for row in plan.entries:
                if row.action in ("copy-state", "preserve-override"):
                    _check_source(row, row.sha256)
            _verify_outputs(files, copied, plan.external, backend)
            for row in plan.entries:
                if row.action == "remove-owned":
                    _check_source(row, row.sha256)
                    if row.ownership == "manifest-match" and not _cleanup_manifest_proof(row):
                        raise OwnershipConflict(f"Cleanup manifest changed: {row.source}")
                    if row.ownership == "registry-match":
                        _verify_inno_cleanup(plan, ctx, backend, row)
                    tx.remove(row.source, expected_hash=row.sha256)
            receipt_path = ctx.paths.state_dir / "migration-receipts" / (_plan_id(plan) + ".json")
            receipt = {"schema_version":3,"plan_id":_plan_id(plan),"vault_id":identity,"tx_id":tx.tx_id,
                       "completed":[{"entry":{"source":str(row.source),"target":str(row.target) if row.target else None,"action":row.action,"sha256":row.sha256,"ownership":row.ownership},
                                     "source_after":_regular_hash(row.source)} for row in plan.entries],
                       "external":plan_document(plan)["external"]}
            tx.write_json(receipt_path, receipt)
            technical = {row.path:row for row in previous.files if row.role == "technical" and row.path.exists()}
            technical.update({row.path:row for row in copied})
            for path in (roots.data_root / "config.json", receipt_path):
                technical[path] = OwnedFile(path, digest(path), "technical")
            uninstallers = shell.files if shell is not None else tuple(item for item in previous.files if item.role == "uninstaller")
            owned = OwnershipManifest(3, tuple(files) + uninstallers + tuple(technical.values()), tuple(owned_external.values()))
            validate_manifest_roots(ctx, owned)
            for item in owned.files:
                _regular_hash(item.path)
            _verify_outputs(files, copied, plan.external, backend)
            tx.write_json(manifest_path, manifest_document(owned))
            for row in plan.entries:
                if row.action in ("copy-state", "preserve-override"):
                    _check_source(row, row.sha256)
            return tx.commit()
    except (FoundationError, OSError, ValueError, KeyError, TypeError) as error:
        return OperationResult(False, tx.tx_id if tx else "", (str(error), *(tx.result.conflicts if tx else ())))
