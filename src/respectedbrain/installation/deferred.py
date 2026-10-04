"""Resume self-update/removal from a verified OS temporary application copy."""
from __future__ import annotations
import ctypes
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

from respectedbrain.core.config import ConfigStore, atomic_write_json
from respectedbrain.core.errors import OwnershipConflict
from respectedbrain.core.paths import Roots
from respectedbrain.vault.registry import build_context
from .ownership import safe_path, digest
from .payload import validate_package
from .transaction import OperationResult


def defer_operation(ctx, *, mode, package=None, purge_data=False):
    if sys.platform != "win32" or not getattr(sys, "frozen", False) or Path(sys.executable).resolve() != (ctx.paths.app_root / "respectedbrain.exe").resolve():
        return None
    if mode not in ("update", "uninstall"):
        raise ValueError("Only activation/removal require exit deferral")
    document = validate_package(ctx.paths.app_root)
    if mode == "update":
        validate_package(package)
    temporary = Path(tempfile.mkdtemp(prefix="respected-activation-"))
    try:
        for name in (*document["files"], "distribution.json"):
            source = safe_path(ctx.paths.app_root / name)
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        validate_package(temporary)
        identity = "deferred-" + str(uuid4())
        request = temporary / "request.json"
        receipt = ctx.paths.data_root / "backups" / identity / "result.json"
        atomic_write_json(request, {"schema_version": 3, "parent_pid": os.getpid(), "mode": mode, "app_root": str(ctx.paths.app_root), "data_root": str(ctx.paths.data_root), "vault": str(ctx.paths.vault_root), "vault_id": ctx.paths.vault_id, "package": str(package) if package is not None else None, "purge_data": bool(purge_data), "receipt": str(receipt)})
        subprocess.Popen([str(temporary / document["launcher"]), "_resume-operation", "--request", str(request), "--request-hash", digest(request)], cwd=temporary, env={**os.environ, "RESPECTED_APP_DIR": str(ctx.paths.app_root), "RESPECTED_DATA_DIR": str(ctx.paths.data_root)}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        # The caller must exit; the helper writes a final receipt after activation.
        return OperationResult(False, identity, (), pending=True)
    except BaseException:
        if temporary.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            shutil.rmtree(temporary)
        raise


def _wait_parent(pid):
    if sys.platform != "win32":
        raise ValueError("Activation helper is Windows-only")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # parent already exited
            return
        raise OSError(ctypes.get_last_error(), "Cannot wait for active launcher")
    try:
        if kernel.WaitForSingleObject(handle, 300000) != 0:
            raise OSError("Active launcher did not exit; activation cancelled")
    finally:
        kernel.CloseHandle(handle)


def resume_operation(request: Path, *, expected_hash: str) -> int:
    safe_path(request)
    if digest(request) != expected_hash:
        raise OwnershipConflict("Activation request changed")
    if not request.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise OwnershipConflict("Activation helper must live in OS temporary storage")
    validate_package(request.parent)
    document = json.loads(request.read_text(encoding="utf-8"))
    if document.get("schema_version") != 3 or document.get("mode") not in ("update", "uninstall"):
        raise OwnershipConflict("Invalid activation request")
    _wait_parent(int(document["parent_pid"]))
    roots = Roots(Path(document["app_root"]), Path(document["data_root"]), Path(document["vault"]))
    ctx = build_context(roots, ConfigStore(roots.data_root), vault=None, vault_id=document["vault_id"], env={})
    from respectedbrain.integrations.backend import NativeBackend
    backend = NativeBackend(roots.data_root)
    receipt = safe_path(Path(document["receipt"]))
    if receipt.parent.parent != roots.data_root / "backups" or not receipt.parent.name.startswith("deferred-"):
        raise OwnershipConflict("Invalid activation receipt boundary")
    if document["mode"] == "update":
        from .update import update
        result = update(ctx, package=Path(document["package"]), backend=backend)
    else:
        from .uninstall import uninstall
        if (ctx.paths.app_root / "uninstall/unins000.exe").is_file() and not document["purge_data"]:
            from .windows import launch_uninstaller
            result = launch_uninstaller(ctx, request=request.parent / "uninstall-proof.json")
        else:
            result = uninstall(ctx, backend=backend, purge_data=document["purge_data"])
    atomic_write_json(receipt, asdict(result))
    return 0 if result.success else 1
