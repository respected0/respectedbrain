#!/usr/bin/env python3
"""Connect supported AI tools globally to an arbitrary Respected Brain vault."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path, PurePath
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_integrations import (  # noqa: E402
    DEFAULT_PYTHON_COMMANDS,
    Profile,
    command_text,
)
from legacy_names import (  # noqa: E402
    LEGACY_CURSOR_RULE,
    LEGACY_GLOBAL_BEGIN,
    LEGACY_GLOBAL_BACKUP_ROOT,
    LEGACY_GLOBAL_END,
    LEGACY_HOOK_NAME,
)


BEGIN = "<!-- RESPECTED-GLOBAL:BEGIN -->"
END = "<!-- RESPECTED-GLOBAL:END -->"
HOOK_NAME = "respected-brain"
CURSOR_RULE = HOOK_NAME + ".mdc"
SUPPORTED = ("antigravity", "codex", "cursor", "claude")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
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


def _user_home() -> Path:
    env_home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if env_home:
        return Path(env_home)
    return Path.home()


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


def bridge_command(vault: PurePath, provider: str, event: str, platform: str) -> str:
    profile = Profile(platform, DEFAULT_PYTHON_COMMANDS[platform])
    return command_text(profile, vault, provider, event, global_hook=True)


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


def build(vault: Path, home: Path, providers: tuple[str, ...], platform: str) -> tuple[list[tuple[Path, str | None]], list[Path]]:
    writes: list[tuple[Path, str | None]] = []
    touched: list[Path] = []
    rule = managed_rule(vault)

    if "antigravity" in providers:
        config = home / ".gemini/config"
        hooks_path = config / "hooks.json"
        hooks = load_object(hooks_path)
        if LEGACY_HOOK_NAME in hooks and HOOK_NAME in hooks:
            raise ValueError("legacy ve current Antigravity hook anahtarları çakışıyor")
        hooks.pop(LEGACY_HOOK_NAME, None)
        hooks[HOOK_NAME] = {
            "PreInvocation": [{"type": "command", "command": bridge_command(vault, "antigravity", "start", platform), "timeout": 15}],
            "Stop": [{"type": "command", "command": bridge_command(vault, "antigravity", "end", platform), "timeout": 10}],
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
            "SessionStart": (bridge_command(vault, "codex", "start", platform), 15),
            "UserPromptSubmit": (bridge_command(vault, "codex", "prompt", platform), 5),
            "SessionEnd": (bridge_command(vault, "codex", "end", platform), 3),
            "PreCompact": (bridge_command(vault, "codex", "precompact", platform), 10),
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
            "sessionStart": [{"command": bridge_command(vault, "cursor", "start", platform), "timeout": 15}],
            "beforeSubmitPrompt": [{"command": bridge_command(vault, "cursor", "prompt", platform), "timeout": 5}],
            "sessionEnd": [{"command": bridge_command(vault, "cursor", "end", platform), "timeout": 10}],
            "preCompact": [{"command": bridge_command(vault, "cursor", "precompact", platform), "timeout": 10}],
        }
        merge_simple_hooks(hooks, "cursor", additions)
        rule_path = config / "rules" / CURSOR_RULE
        legacy_rule_path = config / "rules" / LEGACY_CURSOR_RULE
        if legacy_rule_path.exists():
            if rule_path.exists():
                raise ValueError("legacy ve current Cursor rule dosyaları çakışıyor")
            legacy_content = legacy_rule_path.read_text(encoding="utf-8")
            if classify_managed_block(legacy_content) != "legacy":
                raise ValueError("legacy Cursor rule yönetilen dosya olarak doğrulanamadı")
            writes.append((legacy_rule_path, None))
            touched.append(legacy_rule_path)
        cursor_rule = "---\ndescription: Global second-brain memory\nalwaysApply: true\n---\n\n" + rule + "\n"
        writes += [(hooks_path, json.dumps(hooks, ensure_ascii=False, indent=2) + "\n"), (rule_path, cursor_rule)]
        writes += copy_skills(vault, [config / "skills"])
        touched += [hooks_path, rule_path]

    if "claude" in providers:
        config = home / ".claude"
        settings_path = config / "settings.json"
        settings = load_object(settings_path)
        commands = {
            "SessionStart": (bridge_command(vault, "claude", "start", platform), 15),
            "UserPromptSubmit": (bridge_command(vault, "claude", "prompt", platform), 5),
            "SessionEnd": (bridge_command(vault, "claude", "end", platform), 3),
            "PreCompact": (bridge_command(vault, "claude", "precompact", platform), 10),
        }
        merge_grouped_hooks(settings, "claude", commands)
        rule_path = config / "CLAUDE.md"
        writes += [(settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n"), (rule_path, merge_managed(rule_path.read_text(encoding="utf-8") if rule_path.exists() else "", rule))]
        writes += copy_skills(vault, [config / "skills"])
        touched += [settings_path, rule_path]

    return writes, touched


def _validate_target(path: Path, home: Path) -> None:
    resolved_home = home.resolve()
    try:
        relative = path.relative_to(home)
    except ValueError as error:
        raise ValueError(f"global hedef kullanıcı kökü dışında: {path}") from error
    current = home
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"global hedef symlink üzerinden yönlendiriliyor: {current}")
    try:
        path.parent.resolve().relative_to(resolved_home)
    except ValueError as error:
        raise ValueError(f"global hedef kullanıcı kökü dışında çözülüyor: {path}") from error


def _write_bytes(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.restore.tmp")
    try:
        temporary.write_bytes(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_plan(
    writes: list[tuple[Path, str | None]],
    home: Path,
    backup: Path,
) -> bool:
    effective: list[tuple[Path, str | None]] = []
    for path, content in writes:
        _validate_target(path, home)
        if content is None:
            if path.exists() or path.is_symlink():
                effective.append((path, content))
        elif not path.is_file() or path.read_bytes() != content.encode("utf-8"):
            effective.append((path, content))
    if not effective:
        return False

    snapshots: dict[Path, tuple[bytes, int] | None] = {}
    created_directories: set[Path] = set()
    for path, _content in effective:
        parent = path.parent
        while parent != home and not parent.exists():
            created_directories.add(parent)
            parent = parent.parent
        if path in snapshots:
            continue
        if path.exists():
            if not path.is_file():
                raise ValueError(f"global hedef normal dosya değil: {path}")
            metadata = path.stat()
            snapshots[path] = (path.read_bytes(), metadata.st_mode & 0o777)
        else:
            snapshots[path] = None

    for path, snapshot in snapshots.items():
        if snapshot is None:
            continue
        destination = backup / path.relative_to(home)
        _write_bytes(destination, snapshot[0], 0o600)

    try:
        for path, content in effective:
            if content is None:
                path.unlink(missing_ok=True)
            else:
                write_text(path, content)
    except OSError:
        for path, snapshot in reversed(tuple(snapshots.items())):
            if snapshot is None:
                if path.is_file() or path.is_symlink():
                    path.unlink(missing_ok=True)
            else:
                _write_bytes(path, snapshot[0], snapshot[1])
        for directory in sorted(created_directories, key=lambda item: len(item.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, help="adı serbest olan ikinci beyin vault yolu")
    parser.add_argument("--home", required=True, type=Path, help="AI araçlarının kullanıcı kökü")
    parser.add_argument(
        "--antigravity-home",
        action="append",
        default=[],
        type=Path,
        help=(
            "Antigravity kurulacak ek kullanıcı kökü; windows-wsl profilinde Codex'in "
            "ortak .agents/skills kopyası da buraya yazılır; birden fazla verilebilir"
        ),
    )
    parser.add_argument("--providers", default="all", help="all veya virgülle: antigravity,codex,cursor,claude")
    parser.add_argument("--platform", choices=tuple(DEFAULT_PYTHON_COMMANDS), default="portable")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    vault = args.vault.expanduser().resolve()
    home = args.home.expanduser().resolve()
    providers = SUPPORTED if args.providers == "all" else tuple(dict.fromkeys(part.strip().lower() for part in args.providers.split(",") if part.strip()))
    unknown = set(providers) - set(SUPPORTED)
    if unknown:
        parser.error(f"bilinmeyen provider: {', '.join(sorted(unknown))}")
    if args.antigravity_home and "antigravity" not in providers:
        parser.error("--antigravity-home kullanmak için antigravity provider seçilmeli")
    if not (vault / ".beyin/instructions.md").is_file() or not (vault / ".beyin/skills").is_dir():
        parser.error("geçerli vault içinde .beyin/instructions.md ve .beyin/skills bulunmalı")
    homes: list[tuple[Path, tuple[str, ...]]] = [(home, providers)]
    seen_homes = {home}
    for candidate in args.antigravity_home:
        resolved = candidate.expanduser().resolve()
        if resolved not in seen_homes:
            homes.append((resolved, ("antigravity",)))
            seen_homes.add(resolved)
    shared_skill_homes: set[Path] = set()
    if args.platform == "windows-wsl" and "codex" in providers:
        candidates = [_user_home(), *args.antigravity_home]
        for candidate in candidates:
            resolved = candidate.expanduser().resolve()
            shared_skill_homes.add(resolved)
            if resolved not in seen_homes:
                homes.append((resolved, ()))
                seen_homes.add(resolved)
    for target_home, _target_providers in homes:
        if not target_home.is_dir():
            parser.error(f"kullanıcı kökü bulunamadı: {target_home}")

    plans: list[tuple[Path, list[tuple[Path, str | None]], bool]] = []
    try:
        for target_home, target_providers in homes:
            writes, _touched = build(vault, target_home, target_providers, args.platform)
            if target_home in shared_skill_homes and target_home != home:
                writes += copy_skills(vault, [target_home / ".agents/skills"])
            legacy_backup_root = target_home / LEGACY_GLOBAL_BACKUP_ROOT
            current_backup_root = target_home / ".respected-backups"
            plans.append(
                (
                    target_home,
                    writes,
                    legacy_backup_root.exists() and current_backup_root.exists(),
                )
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2
    print(f"vault: {vault} (adı: {vault.name})")
    print(f"provider'lar: {', '.join(providers)}")
    for target_home, writes, backup_conflict in plans:
        print(f"kullanıcı kökü: {target_home}")
        if backup_conflict:
            print(
                "UYARI: eski ve yeni yedek kökleri çakışıyor; ikisi de aynen korunacak: "
                f"{target_home / LEGACY_GLOBAL_BACKUP_ROOT} | "
                f"{target_home / '.respected-backups'}"
            )
        for path, _ in writes:
            print(f"yönetilecek: {path}")
    if not args.apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0
    if any(backup_conflict for _home, _writes, backup_conflict in plans):
        print(
            "hata: yedek kökleri için ayrı migration kararı gerekli; hiçbir dosya değişmedi",
            file=sys.stderr,
        )
        return 2
    for target_home, writes, _backup_conflict in plans:
        backup = target_home / ".respected-backups" / dt.datetime.now().strftime(
            "%Y%m%d-%H%M%S-%f"
        )
        try:
            changed = apply_plan(writes, target_home, backup)
        except (OSError, ValueError) as exc:
            print(
                f"yazma başarısız ({target_home}): {exc}; yedek: {backup}",
                file=sys.stderr,
            )
            return 3
        if changed:
            print(f"Global bağlantı kuruldu ({target_home}); yedek: {backup}")
        else:
            print(f"Global bağlantı zaten güncel ({target_home}); dosya ve yedek değişmedi.")
    if "codex" in providers:
        print(
            "Codex hook'larını Desktop'ta Ayarlar > Hooks üzerinden veya CLI'da "
            "/hooks ile inceleyip güven."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
