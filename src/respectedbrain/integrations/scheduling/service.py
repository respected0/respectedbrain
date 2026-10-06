"""Readonly schedule definitions using stable UUID-bound launchers."""
from __future__ import annotations
import json
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
from xml.sax.saxutils import escape
from ..backend import ExternalChange, canonical_json, canonical_task_xml
from ..rendering import launch_argv, validate_profile, _Planner, _assert_owned_replacement
from respectedbrain.core.errors import OwnershipConflict
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
    for encoding in ("utf-8-sig", "utf-8", "cp857", "cp1254", "cp1252"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _parse_time(time_str: str) -> tuple[int, int]:
    parts = time_str.split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    return 8, 0


def _windows_xml(command: str, arguments: str, time_str: str = "08:00") -> str:
    h, m = _parse_time(time_str)
    formatted_time = f"{h:02d}:{m:02d}"
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><CalendarTrigger><StartBoundary>2026-01-01T{formatted_time}:00</StartBoundary><ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay><Enabled>true</Enabled></CalendarTrigger></Triggers>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT30M</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>{escape(command)}</Command><Arguments>{escape(arguments)}</Arguments></Exec></Actions>
</Task>
'''


def plan_schedule(ctx, profile, backend, *, time_str="08:00"):
    validate_profile(ctx, profile)
    name = "respected-morning-briefing-" + ctx.paths.vault_id
    argv = launch_argv(ctx, profile, "briefing")
    h, m = _parse_time(time_str)
    if profile.platform.startswith("windows"):
        xml = _windows_xml(argv[0], subprocess.list2cmdline(argv[1:]), time_str)
        after = canonical_task_xml(xml)
        before = backend.read("task", name)
        if before is not None:
            def executables(document):
                if document.get("tag") == "Exec":
                    return [{child["tag"]: child["text"] for child in document.get("children", [])}]
                return [item for child in document.get("children", []) for item in executables(child)]
            try:
                actions = executables(json.loads(before))
            except (ValueError, KeyError, TypeError):
                actions = []
            if actions != [{"Command": argv[0], "Arguments": subprocess.list2cmdline(argv[1:])}]:
                raise OwnershipConflict("Existing UUID task does not target the installed vault launcher")
        return (ExternalChange("task", name, before, after),)
    if sys.platform == "darwin":
        key = profile.user_home / "Library/LaunchAgents" / (name + ".plist")
        content = plistlib.dumps({"Label": name, "ProgramArguments": argv, "StartCalendarInterval": {"Hour": h, "Minute": m}, "RunAtLoad": True})
        native_key = "launchd:" + str(key)
        _assert_owned_replacement(ctx, _Planner(backend), key, content)
        return (ExternalChange("file", str(key), backend.read("file", str(key)), content), ExternalChange("task", native_key, backend.read("task", native_key), canonical_json({"loaded": True})))
    if not sys.platform.startswith("linux"):
        raise ValueError("Unsupported native scheduler")
    directory = profile.user_home / ".config/systemd/user"
    service = directory / (name + ".service")
    timer = directory / (name + ".timer")
    service_text = f"[Unit]\nDescription=Respected morning briefing\n\n[Service]\nType=oneshot\nExecStart={shlex.join(argv)}\n"
    timer_text = f"[Unit]\nDescription=Run Respected morning briefing at {h:02d}:{m:02d}\n\n[Timer]\nOnCalendar=*-*-* {h:02d}:{m:02d}:00\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n"
    native_key = "systemd:" + name + ".timer"
    planner = _Planner(backend)
    _assert_owned_replacement(ctx, planner, service, service_text.encode())
    _assert_owned_replacement(ctx, planner, timer, timer_text.encode())
    return (ExternalChange("file", str(service), backend.read("file", str(service)), service_text.encode()), ExternalChange("file", str(timer), backend.read("file", str(timer)), timer_text.encode()), ExternalChange("task", native_key, backend.read("task", native_key), canonical_json({"enabled": True, "active": True})))
