"""Verified package activation with rollback; user notes are outside the payload."""
from respectedbrain.core.config import ConfigStore
from respectedbrain.core.errors import FoundationError
from respectedbrain.core.paths import Roots
from .ownership import read_manifest, manifest_document
from .operations import validate_manifest_roots, activate_package, plan_connections, operation_manifest
from .transaction import Transaction, OperationResult, recover_transactions
from . import payload
from .common import ensure_linux_launcher, installed_profile


def update(ctx, *, package, backend, shell=None) -> OperationResult:
    tx = None
    try:
        payload.validate_package(package)
        if any(result.conflicts for result in recover_transactions(ctx.paths.data_root, backend)):
            return OperationResult(False, "", ("Unfinished rollback conflict",))
        with Transaction(ctx.paths.data_root, backend) as tx:
            previous = read_manifest(ctx.paths.data_root / "install-manifest.json")
            validate_manifest_roots(ctx, previous)
            if shell is not None:
                shell.prepare(tx)
            tx.checkpoint("backup")
            for item in previous.files:
                if item.path.exists():
                    tx.backup(item.path)
            tx.checkpoint("stage")
            roots = Roots(ctx.paths.app_root, ctx.paths.data_root, ctx.paths.vault_root)
            document, files = activate_package(roots, package, tx, previous)
            tx.checkpoint("activate")
            # Read the latest preferences under the config lock; never copy defaults over them.
            ConfigStore(ctx.paths.data_root).update(lambda value: None, writer=tx.write_json)
            tx.checkpoint("config")
            settings = ctx.config["vaults"][ctx.paths.vault_id].get("settings", {})
            launchers = ensure_linux_launcher(ctx, installed_profile(roots, settings), tx, previous)
            changes, external = plan_connections(ctx, backend, previous)
            for change in changes:
                tx.apply_external(change)
            if shell is not None:
                tx.apply_external(shell.registration)
                external = tuple(item for item in external if (item.kind, item.key) != (shell.registration.kind, shell.registration.key)) + (shell.owned_registration(previous),)
            tx.checkpoint("integrations")
            uninstallers = shell.files if shell is not None else tuple(item for item in previous.files if item.role == "uninstaller")
            tx.write_json(ctx.paths.data_root / "install-manifest.json", manifest_document(operation_manifest(ctx, (*files, *uninstallers, *launchers), external, previous=previous)))
            tx.checkpoint("health")
            payload.validate_package(ctx.paths.app_root)
            payload.validate_installed_health(ctx.paths.app_root, document, ctx.paths.data_root)
            tx.checkpoint("cleanup")
            return tx.commit()
    except (FoundationError, OSError, ValueError) as error:
        return OperationResult(False, tx.tx_id if tx else "", (str(error), *(tx.result.conflicts if tx else ())))
