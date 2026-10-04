"""Cross-process locks used only during explicit write operations."""
from __future__ import annotations
from contextlib import contextmanager
import os
from pathlib import Path
import time
from typing import Iterator

from .errors import BusyError


@contextmanager
def shared_lock(path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    """Active jobs share a lease; an exclusive quiescence lock excludes them all."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    locked = False
    # Windows byte-range locks can cover bytes beyond EOF. Writing a bootstrap
    # byte here races another process that has already locked the empty file.
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        class OVERLAPPED(ctypes.Structure):
            _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t), ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD), ("hEvent", wintypes.HANDLE)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LockFileEx.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(OVERLAPPED))
        kernel.LockFileEx.restype = wintypes.BOOL
        kernel.UnlockFileEx.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(OVERLAPPED))
        overlapped, handle = OVERLAPPED(), msvcrt.get_osfhandle(descriptor)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    if not kernel.LockFileEx(handle, 1, 0, 1, 0, ctypes.byref(overlapped)):
                        raise ctypes.WinError(ctypes.get_last_error())
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
                locked = True
                break
            except OSError as error:
                if time.monotonic() >= deadline:
                    raise BusyError(f"Activation lock is held: {path}") from error
                time.sleep(.02)
        yield
    finally:
        if locked:
            if os.name == "nt":
                kernel.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(overlapped))
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


@contextmanager
def exclusive_lock(path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    locked = False
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise BusyError(f"Write lock is held: {path}") from exc
                time.sleep(0.02)
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
