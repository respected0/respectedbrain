#!/usr/bin/env python3
"""Connect supported AI tools globally to an arbitrary Respot Brain vault."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys


BEGIN = "<!-- RESPOT-GLOBAL:BEGIN -->"
END = "<!-- RESPOT-GLOBAL:END -->"
SUPPORTED = ("antigravity", "codex", "cursor", "claude")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_object(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} bir JSON nesnesi değil")
    return value


def merge_managed(existing: str, managed: str) -> str:
    has_begin = BEGIN in existing
    has_end = END in existing
    if has_begin != has_end:
        raise ValueError("global talimat dosyasında yarım Respot yönetim bloğu var")
    if has_begin:
        start = existing.index(BEGIN)
        finish = existing.index(END, start) + len(END)
        return existing[:start] + managed + existing[finish:]
    separator = "\n\n" if existing.strip() else ""
    return existing.rstrip() + separator + managed + "\n"


def windows_path(vault: Path) -> str | None:
    parts = vault.parts
    if len(parts) >= 4 and parts[1] == "mnt" and len(parts[2]) == 1:
        return f"{parts[2].upper()}:\\" + "\\".join(parts[3:])
    return None


def managed_rule(vault: Path) -> str:
    instructions = (vault / ".beyin/instructions.md").read_text(encoding="utf-8").strip()
    win = windows_path(vault)
    locations = f"`{vault}`" + (f" (Windows: `{win}`)" if win else "")
    return (
        f"{BEGIN}\n"
        "# Global ikinci beyin bağlantısı\n\n"
        f"Kalıcı hafıza vault'u **{vault.name}**: {locations}.\n"
        "Göreceli hafıza yollarını aktif kod reposuna göre değil bu vault köküne göre çöz. "
        "Kullanıcı istemedikçe proje kodunu vault'a taşıma. Vault adı kullanıcı tercihidir; "
        "`respectedOS` olması gerekmez.\n\n"
        f"{instructions}\n"
        f"{END}"
    )


def bridge_command(vault: Path, provider: str, event: str, windows_wsl: bool) -> str:
    bridge = ".beyin/hooks/bridge.py"
    args = f"--global-hook --provider {provider} --event {event}"
    if windows_wsl:
        return f'wsl.exe --cd "{vault.as_posix()}" python3 {bridge} {args}'
    return f'python3 "{vault.as_posix()}/{bridge}" {args}'


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


def merge_grouped_hooks(document: dict, provider: str, commands: dict[str, tuple[str, int]]) -> dict:
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
            if handlers:
                updated = dict(group)
                updated["hooks"] = handlers
                cleaned.append(updated)
        cleaned.append({"hooks": [{"type": "command", "command": command, "timeout": timeout, "statusMessage": f"Loading {provider} second-brain memory"}]})
        hooks[event] = cleaned
    return document


def copy_skills(vault: Path, roots: list[Path]) -> list[tuple[Path, str]]:
    writes = []
    for source in sorted((vault / ".beyin/skills").glob("*/SKILL.md")):
        content = source.read_text(encoding="utf-8")
        for root in roots:
            writes.append((root / source.parent.name / "SKILL.md", content))
    return writes


def build(vault: Path, home: Path, providers: tuple[str, ...], windows_wsl: bool) -> tuple[list[tuple[Path, str]], list[Path]]:
    writes: list[tuple[Path, str]] = []
    touched: list[Path] = []
    rule = managed_rule(vault)

    if "antigravity" in providers:
        config = home / ".gemini/config"
        hooks_path = config / "hooks.json"
        hooks = load_object(hooks_path)
        hooks["respot-brain"] = {
            "PreInvocation": [{"type": "command", "command": bridge_command(vault, "antigravity", "start", windows_wsl), "timeout": 15}],
            "Stop": [{"type": "command", "command": bridge_command(vault, "antigravity", "end", windows_wsl), "timeout": 10}],
        }
        rule_path = home / ".gemini/GEMINI.md"
        writes += [(hooks_path, json.dumps(hooks, ensure_ascii=False, indent=2) + "\n"), (rule_path, merge_managed(rule_path.read_text(encoding="utf-8") if rule_path.exists() else "", rule))]
        writes += copy_skills(vault, [config / "skills"])
        touched += [hooks_path, rule_path]

    if "codex" in providers:
        config = home / ".codex"
        hooks_path = config / "hooks.json"
        hooks = load_object(hooks_path)
        commands = {
            "SessionStart": (bridge_command(vault, "codex", "start", windows_wsl), 15),
            "UserPromptSubmit": (bridge_command(vault, "codex", "prompt", windows_wsl), 5),
            "SessionEnd": (bridge_command(vault, "codex", "end", windows_wsl), 3),
            "PreCompact": (bridge_command(vault, "codex", "precompact", windows_wsl), 10),
        }
        merge_grouped_hooks(hooks, "codex", commands)
        hooks_path_content = json.dumps(hooks, ensure_ascii=False, indent=2) + "\n"
        rule_path = config / "AGENTS.md"
        writes += [(hooks_path, hooks_path_content), (rule_path, merge_managed(rule_path.read_text(encoding="utf-8") if rule_path.exists() else "", rule))]
        writes += copy_skills(vault, [home / ".agents/skills"])
        touched += [hooks_path, rule_path]

    if "cursor" in providers:
        config = home / ".cursor"
        hooks_path = config / "hooks.json"
        hooks = load_object(hooks_path)
        hooks.setdefault("version", 1)
        additions = {
            "sessionStart": [{"command": bridge_command(vault, "cursor", "start", windows_wsl), "timeout": 15}],
            "beforeSubmitPrompt": [{"command": bridge_command(vault, "cursor", "prompt", windows_wsl), "timeout": 5}],
            "sessionEnd": [{"command": bridge_command(vault, "cursor", "end", windows_wsl), "timeout": 10}],
            "preCompact": [{"command": bridge_command(vault, "cursor", "precompact", windows_wsl), "timeout": 10}],
        }
        merge_simple_hooks(hooks, "cursor", additions)
        rule_path = config / "rules/respot-brain.mdc"
        cursor_rule = "---\ndescription: Global second-brain memory\nalwaysApply: true\n---\n\n" + rule + "\n"
        writes += [(hooks_path, json.dumps(hooks, ensure_ascii=False, indent=2) + "\n"), (rule_path, cursor_rule)]
        writes += copy_skills(vault, [config / "skills"])
        touched += [hooks_path, rule_path]

    if "claude" in providers:
        config = home / ".claude"
        settings_path = config / "settings.json"
        settings = load_object(settings_path)
        commands = {
            "SessionStart": (bridge_command(vault, "claude", "start", windows_wsl), 15),
            "UserPromptSubmit": (bridge_command(vault, "claude", "prompt", windows_wsl), 5),
            "SessionEnd": (bridge_command(vault, "claude", "end", windows_wsl), 3),
            "PreCompact": (bridge_command(vault, "claude", "precompact", windows_wsl), 10),
        }
        merge_grouped_hooks(settings, "claude", commands)
        rule_path = config / "CLAUDE.md"
        writes += [(settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n"), (rule_path, merge_managed(rule_path.read_text(encoding="utf-8") if rule_path.exists() else "", rule))]
        writes += copy_skills(vault, [config / "skills"])
        touched += [settings_path, rule_path]

    return writes, touched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, help="adı serbest olan ikinci beyin vault yolu")
    parser.add_argument("--home", required=True, type=Path, help="AI araçlarının kullanıcı kökü")
    parser.add_argument("--providers", default="all", help="all veya virgülle: antigravity,codex,cursor,claude")
    parser.add_argument("--platform", choices=("portable", "windows-wsl"), default="portable")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    vault = args.vault.expanduser().resolve()
    home = args.home.expanduser().resolve()
    providers = SUPPORTED if args.providers == "all" else tuple(dict.fromkeys(part.strip().lower() for part in args.providers.split(",") if part.strip()))
    unknown = set(providers) - set(SUPPORTED)
    if unknown:
        parser.error(f"bilinmeyen provider: {', '.join(sorted(unknown))}")
    if not (vault / ".beyin/instructions.md").is_file() or not (vault / ".beyin/skills").is_dir():
        parser.error("geçerli vault içinde .beyin/instructions.md ve .beyin/skills bulunmalı")
    if not home.is_dir():
        parser.error(f"kullanıcı kökü bulunamadı: {home}")
    try:
        writes, touched = build(vault, home, providers, args.platform == "windows-wsl")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2
    print(f"vault: {vault} (adı: {vault.name})")
    print(f"provider'lar: {', '.join(providers)}")
    for path, _ in writes:
        print(f"yönetilecek: {path}")
    if not args.apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0
    backup = home / ".respot-backups" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        for path in touched:
            if path.is_file():
                destination = backup / path.relative_to(home)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                os.chmod(destination, 0o600)
        for path, content in writes:
            write_text(path, content)
    except OSError as exc:
        print(f"yazma başarısız: {exc}; yedek: {backup}", file=sys.stderr)
        return 3
    print(f"Global bağlantı kuruldu; yedek: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
