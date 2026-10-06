"""The shared installer creates notes once; subsequent operations preserve them."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import stat
from typing import Mapping

from respectedbrain.core.config import ConfigStore
from respectedbrain.core.errors import FoundationError, OwnershipConflict
from respectedbrain.core.paths import Roots
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.vault.registry import VaultRegistry
from .common import installed_profile, installation_context, ensure_linux_launcher
from .ownership import OwnedFile, OwnershipManifest, digest, manifest_document, read_manifest, safe_path
from .transaction import Transaction, OperationResult, recover_transactions
from . import payload


def setup(roots: Roots, vault: Path, *, profile: Mapping[str, str], desired: Mapping[str, bool],
          backend, package: Path | None = None, shell=None) -> OperationResult:
    tx = None
    try:
        safe_path(vault)
        if vault.is_relative_to(roots.app_root) or roots.app_root.is_relative_to(vault) or vault.is_relative_to(roots.data_root) or roots.data_root.is_relative_to(vault):
            raise OwnershipConflict("Vault, program and data roots must be separate")
        store = ConfigStore(roots.data_root)
        config = store.read()
        registered = next((identity for identity, entry in config["vaults"].items() if Path(entry["path"]).resolve() == vault.resolve()), None)
        if registered is None and vault.exists() and any(vault.iterdir()):
            return OperationResult(False, "", ("Nonempty target is not registered; use migration or vault register",))
        if registered is not None:
            VaultRegistry(store).select(vault=vault, vault_id=None, env={})
        source = package if package is not None else roots.app_root
        document = payload.validate_package(source)
        recovery = recover_transactions(roots.data_root, backend)
        if any(item.conflicts for item in recovery):
            raise OwnershipConflict("Unfinished operation has rollback conflicts")
        with Transaction(roots.data_root, backend) as tx:
            if shell is not None:
                shell.prepare(tx)
            tx.checkpoint("backup")
            manifest_path = roots.data_root / "install-manifest.json"
            previous = read_manifest(manifest_path) if manifest_path.is_file() else OwnershipManifest(3, (), ())
            if previous.files:
                from .operations import validate_manifest_roots
                prior_identity = registered or config["active_vault_id"]
                if prior_identity is None:
                    raise OwnershipConflict("Existing ownership requires a registered vault identity")
                validate_manifest_roots(installation_context(roots, vault, prior_identity, config), previous)
            tx.checkpoint("stage")
            if package is not None and package != roots.app_root:
                from .operations import activate_package
                document, _ = activate_package(roots, package, tx, previous)
            tx.checkpoint("activate")
            if registered is None:
                if vault.exists() and any(vault.iterdir()):
                    raise OwnershipConflict("Vault changed during installation")
                values = {"TODAY": date.today().isoformat(), "VAULT_PATH": str(vault), "OS_NAME": vault.name,
                          "USER_NAME": Path.home().name, "USER_BIO": "", "COMPANION": "Companion", **profile}
                with ResourceCatalog().materialize("vault-template") as stage:
                    for file in stage.rglob("*"):
                        if file.is_file() and (file.suffix.lower() in (".md", ".json", ".mdc", ".txt", ".yaml", ".yml") or file.name.startswith(".")):
                            text = file.read_text(encoding="utf-8")
                            for key, value in values.items():
                                text = text.replace("{{" + key + "}}", str(value))
                            file.write_text(text, encoding="utf-8")
                    tx.replace(stage, vault)
            identity = VaultRegistry(store).register(vault, writer=tx.write_json)
            tx.checkpoint("config")
            resolved_profile = installed_profile(roots, profile)
            def edit(value):
                value["integrations"].update({key: bool(desired[key]) for key in ("global", "mcp", "schedule", "shortcut") if key in desired})
                value["vaults"][identity]["settings"].update({key: val for key, val in profile.items() if key in ("OS_NAME", "USER_NAME", "USER_BIO", "COMPANION", "platform", "user_home")})
                value["vaults"][identity]["settings"].setdefault("platform", resolved_profile.platform)
                value["vaults"][identity]["settings"].setdefault("user_home", str(resolved_profile.user_home))
                for key in ("summary_provider", "provider_priority", "provider_fallback"):
                    if key in profile:
                        value["preferences"][key] = profile[key]
            config = store.update(edit, writer=tx.write_json)
            ctx = installation_context(roots, vault, identity, config)
            profile_object = installed_profile(roots, profile)
            launchers = ensure_linux_launcher(ctx, profile_object, tx, previous)
            if registered is None:
                from respectedbrain.integrations.rendering import render_project_integrations
                for name, content in render_project_integrations(ctx, profile_object).items():
                    tx.write(vault / name, content)
            from .operations import plan_connections, operation_manifest
            changes, external = plan_connections(ctx, backend, previous)
            for change in changes:
                tx.apply_external(change)
            if shell is not None:
                tx.apply_external(shell.registration)
                external = tuple(item for item in external if (item.kind, item.key) != (shell.registration.kind, shell.registration.key)) + (shell.owned_registration(previous),)
            tx.checkpoint("integrations")
            owned = tuple(OwnedFile(roots.app_root / name, digest(roots.app_root / name), "application", stat.S_IMODE((roots.app_root / name).stat().st_mode)) for name in (*document["files"], "distribution.json"))
            owned += (OwnedFile(store.path, digest(store.path), "technical"),) + launchers
            owned += shell.files if shell is not None else tuple(item for item in previous.files if item.role == "uninstaller")
            tx.write_json(manifest_path, manifest_document(operation_manifest(ctx, owned, external, previous=previous)))
            tx.checkpoint("health")
            payload.validate_package(roots.app_root)
            payload.validate_installed_health(roots.app_root, document, roots.data_root)
            tx.checkpoint("cleanup")
            return tx.commit()
    except (FoundationError, OSError, ValueError) as error:
        conflicts = tx.result.conflicts if tx is not None else ()
        return OperationResult(False, tx.tx_id if tx else "", (str(error), *conflicts))
