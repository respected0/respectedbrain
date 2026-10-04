"""Retired source entrypoints delegate to the installed package without discovery."""
from __future__ import annotations
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest import mock
from tests.foundation_integrations_test import IntegrationFixture
from tests.foundation_support import snapshot

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    spec = importlib.util.spec_from_file_location("retired_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class RuntimeLayoutTest(IntegrationFixture, unittest.TestCase):
    def test_install_update_uninstall_wrappers_preserve_package_status_and_argv(self):
        for relative, command in (("installer/install.py", "setup"), ("installer/update.py", "update"), ("installer/uninstall.py", "uninstall"), ("runtime/scripts/update_respected.py", "update"), ("runtime/scripts/auto_updater.py", "update"), ("runtime/scripts/dashboard.py", "dashboard")):
            with self.subTest(relative=relative), mock.patch("respectedbrain.cli.main", return_value=7) as main:
                module = load(ROOT / relative)
                self.assertEqual(module.main(["--vault-id", self.ctx.paths.vault_id]), 7)
                main.assert_called_once_with([command, "--vault-id", self.ctx.paths.vault_id])

    def test_setup_wrapper_preserves_source_build_and_explicit_modes(self):
        with mock.patch("respectedbrain.cli.main", return_value=4) as main:
            module = load(ROOT / "setup.py")
            self.assertEqual(module.main(["--repair", "--vault", str(self.vault)]), 4)
            main.assert_called_once_with(["repair", "--vault", str(self.vault)])
        self.assertIn("setuptools", (ROOT / "setup.py").read_text(encoding="utf-8"))

    def test_importing_retired_adapters_has_no_path_home_io_or_process_side_effect(self):
        paths = ["installer/install.py", "installer/update.py", "installer/uninstall.py", "setup.py", "runtime/scripts/auto_updater.py", "runtime/scripts/setup_wizard.py", "runtime/scripts/runtime_hub.py", "runtime/runtime_hub.py", "runtime/scripts/render_integrations.py"]
        for relative in paths:
            before = list(sys.path)
            with self.subTest(relative=relative), mock.patch.object(Path, "home", side_effect=AssertionError("home lookup")), mock.patch.object(Path, "mkdir", side_effect=AssertionError("mkdir")), mock.patch("subprocess.run", side_effect=AssertionError("process")), contextlib.redirect_stdout(io.StringIO()) as stdout:
                load(ROOT / relative)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(sys.path, before)

    def test_render_and_scheduler_imports_are_same_package_service(self):
        from respectedbrain.integrations import rendering
        from respectedbrain.integrations.scheduling import service
        self.assertIs(load(ROOT / "runtime/scripts/render_integrations.py").plan_integrations, rendering.plan_integrations)
        self.assertIs(load(ROOT / "runtime/scripts/install_briefing_schedule.py").plan_schedule, service.plan_schedule)

    def test_project_renderer_keeps_notes_and_technical_state_separate(self):
        from respectedbrain.integrations.rendering import render_project_integrations
        before = snapshot(self.root)
        output = render_project_integrations(self.ctx, self.profile)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(len(output), 5)
        for value in output.values():
            self.assertIn(self.ctx.paths.vault_id.encode(), value)
            self.assertNotIn(b".py", value)

    def test_summary_wrapper_uses_configure_without_legacy_file_write(self):
        with mock.patch("respectedbrain.cli.main", return_value=0) as main:
            module = load(ROOT / "runtime/scripts/set_summary_provider.py")
            self.assertEqual(module.main(["cursor"]), 0)
            main.assert_called_once_with(["configure", "--summary-provider", "cursor"])
        self.assertFalse((self.vault / ".beyin").exists())

    def test_migration_wrapper_is_canonical_preview_unless_apply_explicit(self):
        argv = ["--legacy-root", str(self.root / "old"), "--vault", str(self.vault)]
        with mock.patch("respectedbrain.cli.main", return_value=2) as main:
            module = load(ROOT / "runtime/scripts/migrate_vault_to_runtime.py")
            self.assertEqual(module.main(argv), 2)
            main.assert_called_once_with(["migrate", *argv])

    def test_instruction_adapters_point_to_canonical_package_resource(self):
        paths = ("AGENTS.md", "CLAUDE.md", ".agents/rules/beyin.md", ".gemini/GEMINI.md", ".cursor/rules/beyin.mdc")
        for relative in paths:
            with self.subTest(relative=relative):
                packaged = (ROOT / "src/respectedbrain/resources/integrations" / relative).read_text(encoding="utf-8")
                self.assertIn("src/respectedbrain/resources/instructions/default.md", packaged)
                self.assertNotIn("runtime/instructions.md", packaged)
                self.assertNotIn("python scripts/", packaged)
                retired = (ROOT / "runtime/adapters" / relative).read_text(encoding="utf-8")
                self.assertIn("src/respectedbrain/resources/instructions/default.md", retired)
                self.assertLessEqual(len(retired.splitlines()), 15)
                self.assertNotIn("Sen Jarvis", retired)

    def test_old_scripts_are_small_delegates_and_immutable_payload_excludes_them(self):
        for relative in ("installer/install.py", "installer/update.py", "installer/uninstall.py", "runtime/scripts/install_global.py", "runtime/scripts/vault_mcp_server.py", "runtime/scripts/auto_updater.py", "runtime/scripts/respected_manifest.py"):
            with self.subTest(relative=relative):
                content = (ROOT / relative).read_text(encoding="utf-8")
                self.assertLessEqual(len(content.splitlines()), 40)
                self.assertNotIn("sys.path.insert", content)
                self.assertNotIn("shutil.copytree", content)
        source = (ROOT / "tools/build_installer.py").read_text(encoding="utf-8")
        self.assertNotIn("runtime/scripts", source)

if __name__ == "__main__":
    unittest.main()
