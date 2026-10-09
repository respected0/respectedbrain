"""Delete only unchanged owned files; purge proven technical records by default, never notes."""
from respectedbrain.core.errors import FoundationError
from respectedbrain.integrations.backend import ExternalChange
from .ownership import read_manifest, prove_ownership
from .operations import validate_manifest_roots
from .transaction import Transaction, OperationResult, recover_transactions


def uninstall(ctx, *, backend, purge_data=True, shell_active=False, shell_proof=None) -> OperationResult:
    tx = None
    try:
        # A running Inno executable cannot delete itself. Inno's intrinsic
        # finalization removes exactly its exe/dat after this service returns.
        shell_files = {ctx.paths.app_root / "uninstall" / name for name in ("unins000.exe", "unins000.dat")} if shell_active else set()
        if any(result.conflicts for result in recover_transactions(ctx.paths.data_root, backend)):
            return OperationResult(False, "", ("Unfinished rollback conflict",))
        conflicts = []
        manifest_path = ctx.paths.data_root / "install-manifest.json"
        manifest_before = manifest_path.read_bytes()
        with Transaction(ctx.paths.data_root, backend) as tx:
            manifest = read_manifest(manifest_path)
            validate_manifest_roots(ctx, manifest)
            dat_proven = bool(shell_active and shell_proof is not None and shell_proof())
            for item in manifest.files:
                if item.path in shell_files and not (dat_proven and item.path.name == "unins000.dat") and not prove_ownership(item.path, manifest):
                    raise FoundationError(f"Uninstaller changed: {item.path}")
            for change in reversed(manifest.external):
                current = backend.read(change.kind, change.key)
                if current == change.before:
                    continue
                if current != change.after:
                    conflicts.append(change.kind + ":" + change.key)
                    continue
                tx.apply_external(ExternalChange(change.kind, change.key, change.after, change.before))
            for item in manifest.files:
                if item.role == "technical" and not purge_data or not item.path.exists():
                    continue
                if not (dat_proven and item.path in shell_files and item.path.name == "unins000.dat") and not prove_ownership(item.path, manifest):
                    conflicts.append(str(item.path))
                    continue
                if item.role == "uninstaller" and item.path in shell_files:
                    continue
                tx.remove(item.path, expected_hash=item.sha256)
            result = tx.commit()
            if purge_data and not conflicts:
                if manifest_path.is_file() and manifest_path.read_bytes() == manifest_before:
                    manifest_path.unlink()
                else:
                    conflicts.append(str(manifest_path))
                    return OperationResult(False, result.tx_id, tuple(conflicts))
            # Unknown files and backup journals are deliberately retained.
            return OperationResult(not conflicts, result.tx_id, tuple(conflicts))
    except (FoundationError, OSError, ValueError) as error:
        return OperationResult(False, tx.tx_id if tx else "", (str(error), *(tx.result.conflicts if tx else ())))
