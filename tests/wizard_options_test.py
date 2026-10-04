"""CLI and headless UI preserve explicit setup choices through the action boundary."""
from functools import partial
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from respectedbrain import cli
from respectedbrain.core.config import ConfigStore
from respectedbrain.core.paths import Roots
from respectedbrain.installation import wizard
from respectedbrain.installation.transaction import OperationResult


class InlineThread:
    def __init__(self, *, target, daemon):
        self.target = target

    def start(self):
        self.target()


class WizardOptionsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.roots = Roots(self.directory / "app", self.directory / "data", self.directory / "default-vault")
        self.backend = object()
        self.vault = self.directory / "selected-vault"
        self.package = self.directory / "selected-package"
        self.store = ConfigStore(self.roots.data_root)
        self.store.update(lambda config: config.update(
            active_vault_id="saved",
            vaults={"saved": {"path": str(self.directory / "saved-vault"), "settings": {
                "USER_NAME": "Saved Name", "USER_BIO": "Saved biography", "COMPANION": "Saved Companion",
                "OS_NAME": "Saved OS", "platform": "windows-wsl", "user_home": str(self.directory / "home")}}},
            preferences={"summary_provider": "claude"},
            integrations={"global": True, "mcp": True, "schedule": True, "shortcut": True}))

    def make_wizard(self, **options):
        # Tcl variables are real; only display-dependent widgets are replaced.
        interpreter = tk.Tcl()
        with mock.patch.object(wizard.tk, "StringVar", partial(tk.StringVar, master=interpreter)), \
             mock.patch.object(wizard.tk, "BooleanVar", partial(tk.BooleanVar, master=interpreter)), \
             mock.patch.object(wizard.SetupWizard, "_build_ui"), \
             mock.patch.object(wizard.SetupWizard, "_on_mode_change"), \
             mock.patch.object(wizard.SetupWizard, "_log"):
            ui = wizard.SetupWizard(mock.Mock(), roots=self.roots, backend=self.backend, **options)
        ui.btn_action = mock.Mock()
        ui.progress = mock.Mock()
        ui._log = mock.Mock()
        ui._finish = mock.Mock()
        return ui

    def perform_action(self, ui):
        with mock.patch.object(wizard.threading, "Thread", InlineThread), \
             mock.patch.object(wizard, "run_action", return_value=OperationResult(True, "test", ())) as action:
            ui._start_action_thread()
        self.assertEqual(action.call_count, 1)
        return action.call_args

    def test_cli_gui_forwards_explicit_paths_profile_and_false_integrations(self):
        with mock.patch.object(cli, "application_roots", return_value=self.roots), \
             mock.patch("respectedbrain.integrations.backend.NativeBackend", return_value=self.backend), \
             mock.patch.object(wizard, "main", return_value=7) as launch:
            status = cli.main(["setup", "--gui", "--vault", str(self.vault), "--package", str(self.package),
                               "--user-name", "Ada", "--user-bio", "Architect", "--companion", "Atlas",
                               "--os-name", "AdaOS", "--summary-provider", "codex", "--platform", "posix",
                               "--no-global", "--mcp", "--no-schedule", "--no-shortcut"])
        self.assertEqual(status, 7)
        self.assertEqual(launch.call_args.kwargs, {
            "roots": self.roots, "backend": self.backend, "vault": self.vault, "package": self.package,
            "profile": {"USER_NAME": "Ada", "USER_BIO": "Architect", "COMPANION": "Atlas",
                        "OS_NAME": "AdaOS", "summary_provider": "codex", "platform": "posix"},
            "desired": {"global": False, "mcp": True, "schedule": False, "shortcut": False}})

    def test_cli_gui_leaves_unspecified_choices_for_saved_defaults(self):
        with mock.patch.object(cli, "application_roots", return_value=self.roots), \
             mock.patch("respectedbrain.integrations.backend.NativeBackend", return_value=self.backend), \
             mock.patch.object(wizard, "main", return_value=0) as launch:
            self.assertEqual(cli.main(["setup", "--gui", "--no-global"]), 0)
        self.assertEqual(launch.call_args.kwargs.get("desired"), {"global": False})
        self.assertEqual(launch.call_args.kwargs.get("profile"), {})

    def test_main_passes_selections_to_wizard(self):
        options = {"vault": self.vault, "package": self.package, "profile": {"USER_BIO": "Architect"},
                   "desired": {"global": False}}
        with mock.patch.object(wizard.tk, "Tk") as root, mock.patch.object(wizard, "SetupWizard") as construct:
            self.assertEqual(wizard.main(roots=self.roots, backend=self.backend, **options), 0)
        self.assertEqual(construct.call_args.args, (root.return_value,))
        self.assertEqual(construct.call_args.kwargs, {"roots": self.roots, "backend": self.backend, **options})
        root.return_value.mainloop.assert_called_once_with()

    def test_explicit_choices_override_saved_defaults_and_reach_install(self):
        profile = {"USER_NAME": "Ada", "COMPANION": "Atlas", "USER_BIO": "Architect", "OS_NAME": "AdaOS",
                   "summary_provider": "codex", "platform": "posix", "provider_fallback": False,
                   "user_home": str(self.directory / "selected-home")}
        ui = self.make_wizard(vault=self.vault, package=self.package, profile=profile,
                              desired={"global": False, "mcp": False, "shortcut": False})
        ui.mode_var.set("install")
        call = self.perform_action(ui)
        self.assertEqual(call.args, ("install", self.roots, self.vault))
        self.assertEqual(call.kwargs["package"], self.package)
        self.assertEqual(call.kwargs["profile"], profile)
        self.assertEqual(call.kwargs["desired"], {"global": False, "mcp": False, "schedule": True, "shortcut": False})

    def test_explicit_fresh_vault_does_not_inherit_active_vault_profile(self):
        ui = self.make_wizard(vault=self.vault)
        call = self.perform_action(ui)
        self.assertEqual(call.args, ("install", self.roots, self.vault))
        self.assertEqual(call.kwargs["profile"], {
            "USER_NAME": Path.home().name, "COMPANION": "Companion", "OS_NAME": "selected-vault",
            "USER_BIO": "", "summary_provider": "claude"})

    def test_explicit_registered_vault_uses_its_own_profile_before_overrides(self):
        self.store.update(lambda config: config["vaults"].update(second={
            "path": str(self.vault), "settings": {"USER_NAME": "Second Name", "COMPANION": "Second Companion",
                "OS_NAME": "Second OS", "USER_BIO": "Second biography", "platform": "posix",
                "user_home": str(self.directory / "second-home")}}))
        ui = self.make_wizard(vault=self.vault / "nested" / "..", profile={"USER_BIO": "Explicit biography"})
        call = self.perform_action(ui)
        self.assertEqual(call.args, ("modify", self.roots, self.vault))
        self.assertEqual(call.kwargs["profile"], {
            "USER_NAME": "Second Name", "COMPANION": "Second Companion", "OS_NAME": "Second OS",
            "USER_BIO": "Explicit biography", "platform": "posix",
            "user_home": str(self.directory / "second-home"), "summary_provider": "claude"})

    def test_modify_retains_hidden_saved_profile_and_uses_current_visible_choices(self):
        ui = self.make_wizard()
        ui.user_name_var.set("Edited Name")
        ui.companion_var.set("Edited Companion")
        ui.model_choice_var.set("gemini")
        ui.schedule_var.set(False)
        call = self.perform_action(ui)
        self.assertEqual(call.args[0], "modify")
        self.assertEqual(call.kwargs["profile"], {
            "USER_NAME": "Edited Name", "USER_BIO": "Saved biography", "COMPANION": "Edited Companion",
            "OS_NAME": "Saved OS", "platform": "windows-wsl", "user_home": str(self.directory / "home"),
            "summary_provider": "gemini"})
        self.assertFalse(call.kwargs["desired"]["schedule"])

    def test_edited_fresh_vault_path_drops_old_hidden_profile_at_action(self):
        ui = self.make_wizard()
        ui.vault_path_var.set(str(self.vault))
        ui.mode_var.set("install")
        ui.user_name_var.set("Edited Name")
        ui.companion_var.set("Edited Companion")
        ui.model_choice_var.set("codex")
        call = self.perform_action(ui)
        self.assertEqual(call.args, ("install", self.roots, self.vault))
        self.assertEqual(call.kwargs["profile"], {
            "USER_NAME": "Edited Name", "COMPANION": "Edited Companion", "OS_NAME": "selected-vault",
            "USER_BIO": "", "summary_provider": "codex"})

    def test_browsed_registered_vault_reads_current_hidden_settings_then_explicit_overrides(self):
        ui = self.make_wizard(profile={"USER_BIO": "Explicit biography", "platform": "posix"})
        self.store.update(lambda config: config["vaults"].update(second={
            "path": str(self.vault), "settings": {"OS_NAME": "Second OS", "USER_BIO": "Second biography",
                "platform": "windows-native", "user_home": str(self.directory / "second-home")}}))
        with mock.patch.object(wizard.filedialog, "askdirectory", return_value=str(self.vault)):
            ui._browse_vault()
        ui.user_name_var.set("Edited Name")
        ui.companion_var.set("Edited Companion")
        ui.model_choice_var.set("gemini")
        call = self.perform_action(ui)
        self.assertEqual(call.args, ("modify", self.roots, self.vault))
        self.assertEqual(call.kwargs["profile"], {
            "USER_NAME": "Edited Name", "COMPANION": "Edited Companion", "OS_NAME": "Second OS",
            "USER_BIO": "Explicit biography", "platform": "posix",
            "user_home": str(self.directory / "second-home"), "summary_provider": "gemini"})

    def test_explicit_empty_hidden_values_are_not_replaced_with_saved_values(self):
        ui = self.make_wizard(profile={"USER_BIO": "", "OS_NAME": ""})
        call = self.perform_action(ui)
        self.assertEqual(call.kwargs["profile"]["USER_BIO"], "")
        self.assertEqual(call.kwargs["profile"]["OS_NAME"], "")

    def test_update_uses_supplied_package_without_opening_picker(self):
        ui = self.make_wizard(package=self.package)
        ui.mode_var.set("update")
        with mock.patch.object(wizard.filedialog, "askdirectory") as picker:
            call = self.perform_action(ui)
        self.assertEqual(call.kwargs["package"], self.package)
        picker.assert_not_called()

    def test_update_prompts_for_package_when_unspecified(self):
        ui = self.make_wizard()
        ui.mode_var.set("update")
        with mock.patch.object(wizard.filedialog, "askdirectory", return_value=str(self.package)) as picker:
            call = self.perform_action(ui)
        self.assertEqual(call.kwargs["package"], self.package)
        picker.assert_called_once()


if __name__ == "__main__":
    unittest.main()
