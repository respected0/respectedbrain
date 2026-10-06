"""Atomic final note replacement, including DataRoot staging on another volume."""
from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil
import tempfile


def replace_staged(staging: Path, destination: Path) -> None:
    try:
        os.replace(staging, destination)
        return
    except OSError as error:
        if error.errno != errno.EXDEV and getattr(error, "winerror", None) != 17:
            raise
    # A same-volume commit file is required for atomic replacement. Only this
    # short-lived final commit lives beside the note; durable staging is DataRoot.
    descriptor, name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    commit = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            with staging.open("rb") as source:
                shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(commit, destination)
        staging.unlink(missing_ok=True)
    finally:
        commit.unlink(missing_ok=True)
