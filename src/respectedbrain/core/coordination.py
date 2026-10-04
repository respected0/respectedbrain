"""A brief admission lock prevents new writers during app activation."""
from __future__ import annotations
from contextlib import contextmanager, ExitStack
from functools import wraps
from pathlib import Path
import threading
from uuid import UUID

from .errors import OwnershipConflict, BusyError
from .locking import exclusive_lock, shared_lock
from .platform import path_within_vault

_held = threading.local()


@contextmanager
def writer_lease(ctx, *, timeout=0):
    data, state = ctx.paths.data_root, ctx.paths.state_dir
    key = str(state)
    held = getattr(_held, "paths", set())
    if key in held:
        yield
        return
    if not path_within_vault(state / "writer.lock", data):
        raise OwnershipConflict("Unsafe writer lock")
    with ExitStack() as stack:
        with exclusive_lock(data / ".operation.lock", timeout=timeout):
            stack.enter_context(shared_lock(state / "writer.lock", timeout=timeout))
        _held.paths = held | {key}
        try:
            yield
        finally:
            _held.paths = held


@contextmanager
def quiesce_writers(data_root: Path, vault_id: str | None):
    roots = []
    if vault_id is not None:
        roots.append(data_root / "vaults" / str(UUID(vault_id)) / "state")
    elif (data_root / "vaults").is_dir():
        for candidate in sorted((data_root / "vaults").iterdir()):
            try:
                UUID(candidate.name)
            except ValueError:
                continue
            roots.append(candidate / "state")
    with ExitStack() as stack:
        for root in roots:
            lock = root / "writer.lock"
            if not path_within_vault(lock, data_root):
                raise OwnershipConflict("Unsafe writer lock")
            stack.enter_context(exclusive_lock(lock, timeout=0))
        yield


def guarded_writer(function=None, *, busy_result=0):
    if function is None:
        return lambda function: guarded_writer(function, busy_result=busy_result)
    @wraps(function)
    def guarded(ctx, *args, **kwargs):
        try:
            with writer_lease(getattr(ctx, "ctx", ctx), timeout=10):
                return function(ctx, *args, **kwargs)
        except BusyError:
            if busy_result is None:
                raise
            return busy_result
    return guarded
