"""Deterministic explicit-profile command rendering regressions."""
import json
from unittest import TestCase, mock
from pathlib import PureWindowsPath
from tests.foundation_integrations_test import IntegrationFixture
from tests.foundation_support import snapshot
from respectedbrain.integrations.backend import IntegrationProfile
from respectedbrain.integrations import rendering as RENDER

class ProfileRenderTest(IntegrationFixture, TestCase):
    def test_native_bridge_argv_preserves_a_spaced_windows_vault_as_one_argument(self):
        argv = RENDER.bridge_argv(self.ctx, self.profile, "codex", "start")
        self.assertEqual(argv[0], str(self.app / "respectedbrain.exe"))
        self.assertEqual(argv[argv.index("--vault-id") + 1], self.ctx.paths.vault_id)
        self.assertNotIn(str(self.vault), argv)
        self.assertNotIn(".py", " ".join(argv))

    def test_native_antigravity_hook_uses_stable_absolute_executable(self):
        argv = RENDER.bridge_argv(self.ctx, self.profile, "antigravity", "turn")
        self.assertTrue(__import__("pathlib").Path(argv[0]).is_absolute())
        self.assertEqual(argv[argv.index("--provider") + 1], "antigravity")
        self.assertEqual(argv[argv.index("--event") + 1], "turn")

    def test_portable_global_bridge_uses_explicit_uuid(self):
        profile = IntegrationProfile("posix", ("/opt/Respected Brain/respectedbrain",), self.home)
        argv = RENDER.bridge_argv(self.ctx, profile, "codex", "start", global_hook=True)
        self.assertEqual(argv[0], profile.launcher[0])
        self.assertIn("--global-hook", argv)
        self.assertIn(self.ctx.paths.vault_id, argv)
        self.assertIn("'/opt/Respected Brain/respectedbrain'", RENDER.command_text(profile, argv))

    def test_each_profile_renders_all_provider_adapters(self):
        for platform, launcher in (("windows-native", self.profile.launcher), ("windows-wsl", ("/opt/respectedbrain",)), ("posix", ("/opt/respectedbrain",))):
            with self.subTest(platform=platform), mock.patch.object(RENDER.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=self.wsl_registry_output())):
                profile = IntegrationProfile(platform, launcher, self.home)
                rows = RENDER.plan_integrations(self.ctx, profile, {"global": True}, self.backend())
                text = " ".join(row.after.decode() for row in rows if row.after and __import__("pathlib").Path(row.key).name in {"hooks.json", "settings.json", "config.toml"})
                for provider in ("antigravity", "gemini", "codex", "claude", "cursor"):
                    self.assertIn("--provider " + provider, text)
                self.assertNotIn(".beyin", text)
                self.assertNotIn("bridge.py", text)
                if platform == "windows-wsl":
                    self.assertIn("wsl.exe --cd", text)
                else:
                    self.assertNotIn("wsl.exe", text)

    def test_render_preview_is_deterministic_without_mutating_vault(self):
        before = snapshot(self.root)
        first = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        second = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        self.assertEqual(first, second)
        self.assertEqual(snapshot(self.root), before)

    def test_fresh_project_configs_use_the_same_uuid_launcher_without_global_hook(self):
        self.assertTrue(hasattr(RENDER, "render_project_integrations"))
        before = snapshot(self.root)
        artifacts = RENDER.render_project_integrations(self.ctx, self.profile)
        self.assertTrue({".claude/settings.json", ".codex/hooks.json", ".cursor/hooks.json", ".agents/hooks.json", ".gemini/settings.json"} <= set(artifacts))
        for key, content in artifacts.items():
            with self.subTest(key=key):
                json.loads(content)
                self.assertIn(self.ctx.paths.vault_id, content.decode())
                self.assertNotIn(".beyin", content.decode())
                self.assertNotIn("--global-hook", content.decode())
        self.assertEqual(snapshot(self.root), before)

    def test_wsl_executable_without_registered_uuid_fails_readonly(self):
        from respectedbrain.core.errors import OwnershipConflict
        profile = IntegrationProfile("windows-wsl", ("/opt/respectedbrain",), self.home)
        before = snapshot(self.root)
        with mock.patch.object(RENDER.subprocess, "run", side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=0, stdout="{}")]) as run:
            with self.assertRaisesRegex(OwnershipConflict, "vault register"):
                RENDER.validate_profile(self.ctx, profile)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(run.call_args.args[0], ["wsl.exe", "--", "/opt/respectedbrain", "vault", "list"])

    def test_wsl_existing_uuid_must_point_to_same_converted_vault(self):
        from respectedbrain.core.errors import OwnershipConflict
        profile = IntegrationProfile("windows-wsl", ("/opt/respectedbrain",), self.home)
        wrong = json.dumps({self.ctx.paths.vault_id: {"path": "/wrong/vault"}})
        with mock.patch.object(RENDER.subprocess, "run", side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=0, stdout=wrong)]):
            with self.assertRaises(OwnershipConflict):
                RENDER.validate_profile(self.ctx, profile)

    def test_wsl_matching_existing_uuid_is_accepted_without_registration_write(self):
        profile = IntegrationProfile("windows-wsl", ("/opt/respectedbrain",), self.home)
        registry = json.dumps({self.ctx.paths.vault_id: {"path": RENDER.wsl_path(self.vault)}})
        before = snapshot(self.root)
        with mock.patch.object(RENDER.subprocess, "run", side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=0, stdout=registry)]):
            RENDER.validate_profile(self.ctx, profile)
        self.assertEqual(snapshot(self.root), before)

    def test_installed_wsl_profile_wraps_linux_launcher_exactly_once(self):
        from respectedbrain.installation.common import installed_profile
        from respectedbrain.core.paths import Roots
        profile = installed_profile(Roots(self.app,self.data,self.vault), {"platform":"windows-wsl","user_home":str(self.home)})
        self.assertEqual(profile.launcher, ("respectedbrain",))
        with mock.patch.object(RENDER.subprocess, "run", return_value=mock.Mock(returncode=0,stdout=self.wsl_registry_output())):
            RENDER.validate_profile(self.ctx,profile)
        argv = RENDER.bridge_argv(self.ctx,profile,"cursor","prompt")
        self.assertEqual(argv.count("wsl.exe"),1)
        self.assertEqual(argv[3],"respectedbrain")
