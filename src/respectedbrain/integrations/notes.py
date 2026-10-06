"""Bounded note I/O shared by the local HTTP and MCP entry points."""
from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
import uuid

from respectedbrain.core.platform import path_within_vault

MAX_NOTE_BYTES = 5 * 1024 * 1024


def note_path(root: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or not relative or '\0' in relative or ':' in relative:
        return None
    relative = relative.replace('\\', '/')
    parts = relative.split('/')
    if any(not part or part in {'.', '..'} or part.rstrip(' .') != part
           or PureWindowsPath(part).is_reserved() for part in parts):
        return None
    target = root.joinpath(*parts)
    if target.suffix.lower() != '.md' or not path_within_vault(target, root):
        return None
    return target


def read_note(root: Path, relative: str, *, max_chars: int | None = None) -> str:
    target = note_path(root, relative)
    if target is None:
        raise ValueError('unsafe-note-path')
    with target.open('rb') as handle:
        content = handle.read(MAX_NOTE_BYTES + 1)
    if len(content) > MAX_NOTE_BYTES:
        raise ValueError('note-too-large')
    text = content.decode('utf-8', errors='replace')
    return text if max_chars is None else text[:max_chars]


def create_note(root: Path, directory: Path, filename: str, body: str) -> Path:
    """Exclusively create a note; collisions never replace existing bytes."""
    payload = body.encode('utf-8')
    if len(payload) > MAX_NOTE_BYTES:
        raise ValueError('note-too-large')
    directory.relative_to(root)
    target = directory / filename
    if note_path(root, target.relative_to(root).as_posix()) is None:
        raise ValueError('unsafe-note-path')
    directory.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        if note_path(root, target.relative_to(root).as_posix()) is None:
            raise ValueError('unsafe-note-path')
        try:
            with target.open('xb') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            return target
        except FileExistsError:
            target = directory / (uuid.uuid4().hex + '_' + filename)
    raise FileExistsError('note-name-collision')
