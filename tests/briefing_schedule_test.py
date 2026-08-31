#!/usr/bin/env python3
"""Rendering and preview tests for morning briefing schedule adapters."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/install_briefing_schedule.py"


def load_installer():
    spec = importlib.util.spec_from_file_location("briefing_schedule_installer", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("schedule installer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BriefingScheduleTest(unittest.TestCase):
    def test_windows_native_task_is_missed_run_safe_and_provider_free(self):
        installer = load_installer()
        plan = installer.build_plan(
            PureWindowsPath(r"C:\Users\Ada\Ada Brain"), "windows-native", PureWindowsPath(r"C:\Users\Ada")
        )

        self.assertEqual(plan.kind, "windows-task")
        self.assertIn("<StartWhenAvailable>true</StartWhenAvailable>", plan.content)
        self.assertIn("T08:00:00", plan.content)
        self.assertIn("py.exe", plan.content)
        self.assertIn("Ada Brain", plan.content)
        for provider in ("claude", "codex", "cursor", "agy"):
            self.assertNotIn(provider, plan.content.casefold())

    def test_wsl_linux_and_macos_call_the_same_if_due_worker(self):
        installer = load_installer()
        cases = (
            ("windows-wsl", "wsl.exe", "StartWhenAvailable"),
            ("linux", "Persistent=true", "OnCalendar=*-*-* 08:00:00"),
            ("macos", "StartCalendarInterval", "RunAtLoad"),
        )
        for platform, first, second in cases:
            with self.subTest(platform=platform):
                plan = installer.build_plan(PurePosixPath("/mnt/c/Users/Ada/Ada Brain"), platform, PurePosixPath("/home/ada"))
                self.assertIn(first, plan.content)
                self.assertIn(second, plan.content)
                self.assertIn("morning_briefing.py", plan.content)
                self.assertIn("--if-due", plan.content)

    def test_plan_can_pin_python_and_provider_search_path_without_pinning_provider(self):
        installer = load_installer()
        plan = installer.build_plan(
            PurePosixPath("/home/ada/Ada Brain"),
            "linux",
            PurePosixPath("/home/ada"),
            python_executable="/usr/bin/python3",
            provider_path="/opt/respot-cli/bin:/usr/bin",
        )

        self.assertIn("/usr/bin/python3", plan.content)
        self.assertIn("--provider-path", plan.content)
        self.assertIn("/opt/respot-cli/bin:/usr/bin", plan.content)

    def test_preview_does_not_create_schedule_files(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            vault = Path(temporary) / "Ada Brain"
            (vault / ".beyin").mkdir(parents=True)

            output = io.StringIO()
            with redirect_stdout(output):
                result = installer.install(vault, "linux", home, apply=False)

            self.assertEqual(result, 0)
            self.assertEqual(list(home.rglob("*")), [])
            self.assertIn("ExecStart=", output.getvalue())
            self.assertIn(".service", output.getvalue())
            self.assertIn(".timer", output.getvalue())

    def test_linux_apply_reloads_and_rolls_back_definitions_on_activation_failure(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            vault = Path(temporary) / "Ada Brain"
            (vault / ".beyin").mkdir(parents=True)
            plan = installer.build_plan(vault, "linux", home, python_executable="/usr/bin/python3")
            service, timer = (Path(path) for path in plan.paths)
            service.parent.mkdir(parents=True)
            service.write_text("old-service\n", encoding="utf-8")
            timer.write_text("old-timer\n", encoding="utf-8")
            calls = []

            def command_stub(argv, **kwargs):
                calls.append(argv)
                if "is-enabled" in argv or "is-active" in argv:
                    return mock.Mock(returncode=1, stdout="", stderr="")
                return mock.Mock(returncode=2 if "enable" in argv else 0, stdout="", stderr="fail")

            with mock.patch.object(installer.subprocess, "run", side_effect=command_stub):
                result = installer.install(
                    vault,
                    "linux",
                    home,
                    apply=True,
                    python_executable="/usr/bin/python3",
                )

            self.assertEqual(result, 2)
            self.assertEqual(service.read_text(encoding="utf-8"), "old-service\n")
            self.assertEqual(timer.read_text(encoding="utf-8"), "old-timer\n")
            backups = list((home / ".respot/schedule-backups").rglob("*.service"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "old-service\n")
            self.assertGreaterEqual(
                sum("daemon-reload" in command for command in calls), 2
            )
            self.assertTrue(any("disable" in command for command in calls))
            self.assertTrue(any("stop" in command for command in calls))

    def test_linux_write_failure_restores_first_definition(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            vault = Path(temporary) / "Ada Brain"
            (vault / ".beyin").mkdir(parents=True)
            plan = installer.build_plan(vault, "linux", home)
            service, timer = (Path(path) for path in plan.paths)
            service.parent.mkdir(parents=True)
            service.write_text("old-service\n", encoding="utf-8")
            timer.write_text("old-timer\n", encoding="utf-8")
            real_write = installer._write
            writes = 0

            def failing_write(path, content):
                nonlocal writes
                if path in (service, timer):
                    writes += 1
                    if writes == 2:
                        raise OSError("second write failed")
                return real_write(path, content)

            with mock.patch.object(installer, "_write", side_effect=failing_write), mock.patch.object(
                installer.subprocess,
                "run",
                return_value=mock.Mock(returncode=1, stdout="", stderr=""),
            ):
                result = installer.install(vault, "linux", home, apply=True)

            self.assertEqual(result, 2)
            self.assertEqual(service.read_text(encoding="utf-8"), "old-service\n")
            self.assertEqual(timer.read_text(encoding="utf-8"), "old-timer\n")


if __name__ == "__main__":
    unittest.main()
