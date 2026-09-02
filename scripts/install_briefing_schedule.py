#!/usr/bin/env python3
"""Preview or install the platform adapter for Respected's 08:00 briefing."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import os
from pathlib import Path, PurePath
import shlex
import subprocess
import sys
import tempfile
from typing import Sequence
import xml.etree.ElementTree as ET


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from legacy_names import LEGACY_TASK_PREFIX  # noqa: E402


TASK_PREFIX = "respected-morning-briefing-"
TIMER_SEPARATOR = "\n---RESPECTED-TIMER---\n"


class SchedulePlan:
    def __init__(self, kind: str, name: str, content: str, paths: tuple[PurePath, ...] = ()):
        self.kind = kind
        self.name = name
        self.content = content
        self.paths = paths


def _identifier(vault: PurePath) -> str:
    digest = hashlib.sha256(str(vault).encode("utf-8")).hexdigest()[:12]
    return f"{TASK_PREFIX}{digest}"


def _legacy_identifier(vault: PurePath) -> str:
    digest = hashlib.sha256(str(vault).encode("utf-8")).hexdigest()[:12]
    return f"{LEGACY_TASK_PREFIX}{digest}"


def decode_windows_output(value: bytes) -> str:
    if value.startswith((b"\xff\xfe", b"\xfe\xff")):
        return value.decode("utf-16")
    for encoding in ("utf-8", "cp857"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _decode_windows_xml(value: bytes) -> str:
    if value.startswith((b"\xff\xfe", b"\xfe\xff")):
        return value.decode("utf-16")
    return value.decode("utf-8-sig")


def _task_signature(content: str) -> tuple[str, str, str]:
    root = ET.fromstring(content)
    values: dict[str, str] = {}
    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]
        if name in {"Command", "Arguments", "StartWhenAvailable"}:
            values[name] = (element.text or "").strip()
    return (
        values.get("Command", ""),
        values.get("Arguments", ""),
        values.get("StartWhenAvailable", ""),
    )


def _windows_xml(command: str, arguments: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><CalendarTrigger><StartBoundary>2026-01-01T08:00:00</StartBoundary><ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay><Enabled>true</Enabled></CalendarTrigger></Triggers>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT30M</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>{escape(command)}</Command><Arguments>{escape(arguments)}</Arguments></Exec></Actions>
</Task>
'''


def build_plan(
    vault: PurePath,
    platform: str,
    home: PurePath,
    python_executable: str | None = None,
    provider_path: str | None = None,
) -> SchedulePlan:
    name = _identifier(vault)
    worker_arguments = ["--if-due", "--vault-root", str(vault)]
    if provider_path:
        worker_arguments.extend(("--provider-path", provider_path))
    if platform == "windows-native":
        worker = vault / ".beyin" / "morning_briefing.py"
        executable = python_executable or "py.exe"
        prefix = [] if python_executable else ["-3"]
        arguments = subprocess.list2cmdline(prefix + [str(worker), *worker_arguments])
        return SchedulePlan("windows-task", name, _windows_xml(executable, arguments))
    if platform == "windows-wsl":
        executable = python_executable or sys.executable
        arguments = subprocess.list2cmdline(
            [
                "--cd",
                vault.as_posix(),
                executable,
                ".beyin/morning_briefing.py",
                "--if-due",
                "--vault-root",
                ".",
                *(["--provider-path", provider_path] if provider_path else []),
            ]
        )
        return SchedulePlan("windows-task", name, _windows_xml("wsl.exe", arguments))
    if platform == "linux":
        executable = python_executable or sys.executable
        command = shlex.join(
            [executable, str(vault / ".beyin/morning_briefing.py"), *worker_arguments]
        )
        service = f"""[Unit]
Description=Respected morning briefing

[Service]
Type=oneshot
ExecStart={command}
"""
        timer = """[Unit]
Description=Run Respected morning briefing at 08:00

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""
        root = home / ".config/systemd/user"
        return SchedulePlan(
            "systemd-user",
            name,
            service + TIMER_SEPARATOR + timer,
            (root / f"{name}.service", root / f"{name}.timer"),
        )
    if platform == "macos":
        executable = python_executable or sys.executable
        worker = str(vault / ".beyin/morning_briefing.py")
        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{name}</string>
<key>ProgramArguments</key><array>{''.join(f'<string>{escape(value)}</string>' for value in (executable, worker, *worker_arguments))}</array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
<key>RunAtLoad</key><true/>
</dict></plist>
'''
        return SchedulePlan("launch-agent", name, content, (home / "Library/LaunchAgents" / f"{name}.plist",))
    raise ValueError(f"unsupported-platform:{platform}")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _snapshot(paths: tuple[PurePath, ...]) -> dict[Path, tuple[bytes, int] | None]:
    snapshot: dict[Path, tuple[bytes, int] | None] = {}
    for raw_path in paths:
        path = Path(raw_path)
        snapshot[path] = (path.read_bytes(), path.stat().st_mode) if path.is_file() else None
    return snapshot


def _restore(snapshot: dict[Path, tuple[bytes, int] | None]) -> None:
    for path, previous in snapshot.items():
        if previous is None:
            path.unlink(missing_ok=True)
            continue
        content, mode = previous
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _backup_directory(home: Path, name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return home / ".respected" / "schedule-backups" / name / timestamp


def _persist_file_backups(
    home: Path,
    plan: SchedulePlan,
    snapshot: dict[Path, tuple[bytes, int] | None],
    desired: dict[Path, bytes],
) -> Path | None:
    changed = {
        path: previous[0]
        for path, previous in snapshot.items()
        if previous is not None and previous[0] != desired[path]
    }
    if not changed:
        return None
    backup = _backup_directory(home, plan.name)
    for path, content in changed.items():
        _write(backup / path.name, content.decode("utf-8"))
    print(f"backup: {backup}")
    return backup


def _persist_legacy_backups(
    home: Path,
    name: str,
    snapshot: dict[Path, tuple[bytes, int] | None],
) -> Path | None:
    existing = {path: previous[0] for path, previous in snapshot.items() if previous is not None}
    if not existing:
        return None
    backup = _backup_directory(home, name)
    for path, content in existing.items():
        _write(backup / path.name, content.decode("utf-8"))
    print(f"backup: {backup}")
    return backup


def _query_windows_task(name: str) -> tuple[subprocess.CompletedProcess[bytes], str | None]:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", name, "/XML"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return result, None
    try:
        return result, _decode_windows_xml(result.stdout)
    except UnicodeError:
        return result, None


def _windows_argument_path(path: Path) -> str:
    if os.name == "nt" or not os.environ.get("WSL_INTEROP"):
        return str(path)
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(path)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return str(path)
    converted = result.stdout.strip()
    return converted if result.returncode == 0 and converted else str(path)


def _create_windows_task(
    name: str,
    content: str,
    home: Path,
) -> subprocess.CompletedProcess[bytes]:
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".xml",
        encoding="utf-16",
        delete=False,
        dir=home,
    ) as handle:
        handle.write(content)
        xml_path = Path(handle.name)
    try:
        return subprocess.run(
            [
                "schtasks.exe",
                "/Create",
                "/TN",
                name,
                "/XML",
                _windows_argument_path(xml_path),
                "/F",
            ],
            capture_output=True,
            check=False,
        )
    finally:
        xml_path.unlink(missing_ok=True)


def _delete_windows_task(name: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", name, "/F"],
        capture_output=True,
        check=False,
    )


def _restore_windows_tasks(
    current_name: str,
    current_previous: str | None,
    legacy_name: str,
    legacy_previous: str | None,
    home: Path,
) -> None:
    _delete_windows_task(current_name)
    if current_previous is not None:
        _create_windows_task(current_name, current_previous, home)
    if legacy_previous is not None:
        _create_windows_task(legacy_name, legacy_previous, home)


def install(
    vault: Path,
    platform: str,
    home: Path,
    apply: bool,
    python_executable: str | None = None,
) -> int:
    plan = build_plan(
        vault,
        platform,
        home,
        python_executable,
        os.environ.get("PATH"),
    )
    print(f"platform: {platform}")
    print(f"schedule: {plan.name}")
    for path in plan.paths:
        print(f"target: {path}")
    print("definition:")
    print(plan.content.rstrip())
    if not apply:
        print("ÖNİZLEME: zamanlayıcı değiştirilmedi. Uygulamak için --apply ekle.")
        return 0
    if plan.kind == "windows-task":
        legacy_name = _legacy_identifier(vault)
        _previous_result, previous_xml = _query_windows_task(plan.name)
        _legacy_result, legacy_xml = _query_windows_task(legacy_name)
        if previous_xml is not None and previous_xml != plan.content:
            backup = _backup_directory(home, plan.name)
            _write(backup / f"{plan.name}.xml", previous_xml)
            print(f"backup: {backup}")
        if legacy_xml is not None:
            backup = _backup_directory(home, legacy_name)
            _write(backup / f"{legacy_name}.xml", legacy_xml)
            print(f"backup: {backup}")
        result = _create_windows_task(plan.name, plan.content, home)
        if result.returncode != 0:
            _restore_windows_tasks(
                plan.name,
                previous_xml,
                legacy_name,
                legacy_xml,
                home,
            )
            print(decode_windows_output(result.stdout + result.stderr).strip(), file=sys.stderr)
            return 2
        verified_result, verified_xml = _query_windows_task(plan.name)
        try:
            verified = verified_xml is not None and _task_signature(verified_xml) == _task_signature(plan.content)
        except (ET.ParseError, UnicodeError):
            verified = False
        if verified_result.returncode != 0 or not verified:
            _restore_windows_tasks(
                plan.name,
                previous_xml,
                legacy_name,
                legacy_xml,
                home,
            )
            detail = decode_windows_output(verified_result.stdout + verified_result.stderr).strip()
            print(detail or "yeni Windows görevi doğrulanamadı", file=sys.stderr)
            return 2
        if legacy_xml is not None:
            deleted = _delete_windows_task(legacy_name)
            if deleted.returncode != 0:
                _restore_windows_tasks(
                    plan.name,
                    previous_xml,
                    legacy_name,
                    legacy_xml,
                    home,
                )
                print(
                    decode_windows_output(deleted.stdout + deleted.stderr).strip(),
                    file=sys.stderr,
                )
                return 2
    elif plan.kind == "systemd-user":
        legacy_name = _legacy_identifier(vault)
        root = Path(plan.paths[0]).parent
        legacy_paths = (
            root / f"{legacy_name}.service",
            root / f"{legacy_name}.timer",
        )
        current_snapshot = _snapshot(plan.paths)
        legacy_snapshot = _snapshot(legacy_paths)
        snapshot = {**current_snapshot, **legacy_snapshot}
        service, timer = plan.content.split(TIMER_SEPARATOR, 1)
        unit = f"{plan.name}.timer"
        legacy_unit = f"{legacy_name}.timer"
        was_enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit], check=False
        ).returncode == 0
        was_active = subprocess.run(
            ["systemctl", "--user", "is-active", unit], check=False
        ).returncode == 0
        legacy_was_enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", legacy_unit], check=False
        ).returncode == 0
        legacy_was_active = subprocess.run(
            ["systemctl", "--user", "is-active", legacy_unit], check=False
        ).returncode == 0
        try:
            _persist_file_backups(
                home,
                plan,
                current_snapshot,
                {
                    Path(plan.paths[0]): service.encode("utf-8"),
                    Path(plan.paths[1]): timer.encode("utf-8"),
                },
            )
            _persist_legacy_backups(home, legacy_name, legacy_snapshot)
            _write(Path(plan.paths[0]), service)
            _write(Path(plan.paths[1]), timer)
            reload_result = subprocess.run(
                ["systemctl", "--user", "daemon-reload"], check=False
            )
            if reload_result.returncode != 0:
                raise OSError("systemd-daemon-reload-failed")
            result = subprocess.run(
                ["systemctl", "--user", "enable", "--now", unit], check=False
            )
            if result.returncode != 0:
                raise OSError("systemd-enable-failed")
            if subprocess.run(
                ["systemctl", "--user", "is-enabled", unit], check=False
            ).returncode != 0:
                raise OSError("systemd-current-verification-failed")
            if any(previous is not None for previous in legacy_snapshot.values()):
                disabled = subprocess.run(
                    ["systemctl", "--user", "disable", "--now", legacy_unit],
                    check=False,
                )
                if disabled.returncode != 0:
                    raise OSError("systemd-legacy-disable-failed")
                for path in legacy_paths:
                    path.unlink(missing_ok=True)
                if subprocess.run(
                    ["systemctl", "--user", "daemon-reload"], check=False
                ).returncode != 0:
                    raise OSError("systemd-legacy-reload-failed")
        except (OSError, UnicodeError):
            _restore(snapshot)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
            subprocess.run(
                ["systemctl", "--user", "enable" if was_enabled else "disable", unit],
                check=False,
            )
            subprocess.run(
                ["systemctl", "--user", "start" if was_active else "stop", unit],
                check=False,
            )
            subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "enable" if legacy_was_enabled else "disable",
                    legacy_unit,
                ],
                check=False,
            )
            subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "start" if legacy_was_active else "stop",
                    legacy_unit,
                ],
                check=False,
            )
            return 2
    else:
        target = Path(plan.paths[0])
        legacy_name = _legacy_identifier(vault)
        legacy_target = target.with_name(f"{legacy_name}.plist")
        current_snapshot = _snapshot(plan.paths)
        legacy_snapshot = _snapshot((legacy_target,))
        snapshot = {**current_snapshot, **legacy_snapshot}
        _persist_file_backups(
            home,
            plan,
            current_snapshot,
            {target: plan.content.encode("utf-8")},
        )
        _persist_legacy_backups(home, legacy_name, legacy_snapshot)
        _write(target, plan.content)
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(target)], check=False)
        result = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)], check=False
        )
        verified = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{plan.name}"], check=False
        )
        if result.returncode != 0 or verified.returncode != 0:
            _restore(snapshot)
            if current_snapshot[target] is not None:
                subprocess.run(
                    ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)],
                    check=False,
                )
            return 2
        if legacy_snapshot[legacy_target] is not None:
            subprocess.run(
                ["launchctl", "bootout", f"gui/{os.getuid()}", str(legacy_target)],
                check=False,
            )
            legacy_target.unlink(missing_ok=True)
    print("Sabah brifingi zamanlayıcısı kuruldu.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--platform", choices=("windows-native", "windows-wsl", "linux", "macos"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    vault = args.vault.expanduser().resolve()
    home = args.home.expanduser().resolve()
    if not (vault / ".beyin/morning_briefing.py").is_file():
        parser.error("vault içinde .beyin/morning_briefing.py bulunamadı")
    return install(vault, args.platform, home, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
