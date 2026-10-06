"""Dispatch existing maintenance tools against one explicit application context."""
from __future__ import annotations

from respectedbrain.core.coordination import guarded_writer

from importlib import import_module
from pathlib import Path
import os
from typing import Sequence
from respectedbrain.core.platform import path_within_vault

from respectedbrain.core.context import AppContext

_TOOLS = {
    "repair_daily": ".repair_daily",
    "vault_linter": ".vault_linter",
    "architect_scan": ".architect_scan",
    "smart_merge": ".smart_merge",
    "tiling_check": ".tiling_check",
    "backup_restic": ".backup.backup_restic",
    "publish_git_snapshot": ".backup.publish_git_snapshot",
    "mine_agent_history": ".ingestion.mine_agent_history",
    "defuddle": ".ingestion.defuddle",
}


def selected_vault(ctx: AppContext | None, candidate: Path | str | None) -> Path:
    if ctx is None:
        if candidate is None:
            raise ValueError("An explicit vault context is required")
        return Path(candidate).resolve()
    if candidate is not None and Path(candidate).resolve() != ctx.paths.vault_root:
        raise ValueError("Tool vault must match the selected vault context")
    return ctx.paths.vault_root


def mutable_target(ctx: AppContext | None, target: Path) -> Path:
    target = target.absolute()
    if not path_within_vault(target, Path(target.anchor)):
        raise ValueError("Maintenance target contains a link or reparse point")
    target = target.resolve()
    if ctx is not None and target.is_relative_to(ctx.paths.app_root):
        raise ValueError("Application resources are immutable")
    return target


def note_target(root: Path, target: Path) -> Path:
    root = root.resolve()
    target = target.absolute()
    if target.suffix.lower() != '.md' or not path_within_vault(target, root):
        raise ValueError("Note target must remain within the selected vault without links")
    return target.resolve()


def safe_walk(root: Path):
    """Prune link/reparse directories and files before traversing them."""
    root = mutable_target(None, root)
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if path_within_vault(Path(current) / name, root)]
        yield current, directories, [name for name in files if path_within_vault(Path(current) / name, root)]


@guarded_writer(busy_result=None)
def _run_tool(ctx: AppContext, *, name: str, argv: Sequence[str]) -> int:
    try:
        module_name = _TOOLS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown maintenance tool: {name}") from exc
    module = import_module(module_name, __name__)
    return module.main(list(argv), ctx=ctx)


def run_tool(ctx: AppContext, *, name: str, argv: Sequence[str]) -> int:
    if name not in _TOOLS:
        raise ValueError(f"Unknown maintenance tool: {name}")
    for index, value in enumerate(argv):
        if value in ("--vault", "--vault-root") and index + 1 < len(argv):
            selected_vault(ctx, argv[index + 1])
        elif value.startswith(("--vault=", "--vault-root=")):
            selected_vault(ctx, value.partition("=")[2])
    # Tools with optional writes admit the parsed mutation inside their main.
    if name in ("architect_scan", "tiling_check", "vault_linter"):
        return import_module(_TOOLS[name], __name__).main(list(argv), ctx=ctx)
    return _run_tool(ctx, name=name, argv=argv)
