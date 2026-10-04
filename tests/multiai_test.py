#!/usr/bin/env python3
"""Tests for generated multi-AI adapters and safe migration."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import unittest
from unittest import mock
from types import SimpleNamespace
from contextlib import redirect_stdout
import io


from tests.foundation_integrations_test import IntegrationFixture
from tests.foundation_support import snapshot
from respectedbrain.integrations.backend import IntegrationProfile
from respectedbrain.integrations import rendering as RENDER
from respectedbrain.integrations.hooks import bridge as BRIDGE
from respectedbrain.providers import runner as MODEL_RUNNER

ROOT = Path(__file__).resolve().parents[1]
class MultiAITest(IntegrationFixture, unittest.TestCase):
    def test_generated_files_have_no_drift(self):
        first = RENDER.render_project_integrations(self.ctx, self.profile)
        self.assertEqual(first, RENDER.render_project_integrations(self.ctx, self.profile))

    def test_all_provider_configs_point_to_bridge(self):
        artifacts = RENDER.render_project_integrations(self.ctx, self.profile)
        for content in artifacts.values():
            self.assertIn("respectedbrain.exe hook", content.decode())
            self.assertIn(self.ctx.paths.vault_id, content.decode())
            self.assertNotIn("bridge.py", content.decode())

    def test_fresh_generated_adapters_expose_only_the_current_product_identity(self):
        artifacts = RENDER.render_project_integrations(self.ctx, self.profile)
        antigravity = json.loads(artifacts[".agents/hooks.json"])
        self.assertEqual(set(antigravity), {"respected-brain"})
        text = " ".join(value.decode() for value in artifacts.values())
        self.assertNotIn("res" + "pot", text.lower())

    def test_bridge_normalizes_provider_inputs_and_outputs(self):
        payload = BRIDGE.normalize("antigravity", {"conversationId": "abc", "transcriptPath": "/tmp/t.jsonl", "workspacePaths": ["/tmp/project"], "modelName": "gemini-test"}, vault_root=self.vault, home=self.home)
        self.assertEqual(payload["session_id"], "abc")
        self.assertEqual(payload["cwd"], "/tmp/project")
        self.assertEqual(payload["model"], "gemini-test")
        for provider, event, expected in (("antigravity", "end", {"decision": "stop"}), ("gemini", "turn", {}), ("cursor", "turn", {})):
            output = io.StringIO()
            with redirect_stdout(output):
                BRIDGE.output(provider, event, "")
            self.assertEqual(json.loads(output.getvalue()), expected)

    def test_antigravity_normalize_resolves_ide_then_cli_transcript(self):
        for product, session in (("antigravity-ide", "session-1"), ("antigravity-cli", "session-2")):
            transcript = self.home / ".gemini" / product / "brain" / session / ".system_generated/logs/transcript.jsonl"
            transcript.parent.mkdir(parents=True)
            transcript.write_text("{}\n", encoding="utf-8")
            payload = BRIDGE.normalize("antigravity", {"conversationId": session}, vault_root=self.vault, home=self.home)
            self.assertEqual(payload["transcript_path"], str(transcript))

    def test_antigravity_normalize_uses_stable_transcript_session_when_invocation_ids_change(self):
        transcript = self.home / ".gemini/antigravity-cli/brain/stable-session/.system_generated/logs/transcript.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("{}\n", encoding="utf-8")
        for session in ("invocation-one", "invocation-two"):
            payload = BRIDGE.normalize("antigravity", {"conversationId": session, "transcriptPath": str(transcript)}, vault_root=self.vault, home=self.home)
            self.assertEqual(payload["session_id"], "stable-session")

    def test_antigravity_transcript_discovery_is_safe_and_explicit_wins(self):
        payload = BRIDGE.normalize("antigravity", {"conversationId": "../escape"}, vault_root=self.vault, home=self.home)
        self.assertEqual(payload["transcript_path"], "")
        payload = BRIDGE.normalize("antigravity", {"conversationId": "valid", "transcriptPath": "/explicit/transcript.jsonl"}, vault_root=self.vault, home=self.home)
        self.assertEqual(payload["transcript_path"], "/explicit/transcript.jsonl")

    def test_codex_transcript_discovery_and_safety(self):
        transcript = self.home / ".codex/sessions/2026/10/rollout-codex-session.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("{}\n", encoding="utf-8")
        self.assertEqual(BRIDGE.resolve_codex_transcript("codex-session", self.home), str(transcript))
        self.assertEqual(BRIDGE.resolve_codex_transcript("../escape", self.home), "")
        self.assertEqual(BRIDGE.resolve_codex_transcript("codex-unknown", self.home), "")

    def test_bridge_dispatches_to_shared_lifecycle_without_shell_hooks(self):
        memory = self.vault / "🔮 850-Companion"
        memory.mkdir()
        (memory / "Last-Session.md").write_text("## Session: Bridge\nOrtak lifecycle bağlamı.\n## Previous\n", encoding="utf-8")
        with mock.patch.object(BRIDGE.LIFECYCLE, "_launch_flush"):
            response = BRIDGE.dispatch(self.ctx, provider="codex", event="start", argv=[], stdin=json.dumps({"session_id": "bridge-session"}))
        self.assertIn("Ortak lifecycle bağlamı.", response)
        key = BRIDGE.LIFECYCLE.session_key("bridge-session")
        self.assertEqual((self.ctx.paths.state_dir / ("prompt_count." + key)).read_text(encoding="utf-8").strip(), "0")
        self.assertFalse((self.vault / ".claude/hooks").exists())

    def test_global_bridge_distinguishes_windows_vault_and_external_paths(self):
        root = Path("C:/Users/Ada/Vault")
        self.assertTrue(BRIDGE.inside_vault(r"C:\Users\Ada\Vault", root))
        self.assertTrue(BRIDGE.inside_vault(r"C:\Users\Ada\Vault\nested", root))
        self.assertFalse(BRIDGE.inside_vault(r"C:\Projects\unrelated", root))
        self.assertFalse(BRIDGE.inside_vault("relative-project", root))

    def test_runner_has_windows_user_local_agy_discovery(self):
        from respectedbrain.providers import runner
        with mock.patch.object(Path,"is_file",return_value=True):
            executable=runner._windows_vault_binary("agy",Path("/mnt/c/Users/Ada/Vault"))
        self.assertEqual(Path(executable),Path("/mnt/c/Users/Ada/AppData/Local/agy/bin/agy.exe"))

    def test_runner_supports_cursor_headless(self):
        runner = MODEL_RUNNER
        with mock.patch.object(runner.shutil, "which", side_effect=lambda name: "/bin/cursor-agent" if name == "cursor-agent" else None):
            invocation = runner._command("cursor", "özetle", "text")
        self.assertEqual(
            invocation.argv,
            ["/bin/cursor-agent", "-p", "--output-format", "text", "özetle"],
        )
        self.assertIsNone(invocation.stdin)

    def test_runner_supports_gemini_headless_without_putting_prompt_in_argv(self):
        runner = MODEL_RUNNER
        prompt = "ö" * 100_000
        with mock.patch.object(
            runner.shutil,
            "which",
            side_effect=lambda name: "/bin/gemini" if name == "gemini" else None,
        ):
            invocation = runner._command("gemini", prompt, "text")

        self.assertNotIn(prompt, invocation.argv)
        self.assertEqual(invocation.stdin, prompt)
        self.assertEqual(invocation.argv, ["/bin/gemini", "--output-format", "json", "-p", ""])

    def test_runner_keeps_codex_and_antigravity_prompts_on_stdin(self):
        runner = MODEL_RUNNER
        prompt = "ö" * 100_000

        def which(name):
            return {
                "codex": "/bin/codex",
                "agy": "/mnt/c/Users/Ada/AppData/Local/agy/bin/agy.exe",
            }.get(name)

        with mock.patch.object(runner.shutil, "which", side_effect=which):
            codex = runner._command("codex", prompt, "text")
            agy_text = runner._command("antigravity", prompt, "text")
            agy_workspace = runner._command("antigravity", prompt, "workspace")

        self.assertNotIn(prompt, codex.argv)
        self.assertEqual(codex.stdin, prompt)
        self.assertEqual(codex.argv[-1], "-")
        self.assertIn("--skip-git-repo-check", codex.argv)

        # Antigravity MUST keep prompt on stdin to prevent Windows 32K command-line limit (lpCommandLine)
        self.assertNotIn(prompt, agy_text.argv)
        self.assertNotIn(prompt, agy_workspace.argv)
        self.assertNotIn("--print", agy_text.argv)
        self.assertNotIn("--print", agy_workspace.argv)

        parsed_text_stdin = json.loads(agy_text.stdin)
        self.assertEqual(parsed_text_stdin["event"], "user")
        self.assertEqual(parsed_text_stdin["message"]["content"], prompt)

        parsed_ws_stdin = json.loads(agy_workspace.stdin)
        self.assertEqual(parsed_ws_stdin["event"], "user")
        self.assertEqual(parsed_ws_stdin["message"]["content"], prompt)

        self.assertIn("--input-format", agy_text.argv)
        self.assertIn("stream-json", agy_text.argv)
        self.assertIn("--output-format", agy_text.argv)
        self.assertIn("stream-json", agy_text.argv)
        self.assertIn("--sandbox", agy_text.argv)
        self.assertNotIn("--mode", agy_text.argv)
        self.assertIn("--mode", agy_workspace.argv)
        self.assertIn("accept-edits", agy_workspace.argv)
        self.assertIn("--dangerously-skip-permissions", agy_text.argv)
        self.assertIn("--dangerously-skip-permissions", agy_workspace.argv)
        self.assertTrue(agy_workspace.windows_executable)

    def test_runner_extracts_stream_json_response_and_errors(self):
        runner = MODEL_RUNNER
        stream_success = (
            '{"event":"init","init":{}}\n'
            '{"event":"step_update","step_update":{}}\n'
            '{"event":"result","result":{"status":"SUCCESS","response":"özet başarıyla tamamlandı"}}\n'
        )
        stream_error = (
            '{"event":"init","init":{}}\n'
            '{"event":"result","result":{"status":"ERROR","error":"model-overloaded"}}\n'
        )
        plain_text = "düz metin çıktısı"

        resp, err = runner._extract_response(stream_success, "antigravity")
        self.assertEqual(resp, "özet başarıyla tamamlandı")
        self.assertIsNone(err)

        resp, err = runner._extract_response(stream_error, "antigravity")
        self.assertEqual(resp, "")
        self.assertEqual(err, "model-overloaded")

        resp, err = runner._extract_response(plain_text, "claude")
        self.assertEqual(resp, "düz metin çıktısı")
        self.assertIsNone(err)

        resp, err = runner._extract_response(plain_text, "antigravity")
        self.assertEqual(resp, "düz metin çıktısı")
        self.assertIsNone(err)

        resp, err = runner._extract_response(
            '{"response":"Gemini özeti","stats":{},"error":null}',
            "gemini",
        )
        self.assertEqual(resp, "Gemini özeti")
        self.assertIsNone(err)

        resp, err = runner._extract_response(
            '{"response":null,"error":{"message":"quota exceeded"}}',
            "gemini",
        )
        self.assertEqual(resp, "")
        self.assertEqual(err, "quota exceeded")

    def test_runner_candidate_order_contract_is_unchanged(self):
        runner = MODEL_RUNNER
        with mock.patch.object(runner, "_configured_provider", return_value="auto"):
            self.assertEqual(
                runner._available("antigravity", {}),
                ["antigravity", "claude", "codex", "gemini", "cursor"],
            )
        with mock.patch.object(runner, "_configured_provider", return_value="cursor"):
            self.assertEqual(
                runner._available("antigravity", {}),
                ["cursor", "antigravity", "claude", "codex", "gemini"],
            )

    def test_wsl_windows_cli_receives_translatable_profile_environment(self):
        runner = MODEL_RUNNER
        invocation = runner.Invocation(
            ["/mnt/c/bin/agy.exe", "--print"],
            "prompt",
            True,
        )
        completed = SimpleNamespace(returncode=0, stdout="özet", stderr="")
        base = {
            "WSL_INTEROP": "/run/WSL/1_interop",
            "WSLENV": "PATH/l:KEEP:USERPROFILE",
        }
        cwd = Path("/mnt/c/Users/Ada/AppData/Local/Temp/stage")
        with mock.patch.dict(runner.os.environ, base, clear=True), mock.patch.object(
            runner,
            "_command",
            return_value=invocation,
        ), mock.patch.object(
            runner,
            "_available",
            return_value=["antigravity"],
        ), mock.patch.object(
            runner.subprocess,
            "run",
            return_value=completed,
        ) as called:
            result = runner.run_model("prompt", cwd, "text", 10, ctx=self.ctx)

        self.assertEqual(result, ("özet", None, "antigravity"))
        environment = called.call_args.kwargs["env"]
        self.assertEqual(environment["USERPROFILE"], "/mnt/c/Users/Ada")
        self.assertEqual(
            environment["LOCALAPPDATA"],
            "/mnt/c/Users/Ada/AppData/Local",
        )
        self.assertEqual(
            environment["APPDATA"],
            "/mnt/c/Users/Ada/AppData/Roaming",
        )
        entries = environment["WSLENV"].split(":")
        self.assertEqual(entries.count("USERPROFILE/p"), 1)
        self.assertIn("LOCALAPPDATA/p", entries)
        self.assertIn("APPDATA/p", entries)
        self.assertIn("KEEP", entries)

    @unittest.skipUnless(os.name == "nt", "native Windows only")
    def test_native_codex_child_receives_profile_codex_home_without_parent_stat(self):
        runner = MODEL_RUNNER
        invocation = runner.Invocation(["codex.exe", "exec", "-"], "prompt", True)
        completed = SimpleNamespace(returncode=0, stdout="özet", stderr="")
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile"
            codex_home = profile / ".codex"
            with mock.patch.dict(
                runner.os.environ,
                {"USERPROFILE": str(profile)},
                clear=True,
            ), mock.patch.object(
                runner,
                "_command",
                return_value=invocation,
            ), mock.patch.object(
                runner,
                "_available",
                return_value=["codex"],
            ), mock.patch.object(
                runner.subprocess,
                "run",
                return_value=completed,
            ) as called:
                result = runner.run_model("prompt", ROOT, "text", 10, preferred="codex", ctx=self.ctx)

        self.assertEqual(result, ("özet", None, "codex"))
        self.assertEqual(called.call_args.kwargs["env"].get("CODEX_HOME"), str(codex_home))

    def test_wsl_windows_cli_falls_back_to_windows_temp_when_cwd_is_linux_path(self):
        runner = MODEL_RUNNER
        invocation = runner.Invocation(
            ["/mnt/c/bin/agy.exe", "--print"],
            "prompt",
            True,
        )
        completed = SimpleNamespace(returncode=0, stdout="özet", stderr="")
        linux_cwd = Path("/tmp/wsl_only_scratch")
        mock_fallback = mock.MagicMock()
        mock_fallback.is_dir.return_value = True

        with mock.patch.dict(runner.os.environ, {"WSL_INTEROP": "/run/WSL/1_interop"}, clear=True), mock.patch.object(
            runner,
            "_command",
            return_value=invocation,
        ), mock.patch.object(
            runner,
            "_available",
            return_value=["antigravity"],
        ), mock.patch.object(
            runner.runtime_platform,
            "external_temp_parent",
            return_value=mock_fallback,
        ), mock.patch.object(
            runner.subprocess,
            "run",
            return_value=completed,
        ) as called:
            result = runner.run_model("prompt", linux_cwd, "text", 10, ctx=self.ctx)

        self.assertEqual(result, ("özet", None, "antigravity"))
        self.assertIs(called.call_args.kwargs["cwd"], mock_fallback)

    def test_wsl_windows_cli_retains_windows_cwd_when_already_under_windows_root(self):
        runner = MODEL_RUNNER
        invocation = runner.Invocation(
            ["/mnt/c/bin/agy.exe", "--print"],
            "prompt",
            True,
        )
        completed = SimpleNamespace(returncode=0, stdout="özet", stderr="")
        win_cwd = Path("/mnt/c/Users/Ada/Documents/AdaBrain")

        with mock.patch.dict(runner.os.environ, {"WSL_INTEROP": "/run/WSL/1_interop"}, clear=True), mock.patch.object(
            runner,
            "_command",
            return_value=invocation,
        ), mock.patch.object(
            runner,
            "_available",
            return_value=["antigravity"],
        ), mock.patch.object(
            runner.subprocess,
            "run",
            return_value=completed,
        ) as called:
            result = runner.run_model("prompt", win_cwd, "text", 10, ctx=self.ctx)

        self.assertEqual(result, ("özet", None, "antigravity"))
        self.assertEqual(called.call_args.kwargs["cwd"], win_cwd)

    def test_summary_provider_can_be_persisted_and_overrides_current_agent(self):
        from respectedbrain.core.config import ConfigStore
        store=ConfigStore(self.data)
        store.update(lambda config:config["preferences"].update(summary_provider="cursor"))
        self.assertEqual(store.read()["preferences"]["summary_provider"],"cursor")
        from respectedbrain.providers import runner
        with mock.patch.object(runner,"_configured_provider",return_value="cursor"):
            self.assertEqual(runner._available("codex",store.read()["preferences"])[:2],["cursor","codex"])
        self.assertFalse((self.vault / ".beyin").exists())

    def test_public_docs_describe_provider_neutral_setup(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        setup = (ROOT / "docs/guides/SETUP.md").read_text(encoding="utf-8")
        for required in ("Codex", "Cursor", "Antigravity", "Gemini", "configure --summary-provider", "Kasa adı", "respectedbrain/resources/"):
            self.assertIn(required, readme)
        self.assertIn("kapalıdır", setup)
        self.assertIn("kapalı tercihleri açmaz", setup)
        self.assertIn("doğrulanmış dağıtım", setup)
        self.assertIn("Mevcut dolu kasaya fresh template uygulanmaz", setup)
        self.assertNotIn("Claude aboneliğinin", setup)
        self.assertNotIn("claude CLI YOK", setup)

    def test_public_spec_and_template_have_no_stale_claude_only_setup(self):
        paths = (
            ROOT / "docs/SPECIFICATION.md",
            ROOT / "docs/ARCHITECTURE.md",
            ROOT / "README.md",
            ROOT / "docs/guides/MULTI_AI.md",
            ROOT / "src/respectedbrain/resources/vault-template/🎯 100-Command-Center/Dashboard.md",
            ROOT / "src/respectedbrain/resources/vault-template/🔮 850-Companion/Last-Session.md",
        )
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for stale in (
            "github.com/avenoxai/avenoxbeyin.git",
            "raw.githubusercontent.com/avenoxai",
            "claude CLI YOK",
            "mevcut Claude aboneliğinin",
            "terminal aç ve `claude` çalıştır",
            "with Claude Code",
        ):
            self.assertNotIn(stale, text)
        for required in (
            "summary_provider",
            "WSL",
            "Antigravity",
            "Codex",
        ):
            self.assertIn(required, text)

    def test_public_docs_define_all_three_profiles_and_native_limits(self):
        paths = (
            ROOT / "README.md",
            ROOT / "docs/guides/SETUP.md",
            ROOT / "docs/guides/MULTI_AI.md",
            ROOT / "docs/guides/SETUP-WINDOWS.md",
            ROOT / "docs/SPECIFICATION.md",
            ROOT / "docs/ARCHITECTURE.md",
        )
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for required in (
            "Linux", "macOS", "Native Windows", "WSL",
            "Python 3.10+", "kendi çalışma ortamını içerir",
            "RESPECTED_DATA_DIR", "RESPECTED_APP_DIR",
            "salt okunur", "fiziksel macOS/Linux/WSL kanıtı sayılmaz",
        ):
            self.assertIn(required, text)

    def test_runner_falls_back_only_for_retryable_provider_errors(self):
        runner = MODEL_RUNNER
        commands = {
            "antigravity": runner.Invocation(["agy"], None),
            "claude": runner.Invocation(["claude"], "prompt"),
        }
        with mock.patch.object(runner, "_available", return_value=["antigravity", "claude"]), \
             mock.patch.object(runner, "_command", side_effect=lambda provider, prompt, mode, vault_root=None: commands[provider]), \
             mock.patch.object(runner.subprocess, "run", side_effect=[
                 SimpleNamespace(returncode=1, stdout="", stderr="429 quota exceeded"),
                 SimpleNamespace(returncode=0, stdout="özet", stderr=""),
             ]):
            output, error, provider = runner.run_model("prompt", ROOT, "text", 10, preferred="antigravity", ctx=self.ctx)
        self.assertEqual((output, error, provider), ("özet", None, "claude"))

        with mock.patch.object(runner, "_available", return_value=["antigravity", "claude"]), \
             mock.patch.object(runner, "_command", side_effect=lambda provider, prompt, mode, vault_root=None: commands[provider]), \
             mock.patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="authentication failed")) as run:
            output, error, provider = runner.run_model("prompt", ROOT, "text", 10, preferred="antigravity", ctx=self.ctx)
            self.assertEqual((output, error, provider), (None, "antigravity-exit-1:auth", "antigravity"))
        self.assertEqual(run.call_count, 1)

    def test_locked_summary_provider_does_not_append_fallback_candidates(self):
        """A non-auto provider is the wizard's fail-fast single-model contract."""
        from respectedbrain.providers import runner
        preferences={"summary_provider":"codex","provider_priority":["codex"],"provider_fallback":False}
        self.assertEqual(runner._available(None,preferences),["codex"])

    def test_runner_auto_mode_falls_back_across_all_providers_on_failure(self):
        runner = MODEL_RUNNER
        commands = {
            "claude": runner.Invocation(["claude"], "prompt"),
            "codex": runner.Invocation(["codex"], "prompt"),
        }
        with mock.patch.object(runner, "_configured_provider", return_value="auto"), \
             mock.patch.object(runner, "_available", return_value=["claude", "codex"]), \
             mock.patch.object(runner, "_command", side_effect=lambda provider, prompt, mode, vault_root=None: commands[provider]), \
             mock.patch.object(runner.subprocess, "run", side_effect=[
                 SimpleNamespace(returncode=1, stdout="", stderr="authentication failed"),
                 SimpleNamespace(returncode=0, stdout="auto-özet", stderr=""),
             ]) as run:
            output, error, provider = runner.run_model("prompt", ROOT, "text", 10, preferred=None, ctx=self.ctx)
        self.assertEqual((output, error, provider), ("auto-özet", None, "codex"))
        self.assertEqual(run.call_count, 2)

    def test_canonical_skills_are_identical_for_all_agents(self):
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        skills = [row for row in rows if row.key.endswith("SKILL.md")]
        by_name = {}
        for row in skills:
            by_name.setdefault(Path(row.key).parent.name, set()).add(row.after)
        self.assertTrue(by_name)
        self.assertTrue(all(len(contents) == 1 for contents in by_name.values()))

    def test_maintenance_skills_are_canonical_and_discoverable(self):
        names = self.ctx.resources.iter_files("skills")
        for name in ("beyin-doktor", "gecmis-import", "kod-orkestrasyon"):
            self.assertIn(name + "/SKILL.md", names)

    def test_global_antigravity_installer_preserves_config_and_is_idempotent(self):
        path = self.home / ".gemini/config/hooks.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"personal": {"enabled": True}}), encoding="utf-8")
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        backend = self.backend()
        for row in rows:
            backend.apply(row)
        self.assertEqual(RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, backend), ())
        self.assertTrue(json.loads(path.read_text(encoding="utf-8"))["personal"]["enabled"])

    def test_generic_global_installer_accepts_any_vault_name_and_all_providers(self):
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        backend = self.backend()
        for row in rows:
            backend.apply(row)
        self.assertEqual(RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, backend), ())
        self.assertIn(self.vault.name, (self.home / ".codex/AGENTS.md").read_text(encoding="utf-8"))
        for path in (".gemini/config/hooks.json", ".claude/settings.json", ".cursor/hooks.json", ".codex/hooks.json"):
            self.assertTrue((self.home / path).is_file())

    def test_global_codex_installer_chains_existing_notify_without_losing_it(self):
        codex = self.home / ".codex"
        codex.mkdir()
        original = [str(self.root / "custom notify.exe"), "turn-ended"]
        (codex / "config.toml").write_text("notify = " + json.dumps(original) + "\nmodel = \"custom\"\n", encoding="utf-8")
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        backend = self.backend()
        for row in rows:
            backend.apply(row)
        self.assertEqual(RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, backend), ())
        chain = self.ctx.paths.state_dir / "codex-notify-chain.json"
        self.assertEqual(json.loads(chain.read_text(encoding="utf-8")), {"argv": original})
        self.assertIn('model = "custom"', (codex / "config.toml").read_text(encoding="utf-8"))

    def test_global_codex_installer_writes_valid_toml_for_non_bmp_vault_name(self):
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        backend = self.backend()
        for row in rows:
            backend.apply(row)
        self.assertEqual(RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, backend), ())
        parsed = tomllib.loads((self.home / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertEqual(parsed["notify"][0], str(self.app / "respectedbrain.exe"))
        self.assertIn(self.ctx.paths.vault_id, parsed["notify"])

    def test_global_native_hooks_reuse_vaults_verified_python_command(self):
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        commands = " ".join(row.after.decode() for row in rows if row.after and Path(row.key).name == "hooks.json")
        self.assertIn("respectedbrain.exe", commands)
        self.assertNotIn("python", commands)
        self.assertIn(self.ctx.paths.vault_id, commands)

    def test_global_codex_installer_preserves_valid_multiline_notify(self):
        codex = self.home / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text('notify = [\n  "custom.exe",\n  "turn-ended",\n]\nmodel = "custom"\n', encoding="utf-8")
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        backend = self.backend()
        for row in rows:
            backend.apply(row)
        self.assertEqual(RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, backend), ())
        self.assertEqual(json.loads((self.ctx.paths.state_dir / "codex-notify-chain.json").read_text(encoding="utf-8"))["argv"], ["custom.exe", "turn-ended"])

    def test_global_codex_installer_fails_closed_on_invalid_notify(self):
        path = self.home / ".codex/config.toml"
        path.parent.mkdir()
        path.write_text('notify = "invalid"\nmodel = "custom"\n', encoding="utf-8")
        before = snapshot(self.root)
        with self.assertRaises(ValueError):
            RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        self.assertEqual(snapshot(self.root), before)

    def test_global_installer_manages_explicit_antigravity_homes_only(self):
        extra = self.root / "extra-home"
        extra.mkdir()
        before = snapshot(self.root)
        for home in (self.home, extra):
            profile = IntegrationProfile(self.profile.platform, self.profile.launcher, home)
            rows = RENDER.plan_integrations(self.ctx, profile, {"global": True}, self.backend())
            self.assertTrue(any(row.key == str(home / ".gemini/config/hooks.json") for row in rows))
        self.assertEqual(snapshot(self.root), before)

    def test_windows_wsl_codex_only_syncs_shared_skills_to_runtime_home(self):
        profile = IntegrationProfile("windows-wsl", ("/opt/respectedbrain",), self.home)
        with mock.patch.object(RENDER.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=self.wsl_registry_output())):
            rows = RENDER.plan_integrations(self.ctx, profile, {"global": True}, self.backend())
        self.assertTrue(any(row.key.startswith(str(self.home / ".agents/skills")) for row in rows))
        self.assertFalse(any(row.key.startswith(str(self.vault)) for row in rows))

    def test_global_installer_multi_home_preview_is_deduplicated_and_read_only(self):
        extra = self.root / "extra-home"
        extra.mkdir()
        before = snapshot(self.root)
        for home in (self.home, extra):
            profile = IntegrationProfile(self.profile.platform, self.profile.launcher, home)
            rows = RENDER.plan_integrations(self.ctx, profile, {"global": True}, self.backend())
            self.assertTrue(any(row.key == str(home / ".gemini/config/hooks.json") for row in rows))
        self.assertEqual(snapshot(self.root), before)

    def test_global_installer_rejects_missing_extra_home_before_writes(self):
        profile = IntegrationProfile(self.profile.platform, self.profile.launcher, self.root / "missing-home")
        before = snapshot(self.root)
        with self.assertRaises(ValueError):
            RENDER.plan_integrations(self.ctx, profile, {"global": True}, self.backend())
        self.assertEqual(snapshot(self.root), before)

    def test_compatibility_antigravity_installer_accepts_multiple_homes(self):
        extra = self.root / "extra-home"
        extra.mkdir()
        before = snapshot(self.root)
        for home in (self.home, extra):
            profile = IntegrationProfile(self.profile.platform, self.profile.launcher, home)
            rows = RENDER.plan_integrations(self.ctx, profile, {"global": True}, self.backend())
            self.assertTrue(any(row.key == str(home / ".gemini/config/hooks.json") for row in rows))
        self.assertEqual(snapshot(self.root), before)

    def test_native_windows_global_command_is_absolute_and_shell_free(self):
        command = RENDER.bridge_argv(self.ctx, self.profile, "antigravity", "start", global_hook=True)
        self.assertTrue(Path(command[0]).is_absolute())
        self.assertNotIn("bash", command)
        self.assertNotIn("wsl.exe", command)
        self.assertIn("--global-hook", command)

    def test_native_windows_global_installer_is_selective_and_idempotent(self):
        planner = RENDER._Planner(self.backend())
        writes, _ = RENDER._global_writes(self.ctx, self.profile, planner, providers=("antigravity",))
        keys = {path.relative_to(self.home).as_posix() for path, _ in writes}
        self.assertIn(".gemini/config/hooks.json", keys)
        self.assertNotIn(".codex/hooks.json", keys)
        self.assertNotIn(".claude/settings.json", keys)

    def test_installer_preserves_personalized_instruction_as_canonical(self):
        override = self.ctx.paths.overrides_dir / "instructions.md"
        override.parent.mkdir(parents=True)
        override.write_text("Ada kişisel kuralı", encoding="utf-8")
        rows = RENDER.plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        for row in rows:
            if Path(row.key).name in {"AGENTS.md", "CLAUDE.md", "GEMINI.md"}:
                self.assertIn("Ada kişisel kuralı", row.after.decode())


if __name__ == "__main__":
    unittest.main(verbosity=2)
