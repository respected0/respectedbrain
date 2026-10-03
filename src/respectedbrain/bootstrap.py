"""Composition root: resolve roots and select a registered vault explicitly."""
from __future__ import annotations
import os
from pathlib import Path
import sys
from typing import Mapping

from .core.config import ConfigStore
from .core.context import AppContext
from .core.paths import Roots, resolve_roots
from .core.platform import known_folder
from .vault.registry import build_context


def application_roots(*, env: Mapping[str, str] | None = None) -> Roots:
    values = dict(os.environ if env is None else env)
    if getattr(sys, "frozen", False):
        values.setdefault("RESPECTED_APP_DIR", str(Path(sys.executable).parent))
    return resolve_roots(platform=sys.platform, home=Path.home(), env=values, known_folder=known_folder)


def bootstrap(*, vault: Path | None = None, vault_id: str | None = None,
              env: Mapping[str, str] | None = None) -> AppContext:
    values = os.environ if env is None else env
    roots = application_roots(env=values)
    return build_context(roots, ConfigStore(roots.data_root), vault=vault, vault_id=vault_id, env=values)


def launcher_argv(*, env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable,)
    return (sys.executable, "-m", "respectedbrain")
