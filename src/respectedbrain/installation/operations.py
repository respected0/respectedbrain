"""Common ownership and integration handling for maintenance operations."""
from dataclasses import replace
from pathlib import Path
import stat
from respectedbrain.core.config import ConfigStore
from respectedbrain.core.errors import OwnershipConflict
from respectedbrain.core.paths import Roots
from respectedbrain.integrations.backend import ExternalChange
from .common import installed_profile, linux_launcher_path
from .ownership import safe_path, OwnedFile, OwnershipManifest, digest, prove_ownership


def validate_manifest_roots(ctx, manifest):
    for item in manifest.files:
        safe_path(item.path)
        if item.role == "launcher":
            settings = ctx.config["vaults"][ctx.paths.vault_id].get("settings", {})
            profile = installed_profile(Roots(ctx.paths.app_root, ctx.paths.data_root, ctx.paths.vault_root), settings)
            if profile.platform != "posix" or item.path != linux_launcher_path(ctx, profile):
                raise OwnershipConflict(f"Ownership manifest exceeds launcher boundary: {item.path}")
            continue
        root = ctx.paths.app_root if item.role in ("application", "uninstaller") else ctx.paths.data_root
        if item.role not in ("application", "uninstaller", "technical") or not item.path.is_relative_to(root) or item.path.is_relative_to(ctx.paths.vault_root):
            raise OwnershipConflict(f"Ownership manifest exceeds application/data boundary: {item.path}")


def activate_package(roots, package, tx, previous, *, require_provenance=None, repair_owned=False):
    from .payload import package_members, validate_package
    document = validate_package(package, require_provenance=require_provenance)
    members = package_members(package, document)
    existing = {item.path: item for item in previous.files if item.role == "application"}
    for name in members:
        target = roots.app_root / name
        item = existing.get(target)
        source = safe_path(package / name)
        expected = digest(source)
        if item is not None:
            if target.exists() and not prove_ownership(target, previous) and not repair_owned:
                raise OwnershipConflict(f"Application file changed or unowned: {target}")
        elif target.exists() and digest(safe_path(target)) != expected:
            raise OwnershipConflict(f"Application file changed or unowned: {target}")
    for name in members:
        tx.replace(safe_path(package / name), roots.app_root / name)
    next_paths = {roots.app_root / name for name in members}
    for target, item in existing.items():
        if target not in next_paths and target.exists():
            tx.remove(target, expected_hash=item.sha256)
    return document, tuple(OwnedFile(path, digest(path), "application", stat.S_IMODE(path.stat().st_mode)) for path in sorted(next_paths))


def plan_connections(ctx, backend, previous):
    config = ConfigStore(ctx.paths.data_root).read()
    fresh = replace(ctx, config=config)
    desired = config["integrations"]
    disabled = []
    retained = []
    flag_by_kind = {"file": "global", "mcp": "mcp", "task": "schedule", "shortcut": "shortcut"}
    settings = config["vaults"][ctx.paths.vault_id].get("settings", {})
    home = Path(settings.get("user_home", str(Path.home())))
    name = "respected-morning-briefing-" + ctx.paths.vault_id
    schedule_paths = {str(home / ".config/systemd/user" / (name + suffix)) for suffix in (".service", ".timer")}
    schedule_paths.add(str(home / "Library/LaunchAgents" / (name + ".plist")))
    for prior in previous.external:
        # Local vault hooks remain enabled independently of optional global hooks.
        if prior.kind == "file" and Path(prior.key).is_relative_to(ctx.paths.vault_root):
            retained.append(prior)
            continue
        flag = "schedule" if prior.kind == "file" and prior.key in schedule_paths else flag_by_kind.get(prior.kind)
        if flag is not None and not desired.get(flag, False):
            current = backend.read(prior.kind, prior.key)
            if current == prior.before:
                continue
            if current != prior.after:
                raise OwnershipConflict(f"User changed integration: {prior.kind}:{prior.key}")
            disabled.append(ExternalChange(prior.kind, prior.key, current, prior.before))
        else:
            retained.append(prior)
    if not any(desired.get(key, False) for key in ("global", "mcp", "schedule", "shortcut")):
        return tuple(disabled), tuple(retained)
    from respectedbrain.integrations.rendering import plan_integrations
    roots = Roots(ctx.paths.app_root, ctx.paths.data_root, ctx.paths.vault_root)
    settings = config["vaults"][ctx.paths.vault_id].get("settings", {})
    changes = plan_integrations(fresh, installed_profile(roots, settings), desired, backend)
    owned = {(change.kind, change.key): change for change in retained}
    for change in changes:
        prior = owned.get((change.kind, change.key))
        if prior is not None and change.before != prior.after:
            raise OwnershipConflict(f"User changed integration: {change.kind}:{change.key}")
        owned[(change.kind, change.key)] = ExternalChange(change.kind, change.key, prior.before if prior else change.before, change.after)
    return (*disabled, *changes), tuple(owned.values())


def operation_manifest(ctx, files, external, *, previous=None):
    config_path = ctx.paths.data_root / "config.json"
    owned = {item.path: item for item in previous.files if item.role == "technical"} if previous is not None else {}
    owned.update({item.path: item for item in files})
    owned[config_path] = OwnedFile(config_path, digest(config_path), "technical")
    return OwnershipManifest(3, tuple(owned.values()), tuple(external))
