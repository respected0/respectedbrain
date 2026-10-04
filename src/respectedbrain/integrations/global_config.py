"""Provider configuration merge algorithms; pure and ownership-aware."""
from __future__ import annotations
import ast
import json
from pathlib import Path
import re
from respectedbrain.core.legacy_names import LEGACY_GLOBAL_BEGIN, LEGACY_GLOBAL_END, LEGACY_HOOK_NAME, LEGACY_CURSOR_RULE
BEGIN = "<!-- RESPECTED-GLOBAL:BEGIN -->"
END = "<!-- RESPECTED-GLOBAL:END -->"
HOOK_NAME = "respected-brain"
CURSOR_RULE = HOOK_NAME + ".mdc"
SUPPORTED = ("antigravity", "gemini", "codex", "cursor", "claude")
def classify_managed_block(existing: str) -> str:
    current = (existing.count(BEGIN), existing.count(END))
    legacy = (existing.count(LEGACY_GLOBAL_BEGIN), existing.count(LEGACY_GLOBAL_END))
    if current[0] != current[1] or legacy[0] != legacy[1] or max((*current, *legacy)) > 1:
        return "partial"
    if current[0] and legacy[0]:
        return "collision"
    if current[0]:
        return "current"
    if legacy[0]:
        return "legacy"
    return "none"


def merge_managed(existing: str, managed: str) -> str:
    state = classify_managed_block(existing)
    if state == "partial":
        raise ValueError("global talimat dosyasında yarım veya tekrarlı yönetim bloğu var")
    if state == "collision":
        raise ValueError("legacy ve current global yönetim blokları çakışıyor")
    if state in {"current", "legacy"}:
        begin = BEGIN if state == "current" else LEGACY_GLOBAL_BEGIN
        end = END if state == "current" else LEGACY_GLOBAL_END
        start = existing.index(begin)
        finish = existing.index(end, start) + len(end)
        return existing[:start] + managed + existing[finish:]
    separator = "\n\n" if existing.strip() else ""
    return existing.rstrip() + separator + managed + "\n"


def windows_path(vault: Path) -> str | None:
    if vault.drive:
        return str(vault)
    parts = vault.parts
    if len(parts) >= 4 and parts[1] == "mnt" and len(parts[2]) == 1:
        return f"{parts[2].upper()}:\\" + "\\".join(parts[3:])
    return None


def _codex_notify_assignment(content: str) -> tuple[int, int, str] | None:
    match = re.search(r"(?m)^notify\s*=", content)
    if not match:
        return None
    cursor = match.end()
    while cursor < len(content) and content[cursor].isspace():
        cursor += 1
    if cursor >= len(content) or content[cursor] != "[":
        return match.start(), cursor, ""
    start_literal = cursor
    depth = 0
    quote = ""
    escaped = False
    while cursor < len(content):
        char = content[cursor]
        if quote:
            if quote == '"' and escaped:
                escaped = False
            elif quote == '"' and char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char in {'"', "'"}:
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return match.start(), cursor + 1, content[start_literal:cursor + 1]
        cursor += 1
    return match.start(), cursor, ""


def update_codex_config_toml(content: str, notify_argv: list[str]) -> str:
    escaped_items = ", ".join(json.dumps(item, ensure_ascii=False) for item in notify_argv)
    replacement = f"notify = [ {escaped_items} ]"
    assignment = _codex_notify_assignment(content)
    if assignment is not None:
        start, end, _literal = assignment
        return content[:start] + replacement + content[end:]
    prefix = f"{replacement}\n\n" if content.strip() else f"{replacement}\n"
    return prefix + content


def parse_codex_notify_argv(content: str) -> list[str] | None:
    """Read a Codex notify array without parsing or rewriting unrelated TOML."""
    assignment = _codex_notify_assignment(content)
    if assignment is None or not assignment[2]:
        return None
    try:
        value = ast.literal_eval(assignment[2])
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        return None
    return value


def managed_command(value: object, provider: str) -> bool:
    return isinstance(value, str) and "--global-hook" in value and f"--provider {provider}" in value


def merge_simple_hooks(document: dict, provider: str, additions: dict[str, list[dict]]) -> dict:
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks alanı bir JSON nesnesi değil")
    for event, definitions in additions.items():
        existing = hooks.get(event, [])
        if not isinstance(existing, list):
            raise ValueError(f"hooks.{event} bir liste değil")
        hooks[event] = [item for item in existing if not managed_command(item.get("command") if isinstance(item, dict) else None, provider)] + definitions
    return document


def merge_grouped_hooks(
    document: dict,
    provider: str,
    commands: dict[str, tuple[str, int]],
    *,
    async_events: frozenset[str] = frozenset(),
) -> dict:
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks alanı bir JSON nesnesi değil")
    for event, (command, timeout) in commands.items():
        groups = hooks.get(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"hooks.{event} bir liste değil")
        cleaned = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                cleaned.append(group)
                continue
            handlers = [handler for handler in group["hooks"] if not managed_command(handler.get("command") if isinstance(handler, dict) else None, provider)]
            if handlers or not group["hooks"]:
                updated = dict(group)
                updated["hooks"] = handlers
                cleaned.append(updated)
        handler = {
            "type": "command",
            "command": command,
            "timeout": timeout,
            "statusMessage": f"Loading {provider} second-brain memory",
        }
        if event in async_events:
            handler["async"] = True
        cleaned.append({"hooks": [handler]})
        hooks[event] = cleaned
    return document


def merge_gemini_hooks(document: dict, commands: dict[str, tuple[str, int]]) -> dict:
    """Merge Gemini CLI hooks using only fields in its public hook schema."""
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks alanı bir JSON nesnesi değil")
    for event, (command, timeout) in commands.items():
        groups = hooks.get(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"hooks.{event} bir liste değil")
        cleaned = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                cleaned.append(group)
                continue
            handlers = [
                handler
                for handler in group["hooks"]
                if not managed_command(
                    handler.get("command") if isinstance(handler, dict) else None,
                    "gemini",
                )
            ]
            if handlers or not group["hooks"]:
                updated = dict(group)
                updated["hooks"] = handlers
                cleaned.append(updated)
        cleaned.append(
            {
                "hooks": [
                    {
                        "name": f"respected-brain-{event.lower()}",
                        "type": "command",
                        "command": command,
                        "timeout": timeout,
                        "description": "Sync Respected Brain memory",
                    }
                ]
            }
        )
        hooks[event] = cleaned
    return document


def identity_settings(ctx):
    entry = ctx.config.get("vaults", {}).get(ctx.paths.vault_id, {})
    preferences = dict(ctx.config.get("preferences", {}))
    preferences.update(entry.get("preferences", {}))
    settings = entry.get("settings", {})
    defaults = {"OS_NAME": ctx.paths.vault_root.name, "COMPANION": "Companion", "USER_NAME": "User", "USER_BIO": ""}
    return {key: settings.get(key, preferences.get(key.lower(), value)) for key, value in defaults.items()}
