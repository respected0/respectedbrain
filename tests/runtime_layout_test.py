"""Public package entrypoints replace the retired source launchers."""
from __future__ import annotations
import contextlib
import importlib
import io
from pathlib import Path
import sys
import unittest
from unittest import mock
from respectedbrain import cli
from tests.foundation_integrations_test import IntegrationFixture
from tests.foundation_support import snapshot

ROOT = Path(__file__).resolve().parents[1]


class RuntimeLayoutTest(IntegrationFixture, unittest.TestCase):
    def test_public_commands_preserve_selected_uuid_and_exit_status(self):
        for command in ("repair", "uninstall", "dashboard"):
            with self.subTest(command=command), mock.patch.object(cli, "_dispatch", return_value=7) as dispatch:
                self.assertEqual(cli.main([command, "--vault-id", self.ctx.paths.vault_id]), 7)
                args = dispatch.call_args.args[0]
                self.assertEqual((args.command, args.vault_id), (command, self.ctx.paths.vault_id))

    def test_setup_accepts_explicit_vault_and_gui_mode(self):
        with mock.patch.object(cli, "_dispatch", return_value=4) as dispatch:
            self.assertEqual(cli.main(["setup", "--gui", "--vault", str(self.vault)]), 4)
        args = dispatch.call_args.args[0]
        self.assertEqual(args.vault, self.vault)
        self.assertTrue(args.gui)

    def test_importing_package_services_has_no_home_io_or_process_side_effect(self):
        for name in ("core.paths", "installation.setup", "installation.update", "installation.uninstall", "installation.wizard", "integrations.rendering"):
            before = list(sys.path)
            with self.subTest(name=name), mock.patch.object(Path, "home", side_effect=AssertionError("home lookup")), mock.patch.object(Path, "mkdir", side_effect=AssertionError("mkdir")), mock.patch("subprocess.run", side_effect=AssertionError("process")), contextlib.redirect_stdout(io.StringIO()) as stdout:
                importlib.reload(importlib.import_module("respectedbrain." + name))
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(sys.path, before)

    def test_project_renderer_keeps_notes_and_technical_state_separate(self):
        from respectedbrain.integrations.rendering import render_project_integrations
        before = snapshot(self.root)
        output = render_project_integrations(self.ctx, self.profile)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(len(output), 5)
        for value in output.values():
            self.assertIn(self.ctx.paths.vault_id.encode(), value)
            self.assertNotIn(b".py", value)

    def test_summary_configure_retains_provider_without_legacy_write(self):
        with mock.patch.object(cli, "_dispatch", return_value=0) as dispatch:
            self.assertEqual(cli.main(["configure", "--summary-provider", "cursor"]), 0)
        self.assertEqual(dispatch.call_args.args[0].summary_provider, "cursor")
        self.assertFalse((self.vault / ".beyin").exists())

    def test_migration_is_preview_unless_apply_is_explicit(self):
        argv = ["migrate", "--legacy-root", str(self.root / "old"), "--vault", str(self.vault)]
        for apply in (False, True):
            with self.subTest(apply=apply), mock.patch.object(cli, "_dispatch", return_value=2) as dispatch:
                self.assertEqual(cli.main(argv + (["--apply"] if apply else [])), 2)
                self.assertEqual(dispatch.call_args.args[0].apply, apply)

    def test_instruction_resources_point_to_canonical_instructions(self):
        from respectedbrain.core.resources import ResourceCatalog
        for relative in ("AGENTS.md", "CLAUDE.md", ".agents/rules/beyin.md", ".gemini/GEMINI.md", ".cursor/rules/beyin.mdc"):
            with self.subTest(relative=relative):
                text = ResourceCatalog().read_text("integrations/" + relative)
                self.assertIn("src/respectedbrain/resources/instructions/default.md", text)
                self.assertNotIn("runtime/instructions.md", text)
                self.assertNotIn("python scripts/", text)


if __name__ == "__main__":
    unittest.main()
