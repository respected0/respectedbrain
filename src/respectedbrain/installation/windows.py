"""Inno shell boundary: staged product bytes enter the common transactions."""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
from pathlib import Path

from respectedbrain import __version__
from respectedbrain.core.config import ConfigStore, atomic_write_json
from respectedbrain.core.errors import SelectionError, OwnershipConflict
from respectedbrain.integrations.backend import ExternalChange, canonical_json, INNO_UNINSTALL_KEY
from respectedbrain.vault.registry import build_context
from .common import installed_profile
from .ownership import OwnedFile, OwnershipManifest, safe_path, digest, encode_bytes, decode_bytes, read_manifest, prove_ownership, manifest_document
from .transaction import OperationResult, Transaction


def _fingerprint(path):
    metadata = safe_path(path).stat()
    return {name: getattr(metadata, name) for name in ("st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns")}


def prepare_uninstall(ctx, *, request):
    """Prove Inno bytes before Inno takes its exclusive .dat read/write lock."""
    import tempfile
    if not safe_path(request).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise OwnershipConflict("Uninstall proof must be in OS temp")
    manifest_path = ctx.paths.data_root / "install-manifest.json"
    manifest = read_manifest(manifest_path)
    records = []
    for name in ("unins000.exe", "unins000.dat"):
        path = safe_path(ctx.paths.app_root / "uninstall" / name)
        before = _fingerprint(path)
        if before["st_nlink"] != 1 or not prove_ownership(path, manifest) or before != _fingerprint(path):
            raise OwnershipConflict(f"Uninstaller changed before launch: {path}")
        records.append({"path": str(path), "sha256": digest(path), "identity": before})
    atomic_write_json(request, {"schema_version": 3, "app_root": str(ctx.paths.app_root), "data_root": str(ctx.paths.data_root), "vault": str(ctx.paths.vault_root), "manifest_sha256": digest(manifest_path), "files": records})
    return digest(request)


def validate_uninstall_proof(roots, *, request, expected_hash):
    import tempfile
    if not safe_path(request).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) or digest(request) != expected_hash:
        raise OwnershipConflict("Uninstall proof changed or is outside OS temp")
    proof = json.loads(request.read_text(encoding="utf-8"))
    if proof.get("schema_version") != 3 or any(proof.get(key) != str(value) for key, value in (("app_root", roots.app_root), ("data_root", roots.data_root), ("vault", roots.default_vault))):
        raise OwnershipConflict("Uninstall proof roots do not match")
    manifest_path = roots.data_root / "install-manifest.json"
    if digest(manifest_path) != proof["manifest_sha256"]:
        raise OwnershipConflict("Ownership manifest changed after uninstall preparation")
    manifest = read_manifest(manifest_path)
    expected = {roots.app_root / "uninstall" / name for name in ("unins000.exe", "unins000.dat")}
    if {Path(row["path"]) for row in proof["files"]} != expected:
        raise OwnershipConflict("Uninstall proof must cover exactly the Inno shell pair")
    for row in proof["files"]:
        path = Path(row["path"])
        if row["identity"]["st_nlink"] != 1 or _fingerprint(path) != row["identity"] or not any(item.path == path and item.role == "uninstaller" and item.sha256 == row["sha256"] for item in manifest.files):
            raise OwnershipConflict(f"Uninstaller identity changed after preparation: {path}")
        try:
            current = digest(path)
        except PermissionError:
            if path.name != "unins000.dat":
                raise
            # Inno validates the log and locks it before InitializeUninstall.
            # The unchanged identity and prelaunch SHA are required together.
        else:
            if current != row["sha256"]:
                raise OwnershipConflict(f"Uninstaller bytes changed after preparation: {path}")
    return True


def launch_uninstaller(ctx, *, request, purge_data=True):
    import subprocess
    proof_hash = prepare_uninstall(ctx, request=request)
    receipt = ctx.paths.data_root / "logs/uninstall-result.json"
    before = receipt.read_bytes() if receipt.exists() else None
    result = subprocess.run([str(ctx.paths.app_root / "uninstall/unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DATA=" + str(ctx.paths.data_root), "/VAULT=" + str(ctx.paths.vault_root), "/PROOF=" + str(request), "/PROOFHASH=" + proof_hash, "/PURGEDATA=" + ("1" if purge_data else "0")], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    after = receipt.read_bytes() if receipt.exists() else None
    if after is not None and after != before:
        document = json.loads(after)
        return OperationResult(document["success"] and result.returncode == 0, document["tx_id"], tuple(document["conflicts"]))
    return OperationResult(False, "", ("Inno produced no new uninstall receipt",))


def seal_shell(roots, *, backend):
    """Inno finalizes its log after ssPostInstall; seal only those known log bytes."""
    manifest_path = roots.data_root / "install-manifest.json"
    with Transaction(roots.data_root, backend) as tx:
        manifest = read_manifest(manifest_path)
        executable = safe_path(roots.app_root / "uninstall/unins000.exe")
        if not prove_ownership(executable, manifest):
            raise OwnershipConflict("Uninstaller executable changed before final sealing")
        registered = [row for row in manifest.external if row.kind == "registry"]
        if not registered or any(backend.read(row.kind, row.key) != row.after for row in registered):
            raise OwnershipConflict("Uninstaller registration changed before final sealing")
        files = []
        for item in manifest.files:
            if item.role == "uninstaller" and item.path == roots.app_root / "uninstall/unins000.dat":
                path = safe_path(item.path)
                if path.stat().st_nlink != 1 or not path.read_bytes().startswith(b"Inno Setup Uninstall Log"):
                    raise OwnershipConflict("Inno final log has an invalid header")
                item = OwnedFile(path, digest(path), "uninstaller")
            files.append(item)
        tx.write_json(manifest_path, manifest_document(replace(manifest, files=tuple(files))))
        return tx.commit()


def copy_helper(app_root, output):
    """Stage an executable helper from a fully provenance-verified install.

    The source ``app_root`` is validated with full release provenance
    (``require_provenance=True``) before any byte is copied, so a tampered or
    unsigned install can never seed a helper. The derived helper deliberately
    omits the attestation bundle: it is reproduced from the already-verified
    source, therefore its own ``validate_package`` call passes
    ``require_provenance=False`` and re-checks every copied hash against the
    verified source manifest. The helper is only a transient working copy in OS
    temp, never a new release artifact; a mismatch in any source file raises
    before the helper is written.
    """
    import json
    import shutil
    import tempfile
    from .payload import validate_package
    safe_path(output)
    if not output.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise OwnershipConflict("Executable helper must be in OS temp")
    document = validate_package(app_root, require_provenance=True)
    shell_names = {"uninstall/unins000.exe", "uninstall/unins000.dat"}
    files = {name: digest for name, digest in document["files"].items() if name not in shell_names}
    for name in files:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe_path(app_root / name), safe_path(target))
    helper_manifest = {
        "schema_version": document["schema_version"],
        "version": document["version"],
        "platform": document["platform"],
        "launcher": document["launcher"],
        "files": files,
    }
    (output / "distribution.json").write_text(json.dumps(helper_manifest), encoding="utf-8")
    validate_package(output, require_provenance=False)


def prepare_shell(roots, *, request, package, registry_key=INNO_UNINSTALL_KEY, require_provenance=True, backend):
    from . import payload
    # The Inno shell always supplies --package and the real Setup gate must stay
    # fail-closed: release provenance is verified before any AppRoot/DataRoot/
    # VaultRoot write. ``package`` is mandatory so even a direct Python caller
    # cannot silently skip the release gate; there is no shell-only path without
    # a staged, provenance-verified package.
    payload.validate_package(Path(package).resolve(), require_provenance=require_provenance)
    if roots.app_root.is_relative_to(roots.default_vault) or roots.default_vault.is_relative_to(roots.app_root):
        raise OwnershipConflict("Program directory must be separate from notes")
    manifest_path = roots.data_root / "install-manifest.json"
    previous = read_manifest(manifest_path) if manifest_path.exists() else OwnershipManifest(3, (), ())
    current_registration = backend.read("registry", registry_key)
    registered = next((item for item in previous.external if item.kind == "registry" and item.key == registry_key), None)
    retired_registration = False
    if current_registration is not None and (registered is None or registered.after != current_registration):
        from .legacy import _registry_uninstaller
        errors = []
        legacy = _registry_uninstaller(backend, roots.data_root, roots.default_vault, errors) if registry_key == INNO_UNINSTALL_KEY else None
        if legacy is None or errors:
            raise OwnershipConflict("Uninstall registration is not owned or has changed")
        log = safe_path(legacy.with_suffix(".dat"))
        if not log.is_file() or not log.read_bytes().startswith(b"Inno Setup Uninstall Log"):
            raise OwnershipConflict("Legacy uninstall registration lacks an exact Inno log")
        retired_registration = True
    before = {}
    for name in ("unins000.exe", "unins000.dat"):
        path = safe_path(roots.app_root / "uninstall" / name)
        if path.exists() and not prove_ownership(path, previous):
            raise OwnershipConflict(f"Uninstaller file is not owned or has changed: {path}")
        before[name] = encode_bytes(path.read_bytes()) if path.is_file() else None
    atomic_write_json(request, {"schema_version": 3, "app_root": str(roots.app_root), "data_root": str(roots.data_root), "vault": str(roots.default_vault), "registry_key": registry_key, "registry_before": encode_bytes(current_registration), "retired_registration": retired_registration, "uninstaller_before": before})


@dataclass(frozen=True)
class ShellArtifacts:
    files: tuple
    registration: ExternalChange
    before: dict
    retired_registration: bool = False

    def owned_registration(self, previous):
        prior = next((item for item in previous.external if (item.kind, item.key) == (self.registration.kind, self.registration.key)), None)
        if prior is not None:
            if prior.after != self.registration.before:
                raise OwnershipConflict("Owned uninstall registration changed")
            return replace(self.registration, before=prior.before)
        return replace(self.registration, before=None) if self.retired_registration else self.registration

    def prepare(self, tx):
        for item in self.files:
            tx.adopt_before(item.path, decode_bytes(self.before.get(item.path.name)))


def deploy_shell(roots, *, package, request, backend):
    from .setup import setup
    from .update import update
    from .migration import plan_migration, apply_migration
    document = json.loads(safe_path(request).read_text(encoding="utf-8"))
    if document.get("schema_version") != 3 or any(document.get(key) != str(value) for key, value in (("app_root", roots.app_root), ("data_root", roots.data_root), ("vault", roots.default_vault))):
        raise OwnershipConflict("Shell preparation does not match selected roots")
    key = document["registry_key"]
    before = decode_bytes(document["registry_before"])
    if backend.read("registry", key) != before:
        raise OwnershipConflict("Uninstall registration changed after shell preparation")
    files = []
    for name in ("unins000.exe", "unins000.dat"):
        path = safe_path(roots.app_root / "uninstall" / name)
        if not path.is_file() or path.stat().st_nlink != 1:
            raise OwnershipConflict("Inno did not produce a regular uninstaller")
        files.append(OwnedFile(path, digest(path), "uninstaller"))
    uninstaller = roots.app_root / "uninstall/unins000.exe"
    import subprocess
    command = subprocess.list2cmdline([str(roots.app_root / "respectedbrain.exe"), "_inno-launch", "--app-root", str(roots.app_root), "--data-root", str(roots.data_root), "--vault", str(roots.default_vault)])
    values = {"DisplayName": "Respected Brain", "DisplayVersion": __version__, "Publisher": "Respected", "InstallLocation": str(roots.app_root), "UninstallString": command, "QuietUninstallString": command, "DisplayIcon": str(roots.app_root / "respectedbrain.exe")}
    registration = ExternalChange("registry", key, before, canonical_json({"values": {name: {"type": 1, "data": value} for name, value in values.items()}, "subkeys": {}}))
    shell = ShellArtifacts(tuple(files), registration, document["uninstaller_before"], document.get("retired_registration", False))
    store = ConfigStore(roots.data_root)
    try:
        config = store.read()
    except SelectionError:
        config = None
    registered = config is not None and any(Path(row["path"]).resolve() == roots.default_vault.resolve() for row in config["vaults"].values())
    if registered:
        ctx = build_context(roots, store, vault=roots.default_vault, vault_id=None, env={})
        return update(ctx, package=package, backend=backend, shell=shell)
    if roots.default_vault.is_dir() and any(roots.default_vault.iterdir()):
        plan = plan_migration(roots.data_root, roots.default_vault, roots=roots, backend=backend, profile=installed_profile(roots, {}))
        changes = tuple(item for item in plan.external if (item.kind, item.key) != (registration.kind, registration.key)) + (registration,)
        return apply_migration(replace(plan, external=changes), roots=roots, package=package, backend=backend, shell=shell)
    desired = config["integrations"] if config is not None else dict.fromkeys(("global", "mcp", "schedule", "shortcut"), False)
    return setup(roots, roots.default_vault, profile={}, desired=desired, backend=backend, package=package, shell=shell)
