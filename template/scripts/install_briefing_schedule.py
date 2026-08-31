#!/usr/bin/env python3
"""Preview or install the platform adapter for Respot's 08:00 briefing."""

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


class SchedulePlan:
    def __init__(self, kind: str, name: str, content: str, paths: tuple[PurePath, ...] = ()):
        self.kind = kind
        self.name = name
        self.content = content
        self.paths = paths


def _identifier(vault: PurePath) -> str:
    digest = hashlib.sha256(str(vault).encode("utf-8")).hexdigest()[:12]
    return f"respot-morning-briefing-{digest}"


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
Description=Respot morning briefing

[Service]
Type=oneshot
ExecStart={command}
"""
        timer = """[Unit]
Description=Run Respot morning briefing at 08:00

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
            service + "\n---RESPOT-TIMER---\n" + timer,
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
    return home / ".respot" / "schedule-backups" / name / timestamp


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
        python_executable or sys.executable,
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
        previous = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", plan.name, "/XML"],
            text=True,
            capture_output=True,
            check=False,
        )
        if previous.returncode == 0 and previous.stdout.strip() and previous.stdout != plan.content:
            backup = _backup_directory(home, plan.name)
            _write(backup / f"{plan.name}.xml", previous.stdout)
            print(f"backup: {backup}")
        with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-16", delete=False) as handle:
            handle.write(plan.content)
            xml_path = Path(handle.name)
        try:
            result = subprocess.run(
                ["schtasks.exe", "/Create", "/TN", plan.name, "/XML", str(xml_path), "/F"],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            xml_path.unlink(missing_ok=True)
        if result.returncode != 0:
            if previous.returncode == 0 and previous.stdout.strip():
                with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-16", delete=False) as handle:
                    handle.write(previous.stdout)
                    restore_xml = Path(handle.name)
                try:
                    subprocess.run(
                        ["schtasks.exe", "/Create", "/TN", plan.name, "/XML", str(restore_xml), "/F"],
                        check=False,
                    )
                finally:
                    restore_xml.unlink(missing_ok=True)
            print((result.stdout + result.stderr).strip(), file=sys.stderr)
            return 2
    elif plan.kind == "systemd-user":
        snapshot = _snapshot(plan.paths)
        service, timer = plan.content.split("\n---RESPOT-TIMER---\n", 1)
        unit = f"{plan.name}.timer"
        was_enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit], check=False
        ).returncode == 0
        was_active = subprocess.run(
            ["systemctl", "--user", "is-active", unit], check=False
        ).returncode == 0
        try:
            _persist_file_backups(
                home,
                plan,
                snapshot,
                {
                    Path(plan.paths[0]): service.encode("utf-8"),
                    Path(plan.paths[1]): timer.encode("utf-8"),
                },
            )
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
            return 2
    else:
        target = Path(plan.paths[0])
        snapshot = _snapshot(plan.paths)
        _persist_file_backups(
            home,
            plan,
            snapshot,
            {target: plan.content.encode("utf-8")},
        )
        _write(target, plan.content)
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(target)], check=False)
        result = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)], check=False
        )
        if result.returncode != 0:
            _restore(snapshot)
            if snapshot[target] is not None:
                subprocess.run(
                    ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)],
                    check=False,
                )
            return 2
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
