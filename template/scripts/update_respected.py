#!/usr/bin/env python3
"""Preview or transactionally update an already stamped Respected Brain vault."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Sequence
import uuid

from legacy_names import LEGACY_MANIFEST_SCRIPT, LEGACY_NAMESPACE, LEGACY_UPDATE_SCRIPT
from respected_manifest import (
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
CURRENT_TOOL_FILES = ("scripts/update_respected.py", "scripts/respected_manifest.py")
LEGACY_TOOL_FILES = (LEGACY_UPDATE_SCRIPT, LEGACY_MANIFEST_SCRIPT)


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
    return tuple(
        dict.fromkeys(
            (*GENERATED, *RUNTIME, *CURRENT_TOOL_FILES, ".beyin/config.json", *_skill_relatives())
        )
    )


def _validate_source() -> None:
    if not TEMPLATE.is_dir():
        raise UpdateError(
            "repo template klasörü yok; updater'ı Respected Brain checkout'undan çalıştır"
        )
    missing = [relative for relative in RUNTIME if not (TEMPLATE / relative).is_file()]
    missing.extend(relative for relative in CURRENT_TOOL_FILES if not (REPO / relative).is_file())
    if missing:
        raise UpdateError(f"repo template eksik managed dosya: {missing[0]}")


def _is_linklike(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(reparse and attributes & reparse)


def _safe_target(vault: Path, relative: str) -> Path:
    candidate_relative = Path(relative)
    if candidate_relative.is_absolute() or ".." in candidate_relative.parts:
        raise UpdateError(f"managed yol vault dışında: {relative}")
    current = vault
    for component in candidate_relative.parts:
        current = current / component
        if _is_linklike(current):
            raise UpdateError(f"managed hedef sembolik bağlantı/reparse point: {relative}")
    try:
        current.resolve(strict=False).relative_to(vault)
    except ValueError as error:
        raise UpdateError(f"managed yol vault dışında: {relative}") from error
    if current.exists() and not current.is_file():
        raise UpdateError(f"managed hedef normal dosya değil: {relative}")
    return current


def _legacy_owned(relative: str, content: bytes) -> bool:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    old_manifest = LEGACY_NAMESPACE + "_manifest"
    old_product = "Res" + "pot"
    if relative == LEGACY_UPDATE_SCRIPT:
        signatures = (
            "#!/usr/bin/env python3",
            old_product,
            f"from {old_manifest} import",
            "class UpdateError(RuntimeError)",
            "def update(",
            "argparse",
            "--apply",
        )
        return all(signature in text for signature in signatures)
    if relative == LEGACY_MANIFEST_SCRIPT:
        signatures = (
            old_product,
            "CORE_VERSION",
            "MULTI_VERSION",
            "GENERATED",
            "RUNTIME",
            "SKILL_DESTINATIONS",
        )
        return all(signature in text for signature in signatures)
    return False


def _validated_legacy_removals(vault: Path) -> tuple[str, ...]:
    removals: list[str] = []
    for relative in LEGACY_TOOL_FILES:
        path = _safe_target(vault, relative)
        if not path.exists():
            continue
        content = path.read_bytes()
        if not _legacy_owned(relative, content):
            raise UpdateError(f"eski managed dosyanın sahipliği doğrulanamadı: {relative}")
        removals.append(relative)
    return tuple(removals)


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
    for relative in (*managed_files(), *LEGACY_TOOL_FILES, ".beyin-multi-version"):
        _safe_target(vault, relative)
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


def _file_record(path: Path) -> dict[str, Any]:
    metadata = path.stat()
    return {
        "existed": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "mode": stat.S_IMODE(metadata.st_mode),
    }


def _backup_root(vault: Path) -> Path:
    identity = hashlib.sha256(str(vault).encode("utf-8")).hexdigest()[:16]
    root = Path.home() / ".respected" / "update-backups" / identity
    resolved_root = root.resolve(strict=False)
    if resolved_root == vault or resolved_root.is_relative_to(vault):
        raise UpdateError("transaction yedeği vault dışında olmalı")
    return root


def _create_backup(
    vault: Path,
    targets: tuple[str, ...],
    legacy_removals: tuple[str, ...],
) -> tuple[Path, set[str]]:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = _backup_root(vault) / f"{stamp}-{uuid.uuid4().hex[:8]}"
    existed: set[str] = set()
    records: dict[str, dict[str, Any]] = {}
    for relative in targets:
        source = _safe_target(vault, relative)
        if source.is_file():
            _atomic_copy(source, backup / relative)
            existed.add(relative)
            records[relative] = _file_record(source)
        else:
            records[relative] = {"existed": False, "sha256": None, "mode": None}
    _atomic_write(
        backup / "respected-update-manifest.json",
        json.dumps(
            {
                "vault": str(vault),
                "targets": records,
                "legacy_removals": sorted(legacy_removals),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    return backup, existed


def _directory_relatives(vault: Path) -> set[str]:
    directories: set[str] = set()
    for current, names, _files in os.walk(vault, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in names:
            path = current_path / name
            if not _is_linklike(path):
                directories.add(path.relative_to(vault).as_posix())
    return directories


def _restore(
    vault: Path,
    backup: Path,
    targets: tuple[str, ...],
    existed: set[str],
    original_directories: set[str],
) -> None:
    for relative in targets:
        destination = _safe_target(vault, relative)
        if destination.is_file():
            destination.unlink()
    for relative in sorted(existed):
        _atomic_copy(backup / relative, _safe_target(vault, relative))
    current_directories = _directory_relatives(vault)
    for relative in sorted(current_directories - original_directories, reverse=True):
        try:
            (vault / relative).rmdir()
        except OSError:
            pass


def _install_managed(vault: Path) -> None:
    for relative in RUNTIME:
        _atomic_copy(TEMPLATE / relative, vault / relative)
    for relative in CURRENT_TOOL_FILES:
        _atomic_copy(REPO / relative, vault / relative)
    for source in sorted((TEMPLATE / ".beyin" / "skills").glob("*/SKILL.md")):
        destination = vault / ".beyin" / "skills" / source.parent.name / "SKILL.md"
        _atomic_copy(source, destination)


def _create_stage(vault: Path, profile: str, requested_profile: str) -> tuple[Path, Path]:
    stage_container = Path(tempfile.mkdtemp(prefix="respected-update-"))
    if os.name != "nt":
        os.chmod(stage_container, 0o700)
    resolved_stage = stage_container.resolve()
    if resolved_stage == vault or resolved_stage.is_relative_to(vault):
        shutil.rmtree(stage_container, ignore_errors=True)
        raise UpdateError("transaction staging alanı vault dışında olmalı")
    stage = stage_container / "vault"
    stage.mkdir(mode=0o700)
    try:
        for relative in (".beyin/instructions.md", ".beyin/config.json"):
            _atomic_copy(vault / relative, stage / relative)
        _install_managed(stage)
        _prepare_config(stage, profile, requested_profile)
        _run_renderer(stage)
        _gate(stage, managed_files(), allow_test_failure=False)
    except BaseException:
        shutil.rmtree(stage_container, ignore_errors=True)
        raise
    return stage_container, stage


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


def _gate(vault: Path, relatives: tuple[str, ...], *, allow_test_failure: bool = True) -> None:
    if allow_test_failure and os.environ.get("RESPECTED_TEST_FAIL_GATE") == "render":
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
    legacy_removals = _validated_legacy_removals(vault)
    print(f"Respected Brain: {current_multi} -> {MULTI_VERSION}")
    print(f"platform: {profile}")
    print("yönetilen dosyalar:")
    for relative in relatives:
        print(f"  {relative}")
    if legacy_removals:
        print("doğrulanmış eski managed dosyalar kaldırılacak:")
        for relative in legacy_removals:
            print(f"  {relative}")
    if not apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0
    if current_multi == MULTI_VERSION:
        print("Bu vault zaten güncel.")
        return 3

    stage_container, stage = _create_stage(vault, profile, requested_profile)
    targets = tuple(dict.fromkeys((*relatives, *legacy_removals, ".beyin-multi-version")))
    original_directories = _directory_relatives(vault)
    backup: Path | None = None
    try:
        backup, existed = _create_backup(vault, targets, legacy_removals)
        for relative in relatives:
            _atomic_copy(stage / relative, _safe_target(vault, relative))
        _run_renderer(vault)
        for relative in legacy_removals:
            _safe_target(vault, relative).unlink()
        _gate(vault, relatives)
        _atomic_write(vault / ".beyin-multi-version", f"{MULTI_VERSION}\n")
    except (OSError, UnicodeError, ValueError, UpdateError) as error:
        if backup is None:
            raise UpdateError(f"update başlamadan durduruldu: {error}") from error
        try:
            _restore(vault, backup, targets, existed, original_directories)
        except OSError as rollback_error:
            raise UpdateError(
                f"update başarısız ({error}); rollback da başarısız ({rollback_error}); yedek: {backup}"
            ) from rollback_error
        raise UpdateError(f"update geri alındı: {error}; yedek: {backup}") from error
    finally:
        shutil.rmtree(stage_container, ignore_errors=True)

    print(f"Respected Brain güncellendi: multi-AI {MULTI_VERSION}; yedek: {backup}")
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
