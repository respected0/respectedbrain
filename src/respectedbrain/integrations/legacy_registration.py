"""Readonly cleanup plans after exact legacy registration inspection."""
from __future__ import annotations
import json
from dataclasses import replace
from pathlib import Path
from .backend import ExternalChange
from .global_config import BEGIN, END, classify_managed_block, parse_codex_notify_argv, update_codex_config_toml, _codex_notify_assignment
from respectedbrain.core.legacy_names import LEGACY_GLOBAL_BEGIN, LEGACY_GLOBAL_END
from respectedbrain.core.errors import OwnershipConflict

def _remove_global(backend, row, ctx, profile):
    if Path(row.key).name == "SKILL.md":
        return None
    text = row.before.decode("utf-8")
    state = classify_managed_block(text)
    if state in {"current", "legacy"}:
        begin = BEGIN if state == "current" else LEGACY_GLOBAL_BEGIN
        end = END if state == "current" else LEGACY_GLOBAL_END
        start = text.index(begin)
        finish = text.index(end, start) + len(end)
        return (text[:start] + text[finish:]).encode("utf-8")
    if Path(row.key).name == "config.toml":
        argv = parse_codex_notify_argv(text)
        if not argv:
            raise OwnershipConflict("Inspected notify handler is no longer readable")
        chain = None
        if "--chain-file" in argv:
            index = argv.index("--chain-file")
            if index + 1 >= len(argv):
                raise OwnershipConflict("Legacy notify chain is incomplete")
            path = Path(argv[index + 1])
            known = {profile.user_home / ".codex/respected-notify-chain.json", ctx.paths.state_dir / "codex-notify-chain.json"}
            if path.resolve() not in {candidate.resolve() for candidate in known}:
                raise OwnershipConflict("Legacy notify chain belongs to an unknown path")
            data = backend.read("file", str(path))
            if data is None:
                raise OwnershipConflict("Legacy notify chain is missing")
            document = json.loads(data)
            chain = document.get("argv")
            if not isinstance(chain, list) or not chain or not all(isinstance(value, str) for value in chain):
                raise OwnershipConflict("Legacy notify chain is malformed")
        if chain:
            return update_codex_config_toml(text, chain).encode("utf-8")
        assignment = _codex_notify_assignment(text)
        return (text[:assignment[0]] + text[assignment[1]:]).encode("utf-8")
    document = json.loads(text)
    def clean(value):
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("command"), str) and ("--global-hook" in item["command"] or "bridge.py" in item["command"]):
                    continue
                updated = clean(item)
                if isinstance(updated, dict) and "hooks" in updated and not updated["hooks"] and item.get("hooks"):
                    continue
                result.append(updated)
            return result
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        return value
    return (json.dumps(clean(document), ensure_ascii=False, indent=2) + "\n").encode("utf-8")

def migration_changes(backend, ctx, *, legacy_root, vault, roots, profile, desired):
    snapshots = backend.inspect_legacy_registrations(legacy_root, vault, roots, profile)
    old_proofs = getattr(backend, "_legacy_proofs", {})
    backend._legacy_proofs = {(row.kind, row.key): row.before for row in snapshots}
    try:
        fresh = backend.preview(ctx, desired=desired, profile=profile)
    finally:
        backend._legacy_proofs = old_proofs
    # New current registration is applied and verified before retiring old names.
    changes = {(row.kind, row.key): row for row in fresh}
    for row in snapshots:
        identity = (row.kind, row.key)
        if row.kind == "file":
            baseline = _remove_global(backend, row, ctx, profile)
        elif row.kind == "mcp":
            document = json.loads(row.before)
            document["mcpServers"].pop("respected-vault", None)
            baseline = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        else:
            baseline = None
        if identity in changes:
            changes[identity] = replace(changes[identity], has_uninstall_baseline=True, uninstall_before=baseline)
            continue
        desired_key = {"file": "global", "mcp": "mcp", "task": "schedule", "shortcut": "shortcut"}.get(row.kind)
        after = row.before
        if row.kind in {"task", "shortcut"}:
            after = None  # Old registered names/launchers retire after current verification.
        elif desired_key is not None and not desired.get(desired_key, False):
            if row.kind == "file":
                after = _remove_global(backend, row, ctx, profile)
            elif row.kind == "mcp":
                document = json.loads(row.before)
                document["mcpServers"].pop("respected-vault", None)
                after = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        changes[identity] = ExternalChange(row.kind, row.key, row.before, after, has_uninstall_baseline=True, uninstall_before=baseline)
    return tuple(changes.values())
