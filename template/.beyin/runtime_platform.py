#!/usr/bin/env python3
"""Small host-specific primitives shared by the Respected memory runtime."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import time
from typing import ContextManager, IO


_WINDOWS_REPARSE_POINT = 0x0400


def _prepare_windows_lock(handle: IO[str]) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write("\0")
        handle.flush()
    handle.seek(0)


def _acquire_windows(handle: IO[str], *, blocking: bool, timeout: float) -> bool:
    import msvcrt

    _prepare_windows_lock(handle)
    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            if not blocking or time.monotonic() >= deadline:
                return False
            time.sleep(0.05)


def _acquire_posix(handle: IO[str], *, blocking: bool) -> bool:
    import fcntl

    operation = fcntl.LOCK_EX
    if not blocking:
        operation |= fcntl.LOCK_NB
    try:
        fcntl.flock(handle.fileno(), operation)
    except BlockingIOError:
        return False
    return True


def _release(handle: IO[str]) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def exclusive_lock(
    handle: IO[str], *, blocking: bool, timeout: float = 300.0
) -> ContextManager[bool]:
    """Hold an exclusive file lock and yield whether acquisition succeeded."""

    if os.name == "nt":
        held = _acquire_windows(handle, blocking=blocking, timeout=timeout)
    else:
        held = _acquire_posix(handle, blocking=blocking)
    try:
        yield held
    finally:
        if held:
            _release(handle)


def detached_process_options() -> dict[str, int | bool]:
    """Return subprocess options for a child that survives the caller."""

    if os.name != "nt":
        return {"start_new_session": True}
    flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    flags |= int(getattr(subprocess, "DETACHED_PROCESS", 0x00000008))
    flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {"creationflags": flags}


def hidden_process_options() -> dict[str, int]:
    """Hide a synchronous child console on native Windows."""

    if os.name != "nt":
        return {}
    return {
        "creationflags": int(
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
    }


def windows_user_root(path: Path) -> Path | None:
    """Return /mnt/<drive>/Users/<user> for a WSL-visible user path."""

    parts = PurePosixPath(os.fspath(path).replace("\\", "/")).parts
    if (
        len(parts) < 5
        or parts[0] != "/"
        or parts[1] != "mnt"
        or len(parts[2]) != 1
        or parts[3].casefold() != "users"
    ):
        return None
    return Path(*parts[:5])


def external_temp_parent(vault_root: Path) -> Path | None:
    """Choose a temp parent usable by both WSL Python and Windows CLIs."""

    if os.name == "nt":
        return None
    user_root = windows_user_root(vault_root)
    if user_root is None:
        return None
    return user_root / "AppData" / "Local" / "Temp"


def create_exclusive_claim(path: Path, mode: int = 0o600) -> bool:
    """Create a claim file once without overwriting an existing claimant."""

    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    except FileExistsError:
        return False
    except PermissionError:
        if os.name == "nt" and path.exists():
            return False
        raise
    os.close(descriptor)
    return True


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return bool(attributes & _WINDOWS_REPARSE_POINT)


def _has_unsafe_component(path: Path, vault_root: Path) -> bool:
    try:
        relative = path.absolute().relative_to(vault_root.absolute())
    except ValueError:
        return False
    current = vault_root.absolute()
    if _is_link_or_reparse(current):
        return True
    for part in relative.parts:
        current /= part
        if _is_link_or_reparse(current):
            return True
    return False


def path_within_vault(path: Path, vault_root: Path) -> bool:
    """Return true only for a contained path reached without links/reparse points."""

    candidate = Path(path)
    root = Path(vault_root)
    if _has_unsafe_component(candidate, root):
        return False
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return False
    return True
