#!/usr/bin/env python3
"""Connect a Windows Antigravity profile to one Respot vault safely."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys


HOOK_NAME = "respot-brain"
BEGIN = "<!-- RESPOT-GLOBAL:BEGIN -->"
END = "<!-- RESPOT-GLOBAL:END -->"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _load_hooks(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("hooks.json bir JSON nesnesi değil")
    return value


def _managed_rule(vault: Path, windows_vault: str) -> str:
    instructions = (vault / ".beyin" / "instructions.md").read_text(encoding="utf-8").strip()
    return (
        f"{BEGIN}\n"
        "# Respot global ikinci beyin bağlantısı\n\n"
        f"Kalıcı hafıza vault'u: `{windows_vault}` (WSL: `{vault.as_posix()}`).\n"
        "Aşağıdaki göreceli hafıza yollarını aktif kod reposuna göre değil, bu vault köküne göre "
        "çöz. Proje kodunu kullanıcı istemedikçe hafıza vault'una taşıma.\n\n"
        f"{instructions}\n"
        f"{END}"
    )


def _merge_managed(existing: str, managed: str) -> str:
    has_begin = BEGIN in existing
    has_end = END in existing
    if has_begin != has_end:
        raise ValueError("GEMINI.md içinde yarım Respot yönetim bloğu var")
    if has_begin:
        start = existing.index(BEGIN)
        finish = existing.index(END, start) + len(END)
        return existing[:start] + managed + existing[finish:]
    separator = "\n\n" if existing.strip() else ""
    return existing.rstrip() + separator + managed + "\n"


def _windows_path(vault: Path) -> str:
    parts = vault.parts
    if len(parts) < 4 or parts[1] != "mnt" or len(parts[2]) != 1:
        raise ValueError("Windows Antigravity için vault /mnt/<sürücü>/... altında olmalı")
    drive = parts[2].upper()
    tail = "\\".join(parts[3:])
    return f"{drive}:\\{tail}"


def _hook_payload(vault: Path) -> dict:
    root = vault.as_posix()
    prefix = f'wsl.exe --cd "{root}" python3 .beyin/hooks/bridge.py --provider antigravity'
    return {
        "PreInvocation": [
            {"type": "command", "command": f"{prefix} --event start", "timeout": 15}
        ],
        "Stop": [
            {"type": "command", "command": f"{prefix} --event end", "timeout": 10}
        ],
    }


def _backup(paths: list[Path], backup: Path) -> None:
    for path in paths:
        if not path.is_file():
            continue
        destination = backup / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        os.chmod(destination, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, help="WSL'den görülen, adı serbest vault yolu")
    parser.add_argument(
        "--antigravity-home",
        required=True,
        type=Path,
        help="Windows kullanıcı kökü; ör. /mnt/c/Users/<ad>",
    )
    parser.add_argument("--apply", action="store_true", help="önizleme yerine değişiklikleri uygula")
    args = parser.parse_args()

    vault = args.vault.expanduser().resolve()
    home = args.antigravity_home.expanduser().resolve()
    if not (vault / ".beyin" / "instructions.md").is_file():
        parser.error("vault içinde .beyin/instructions.md bulunamadı")
    if not (vault / ".beyin" / "skills").is_dir():
        parser.error("vault içinde .beyin/skills bulunamadı")
    if not home.is_dir():
        parser.error(f"Antigravity kullanıcı kökü bulunamadı: {home}")

    config = home / ".gemini" / "config"
    hooks_path = config / "hooks.json"
    rule_path = home / ".gemini" / "GEMINI.md"
    skills_root = config / "skills"
    try:
        hooks = _load_hooks(hooks_path)
        existing_rule = rule_path.read_text(encoding="utf-8") if rule_path.exists() else ""
        windows_vault = _windows_path(vault)
        merged_rule = _merge_managed(existing_rule, _managed_rule(vault, windows_vault))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    hooks[HOOK_NAME] = _hook_payload(vault)
    skill_sources = sorted((vault / ".beyin" / "skills").glob("*/SKILL.md"))
    print(f"global rule: {rule_path}")
    print(f"global hooks: {hooks_path}")
    for source in skill_sources:
        print(f"global skill: {source.parent.name}")
    if not args.apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = config / "respot-backups" / stamp
    try:
        _backup([hooks_path, rule_path], backup)
        _write_text(hooks_path, json.dumps(hooks, ensure_ascii=False, indent=2) + "\n")
        _write_text(rule_path, merged_rule)
        for source in skill_sources:
            destination = skills_root / source.parent.name / "SKILL.md"
            _write_text(destination, source.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"yazma başarısız: {exc}; yedek: {backup}", file=sys.stderr)
        return 3
    print(f"Respot global Antigravity bağlantısı kuruldu; yedek: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
