#!/usr/bin/env python3
"""Preview or transactionally update an already stamped Respot Brain vault."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence
import uuid

from respot_manifest import (
    CORE_VERSION,
    GENERATED,
    MULTI_VERSION,
    RUNTIME,
    SKILL_DESTINATIONS,
    UPDATABLE_MULTI_VERSIONS,
)


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "template"
PROFILES = ("portable", "windows-wsl", "windows-native")
DEFAULT_COMMANDS = {
    "portable": ["python3"],
    "windows-wsl": ["python3"],
    "windows-native": ["py.exe", "-3"],
}
SUMMARY_PROVIDERS = {"auto", "claude", "codex", "cursor", "antigravity"}


class UpdateError(RuntimeError):
    """A validation or transaction gate rejected the update."""


def _read_stamp(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, IndexError, UnicodeError):
        return ""


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdateError(f"geçersiz JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise UpdateError(f"JSON nesne olmalı: {path}")
    return value


def _atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.chmod(temporary, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _skill_relatives() -> tuple[str, ...]:
    relatives: list[str] = []
    for source in sorted((TEMPLATE / ".beyin" / "skills").glob("*/SKILL.md")):
        for destination in SKILL_DESTINATIONS:
            relatives.append(f"{destination}/{source.parent.name}/SKILL.md")
    return tuple(relatives)


def managed_files() -> tuple[str, ...]:
    return tuple(dict.fromkeys((*GENERATED, *RUNTIME, ".beyin/config.json", *_skill_relatives())))


def _validate_source() -> None:
    if not TEMPLATE.is_dir():
        raise UpdateError("repo template klasörü yok; updater'ı Respot Brain checkout'undan çalıştır")
    missing = [relative for relative in RUNTIME if not (TEMPLATE / relative).is_file()]
    if missing:
        raise UpdateError(f"repo template eksik managed dosya: {missing[0]}")


def _validate_target(vault: Path) -> tuple[str, str]:
    if not vault.is_dir() or vault == Path(vault.anchor):
        raise UpdateError(f"geçersiz vault yolu: {vault}")
    core = _read_stamp(vault / ".beyin-version")
    multi = _read_stamp(vault / ".beyin-multi-version")
    if core != CORE_VERSION:
        shown = core or "yok (unstamped/v1)"
        raise UpdateError(f"desteklenmeyen çekirdek sürümü: {shown}")
    if multi not in UPDATABLE_MULTI_VERSIONS:
        shown = multi or "yok"
        raise UpdateError(f"desteklenmeyen multi-AI sürümü: {shown}")
    if not (vault / ".beyin/instructions.md").is_file():
        raise UpdateError("kanonik .beyin/instructions.md yok")
    return core, multi


def _infer_profile(vault: Path, requested: str, config: dict[str, Any]) -> str:
    if requested != "auto":
        return requested
    persisted = config.get("platform")
    if persisted in PROFILES:
        return persisted
    if os.name == "nt":
        return "windows-native"
    in_wsl = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
    return "windows-wsl" if in_wsl and str(vault).startswith("/mnt/") else "portable"


def _prepare_config(vault: Path, profile: str, requested: str) -> None:
    path = vault / ".beyin/config.json"
    config = _load_object(path)
    config["platform"] = profile
    command = config.get("python_command")
    valid_command = (
        isinstance(command, list)
        and bool(command)
        and all(isinstance(part, str) and part for part in command)
    )
    if requested != "auto" or not valid_command:
        config["python_command"] = DEFAULT_COMMANDS[profile]
    _atomic_write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def _create_backup(vault: Path, relatives: tuple[str, ...]) -> tuple[Path, set[str]]:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = vault / ".beyin" / "backups" / f"{stamp}-{uuid.uuid4().hex[:8]}"
    existed: set[str] = set()
    for relative in relatives:
        source = vault / relative
        if source.is_file():
            _atomic_copy(source, backup / relative)
            existed.add(relative)
    _atomic_write(
        backup / "respot-update-manifest.json",
        json.dumps({"existed": sorted(existed)}, ensure_ascii=False, indent=2) + "\n",
    )
    return backup, existed


def _restore(vault: Path, backup: Path, relatives: tuple[str, ...], existed: set[str]) -> None:
    for relative in relatives:
        destination = vault / relative
        if destination.is_file() or destination.is_symlink():
            destination.unlink(missing_ok=True)
    for relative in sorted(existed):
        _atomic_copy(backup / relative, vault / relative)


def _install_managed(vault: Path) -> None:
    for relative in RUNTIME:
        _atomic_copy(TEMPLATE / relative, vault / relative)
    for source in sorted((TEMPLATE / ".beyin" / "skills").glob("*/SKILL.md")):
        destination = vault / ".beyin" / "skills" / source.parent.name / "SKILL.md"
        _atomic_copy(source, destination)


def _run_renderer(vault: Path, check: bool = False) -> None:
    command = [
        sys.executable,
        str(vault / "scripts/render_integrations.py"),
        "--root",
        str(vault),
    ]
    if check:
        command.append("--check")
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise UpdateError(f"adapter render gate başarısız: {detail}")


def _gate(vault: Path, relatives: tuple[str, ...]) -> None:
    if os.environ.get("RESPOT_TEST_FAIL_GATE") == "render":
        raise UpdateError("test render gate failure")
    _run_renderer(vault, check=True)
    for relative in relatives:
        if not (vault / relative).is_file():
            raise UpdateError(f"managed dosya gate eksik: {relative}")
    syntax_files = (
        ".beyin/runtime_platform.py",
        ".beyin/map_builder.py",
        ".beyin/morning_briefing.py",
        ".beyin/hooks/lifecycle.py",
        ".beyin/hooks/bridge.py",
        ".beyin/model_runner.py",
        ".claude/scripts/flush.py",
        ".claude/scripts/compile.py",
        "scripts/render_integrations.py",
        "scripts/install_briefing_schedule.py",
    )
    for relative in syntax_files:
        source = (vault / relative).read_text(encoding="utf-8")
        compile(source, str(vault / relative), "exec")
    for relative in (
        ".beyin/config.json",
        ".claude/settings.json",
        ".codex/hooks.json",
        ".cursor/hooks.json",
        ".agents/hooks.json",
    ):
        _load_object(vault / relative)
    config = _load_object(vault / ".beyin/config.json")
    if config.get("summary_provider") not in SUMMARY_PROVIDERS:
        raise UpdateError("summary_provider gate başarısız")
    if config.get("platform") not in PROFILES:
        raise UpdateError("platform gate başarısız")
    for relative in (
        ".beyin/instructions.md",
        "AGENTS.md",
        "CLAUDE.md",
        ".agents/rules/beyin.md",
        ".cursor/rules/beyin.mdc",
    ):
        if "{{" in (vault / relative).read_text(encoding="utf-8"):
            raise UpdateError(f"placeholder gate başarısız: {relative}")


def update(vault: Path, requested_profile: str, apply: bool) -> int:
    _validate_source()
    _core, current_multi = _validate_target(vault)
    config = _load_object(vault / ".beyin/config.json")
    profile = _infer_profile(vault, requested_profile, config)
    relatives = managed_files()
    print(f"Respot Brain: {current_multi} -> {MULTI_VERSION}")
    print(f"platform: {profile}")
    print("yönetilen dosyalar:")
    for relative in relatives:
        print(f"  {relative}")
    if not apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0
    if current_multi == MULTI_VERSION:
        print("Bu vault zaten güncel.")
        return 3

    backup, existed = _create_backup(vault, relatives)
    try:
        _install_managed(vault)
        _prepare_config(vault, profile, requested_profile)
        _run_renderer(vault)
        _gate(vault, relatives)
    except (OSError, UnicodeError, ValueError, UpdateError) as error:
        try:
            _restore(vault, backup, relatives, existed)
        except OSError as rollback_error:
            raise UpdateError(
                f"update başarısız ({error}); rollback da başarısız ({rollback_error}); yedek: {backup}"
            ) from rollback_error
        raise UpdateError(f"update geri alındı: {error}; yedek: {backup}") from error

    _atomic_write(vault / ".beyin-multi-version", f"{MULTI_VERSION}\n")
    print(f"Respot Brain güncellendi: multi-AI {MULTI_VERSION}; yedek: {backup}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path)
    parser.add_argument("--platform", choices=("auto", *PROFILES), default="auto")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    vault = args.vault.expanduser().resolve()
    try:
        return update(vault, args.platform, args.apply)
    except UpdateError as error:
        print(f"HATA: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
