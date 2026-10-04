"""Read legacy layouts without creating, modifying, or following user paths."""
from __future__ import annotations
from dataclasses import dataclass
import copy
import json
import os
from pathlib import Path
import stat
from typing import Any

from respectedbrain.core.errors import FoundationError, OwnershipConflict
from respectedbrain.core.paths import Roots
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.integrations.backend import IntegrationBackend
from .ownership import digest, prove_ownership, read_manifest, safe_path
from .migration import MigrationEntry

INNO_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{870D0E4C-87A0-4A3C-9A82-F8E3C3A19C1D}_is1"
PREFERENCE_KEYS = ("summary_provider", "provider_priority", "provider_fallback")
FLAGS = ("global", "mcp", "schedule", "shortcut")

@dataclass(frozen=True)
class LegacyInventory:
    entries: tuple[MigrationEntry, ...]
    preferences: dict[str, Any]
    desired: dict[str, bool]
    conflicts: tuple[str, ...]


def _read_object(path: Path) -> dict[str, Any]:
    document = json.loads(safe_path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"JSON object required: {path}")
    return document


def _valid_preferences(document: dict[str, Any]) -> dict[str, Any]:
    source = document.get("preferences", document)
    if not isinstance(source, dict):
        return {}
    result = copy.deepcopy(source)
    providers = {"auto", "claude", "codex", "gemini", "antigravity", "cursor"}
    if "summary_provider" in result and (not isinstance(result["summary_provider"], str) or result["summary_provider"] not in providers):
        result.pop("summary_provider")
    if "provider_priority" in result:
        priority = result["provider_priority"]
        if not isinstance(priority, list) or not priority or any(not isinstance(p, str) or p not in providers - {"auto"} for p in priority):
            result.pop("provider_priority")
    if "provider_fallback" in result and not isinstance(result["provider_fallback"], bool):
        result.pop("provider_fallback")
    for key in ("schema_version", "vault_path", "runtime_path", "runtime_dir", "integrations", "vaults", "active_vault_id"):
        result.pop(key, None)
    return result


def _walk(root: Path, conflicts: list[str]):
    if not root.exists() and not root.is_symlink():
        return
    try:
        safe_path(root)
        metadata = root.lstat()
        if not stat.S_ISDIR(metadata.st_mode):
            raise OwnershipConflict(f"Legacy root is not a directory: {root}")
    except (OSError, FoundationError) as error:
        conflicts.append(str(error))
        return
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        parent = Path(current)
        for name in list(directory_names):
            child = parent / name
            try:
                safe_path(child)
            except (OSError, FoundationError) as error:
                conflicts.append(str(error))
                directory_names.remove(name)
        for name in sorted(file_names):
            path = parent / name
            try:
                safe_path(path)
                metadata = path.lstat()
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise OwnershipConflict(f"Unsafe legacy source: {path}")
                yield path
            except (OSError, FoundationError) as error:
                conflicts.append(str(error))
                yield MigrationEntry(path, None, "retain-user", None, "conflict")


def _within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _registry_uninstaller(backend: IntegrationBackend, legacy_root: Path, vault: Path, conflicts: list[str]) -> Path | None:
    try:
        payload = backend.read("registry", INNO_KEY)
        if payload is None:
            return None
        document = json.loads(payload)
        values = document.get("values", document)
        def value(key):
            row = values.get(key)
            return row.get("value", row.get("data")) if isinstance(row, dict) else row
        location, uninstall = value("InstallLocation"), value("UninstallString")
        if not isinstance(location, str) or not isinstance(uninstall, str):
            return None
        executable = uninstall.strip().strip('"')
        # Arguments or ambiguous commands are not exact executable ownership.
        if not executable.casefold().endswith(".exe"):
            return None
        install = Path(location)
        candidate = Path(executable)
        if install not in (legacy_root, vault) or not candidate.is_absolute():
            return None
        safe_path(candidate)
        if not candidate.is_file() or not candidate.name.casefold().startswith("unins"):
            return None
        return candidate
    except (OSError, ValueError, TypeError, FoundationError) as error:
        conflicts.append(f"legacy-registry:{error}")
        return None


def inventory_legacy(legacy_root: Path, vault: Path, *, roots: Roots, backend: IntegrationBackend) -> LegacyInventory:
    legacy_root, vault = Path(legacy_root), Path(vault)
    conflicts: list[str] = []
    entries: list[MigrationEntry] = []
    preferences: dict[str, Any] = {}
    desired: dict[str, bool] = {}
    engines = list(dict.fromkeys((legacy_root, legacy_root / "runtime", vault / ".beyin")))
    state_roots = list(dict.fromkeys([p / name for p in engines for name in ("state", ".state", "engine/.state")]
        + [vault / ".claude/scripts/.state", vault / ".state", roots.data_root / "state", roots.data_root / ".state"]))
    cache_roots = [p / "cache" for p in engines] + [roots.data_root / "cache"]
    pending = roots.data_root / "vaults" / "_pending"
    catalog = ResourceCatalog()
    manifests = []
    for source in (legacy_root, legacy_root / "runtime", vault, vault / ".beyin", roots.data_root):
        path = source / "install-manifest.json"
        if path.exists() or path.is_symlink():
            try:
                manifests.append(read_manifest(path))
            except (OSError, ValueError, KeyError, TypeError, FoundationError) as error:
                conflicts.append(f"legacy-manifest:{path}:{error}")
    config_sources = list(dict.fromkeys([roots.data_root / "config.json"] + [p / "config.json" for p in engines]))
    uninstaller = _registry_uninstaller(backend, legacy_root, vault, conflicts)
    seen = set()
    scan_roots = list(dict.fromkeys([legacy_root, vault / ".beyin", vault / ".claude/scripts", vault / ".state", roots.data_root / "state", roots.data_root / ".state", roots.data_root / "cache"]))
    files = []
    for path in config_sources:
        if path.exists() or path.is_symlink():
            try:
                if _read_object(path).get("schema_version") != 3:
                    files.append(path)
            except (OSError, ValueError, FoundationError) as error:
                conflicts.append(f"legacy-config:{path}:{error}")
    for root in scan_roots:
        files.extend(_walk(root, conflicts))
    # Root-level custom code and installer residue are inventoried without scanning notes.
    if vault.is_dir():
        try:
            safe_path(vault)
            for path in sorted(vault.iterdir()):
                if path.is_file() or path.is_symlink():
                    files.append(path)
        except (OSError, FoundationError) as error:
            conflicts.append(str(error))
    for source in files:
        if isinstance(source, MigrationEntry):
            entries.append(source)
            continue
        if source in seen:
            continue
        seen.add(source)
        try:
            safe_path(source)
            metadata = source.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise OwnershipConflict(f"Unsafe legacy source: {source}")
            sha = digest(source)
            owned = any(prove_ownership(source, manifest) for manifest in manifests)
            ownership = "manifest-match" if owned else "user"
            action, target = "retain-user", None
            state = next((root for root in state_roots if _within(source, root)), None)
            cache = next((root for root in cache_roots if _within(source, root)), None)
            if state:
                action, target = "copy-state", pending / "state" / source.relative_to(state)
            elif cache:
                action, target = "rebuild-cache", pending / "cache" / source.relative_to(cache)
            elif source in config_sources:
                action, target = "merge-config", roots.data_root / "config.json"
                document = _read_object(source)
                for key, value in _valid_preferences(document).items():
                    preferences.setdefault(key, value)
                integrations = document.get("integrations", {})
                if isinstance(integrations, dict):
                    for key, value in integrations.items():
                        if isinstance(value, bool):
                            desired.setdefault(key, value)
                        else:
                            conflicts.append(f"invalid-integration:{source}:{key}")
            else:
                engine = next((root for root in reversed(engines) if _within(source, root)), None)
                if engine:
                    relative = source.relative_to(engine)
                    resource = "instructions/default.md" if relative.as_posix() == "instructions.md" else relative.as_posix() if relative.parts and relative.parts[0] == "skills" else None
                    if resource:
                        try:
                            default = catalog.read_text(resource).encode("utf-8")
                        except (FileNotFoundError, ValueError):
                            default = None
                        if default != source.read_bytes():
                            action, target = "preserve-override", pending / "overrides" / resource
                if action == "retain-user" and source.name.casefold().startswith("unins"):
                    if uninstaller is not None and source.suffix.casefold() in (".exe", ".dat") and source.with_suffix(".exe") == uninstaller:
                        action, ownership = "remove-owned", "registry-match"
                    else:
                        ownership = "user"  # Inno artifacts require exact registration too.
                elif action == "retain-user" and owned:
                    action = "remove-owned"
            entries.append(MigrationEntry(source, target, action, sha, ownership))
        except (OSError, ValueError, KeyError, TypeError, FoundationError) as error:
            conflicts.append(f"legacy-source:{source}:{error}")
            entries.append(MigrationEntry(source, None, "retain-user", None, "conflict"))
    # Report invalid explicit legacy override; it never influences new roots.
    override = os.environ.get("RESPECTED_RUNTIME_DIR")
    if override is not None:
        try:
            path = safe_path(Path(override))
            if not path.is_dir():
                raise OwnershipConflict("RESPECTED_RUNTIME_DIR does not exist")
        except (OSError, FoundationError) as error:
            conflicts.append(f"RESPECTED_RUNTIME_DIR:{error}")
    return LegacyInventory(tuple(entries), preferences, desired, tuple(dict.fromkeys(conflicts)))
