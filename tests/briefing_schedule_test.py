"""Native schedule planning, rollback and exact-registration protections."""
import json
from pathlib import Path
from unittest import TestCase, mock
from tests.foundation_integrations_test import IntegrationFixture
from tests.foundation_support import snapshot
from respectedbrain.integrations.backend import IntegrationProfile, ExternalChange, canonical_task_xml
from respectedbrain.integrations.scheduling import service as SCHEDULE
from respectedbrain.installation.transaction import Transaction
from respectedbrain.core.errors import FoundationError, OwnershipConflict

class BriefingScheduleTest(IntegrationFixture, TestCase):
    def native_plan(self, **kw):
        backend = mock.Mock()
        backend.read.return_value = None
        return SCHEDULE.plan_schedule(self.ctx, self.profile, backend, **kw)

    def test_windows_native_task_is_missed_run_safe_and_provider_free(self):
        row = self.native_plan()[0]
        text = row.after.decode()
        self.assertIn("IgnoreNew", text)
        self.assertIn("StartWhenAvailable", text)
        self.assertIn("PT30M", text)
        self.assertIn("respectedbrain.exe", text)
        self.assertNotIn("python", text)
        self.assertNotIn("--provider", text)

    def test_wsl_linux_and_macos_call_the_same_uuid_worker(self):
        backend = mock.Mock()
        backend.read.return_value = None
        for platform, native in (("windows-wsl", "win32"), ("posix", "linux"), ("posix", "darwin")):
            profile = IntegrationProfile(platform, ("/opt/respectedbrain",), self.home)
            with self.subTest(platform=native), mock.patch.object(SCHEDULE.sys, "platform", native), mock.patch("respectedbrain.integrations.rendering.subprocess.run", return_value=mock.Mock(returncode=0, stdout=self.wsl_registry_output())):
                rows = SCHEDULE.plan_schedule(self.ctx, profile, backend)
                text = " ".join(row.after.decode() for row in rows if row.after)
                self.assertIn("briefing", text)
                self.assertIn(self.ctx.paths.vault_id, text)
                self.assertNotIn(".py", text)
                self.assertNotIn("--provider", text)

    def test_plan_pins_explicit_launcher_without_pinning_provider(self):
        row = self.native_plan(time_str="09:35")[0]
        self.assertIn("09:35:00", row.after.decode())
        self.assertIn(str(self.app / "respectedbrain.exe").replace("\\", "\\\\"), row.after.decode())
        self.assertNotIn("codex", row.after.decode())

    def test_preview_does_not_create_schedule_files(self):
        before = snapshot(self.root)
        self.native_plan()
        self.assertEqual(snapshot(self.root), before)

    def test_linux_apply_reloads_and_rolls_back_definitions_on_activation_failure(self):
        backend = self.backend()
        unit = self.home / ".config/systemd/user/respected-test.timer"
        rows = [ExternalChange("file", str(unit), None, b"[Timer]\nPersistent=true\n"), ExternalChange("task", "systemd:respected-test.timer", None, b'{"enabled":true,"active":true}\n')]
        original_read = backend.read
        def read(kind, key):
            return None if kind == "task" else original_read(kind, key)
        with mock.patch.object(backend, "read", side_effect=read), mock.patch.object(backend, "_native_command", side_effect=FoundationError("activation-failure")) as command:
            with self.assertRaisesRegex(FoundationError, "activation-failure"):
                with Transaction(self.data, backend, vault_id=self.ctx.paths.vault_id) as tx:
                    for row in rows:
                        tx.apply_external(row)
                    tx.commit()
        self.assertFalse(unit.exists())
        self.assertEqual(command.call_args.args[0], ["systemctl", "--user", "daemon-reload"])

    def test_linux_write_failure_restores_first_definition(self):
        backend = self.backend()
        first = self.home / "units/new.service"
        second = self.home / "units/new.timer"
        original = backend._write
        def write(kind, key, content):
            if key == str(second) and content is not None:
                raise OSError("write-failure")
            return original(kind, key, content)
        with mock.patch.object(backend, "_write", side_effect=write):
            with self.assertRaisesRegex(OSError, "write-failure"):
                with Transaction(self.data, backend, vault_id=self.ctx.paths.vault_id) as tx:
                    tx.apply_external(ExternalChange("file", str(first), None, b"new"))
                    tx.apply_external(ExternalChange("file", str(second), None, b"new"))
                    tx.commit()
        self.assertFalse(first.parent.exists())

    def test_linux_plan_definitions_precede_activation(self):
        backend = mock.Mock()
        backend.read.return_value = None
        profile = IntegrationProfile("posix", ("/opt/respectedbrain",), self.home)
        with mock.patch.object(SCHEDULE.sys, "platform", "linux"):
            rows = SCHEDULE.plan_schedule(self.ctx, profile, backend)
        self.assertEqual([row.kind for row in rows], ["file", "file", "task"])
        self.assertTrue(rows[-1].key.startswith("systemd:"))
        self.assertIn("Persistent=true", rows[1].after.decode())

    def test_macos_plan_plist_precedes_bootstrap(self):
        backend = mock.Mock()
        backend.read.return_value = None
        profile = IntegrationProfile("posix", ("/opt/respectedbrain",), self.home)
        with mock.patch.object(SCHEDULE.sys, "platform", "darwin"):
            rows = SCHEDULE.plan_schedule(self.ctx, profile, backend)
        self.assertEqual([row.kind for row in rows], ["file", "task"])
        self.assertIn("RunAtLoad", rows[0].after.decode())
        self.assertTrue(rows[-1].key.startswith("launchd:"))

    def test_windows_oem_output_decoder_preserves_turkish_diagnostics(self):
        text = "Görev başarıyla kaydedildi."
        self.assertEqual(SCHEDULE.decode_windows_output(text.encode("cp857")), text)
        self.assertEqual(SCHEDULE.decode_windows_output(text.encode("utf-16")), text)

    def test_wsl_task_launches_validated_linux_launcher_and_translates_only_cwd(self):
        profile = IntegrationProfile("windows-wsl", ("/opt/Respected Brain/respectedbrain",), self.home)
        backend = mock.Mock()
        backend.read.return_value = None
        with mock.patch("respectedbrain.integrations.rendering.subprocess.run", return_value=mock.Mock(returncode=0, stdout=self.wsl_registry_output())):
            row = SCHEDULE.plan_schedule(self.ctx, profile, backend)[0]
        self.assertIn("wsl.exe", row.after.decode())
        self.assertIn("/opt/Respected Brain/respectedbrain", row.after.decode())
        self.assertNotIn("wslpath", row.after.decode())

    def test_non_wsl_windows_task_does_not_invoke_wslpath(self):
        with mock.patch("respectedbrain.integrations.rendering.subprocess.run") as run:
            self.native_plan()
        run.assert_not_called()

    def test_windows_before_snapshot_protects_a_concurrent_task_edit(self):
        backend = self.backend()
        planned = self.native_plan()[0]
        with mock.patch.object(backend, "read", return_value=b"user edit"), mock.patch.object(backend, "_write") as write:
            with self.assertRaises(OwnershipConflict):
                backend.apply(planned)
        write.assert_not_called()
