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
import unittest
from unittest import mock
from types import SimpleNamespace
from contextlib import redirect_stdout
import io


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


class MultiAITest(unittest.TestCase):
    def test_generated_files_have_no_drift(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_integrations.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_provider_configs_point_to_bridge(self):
        codex = json.loads((ROOT / "template/.codex/hooks.json").read_text())
        cursor = json.loads((ROOT / "template/.cursor/hooks.json").read_text())
        antigravity = json.loads((ROOT / "template/.agents/hooks.json").read_text())
        self.assertIn(".beyin/hooks/bridge.py", json.dumps(codex))
        self.assertIn(".beyin/hooks/bridge.py", json.dumps(cursor))
        self.assertIn(".beyin/hooks/bridge.py", json.dumps(antigravity))

    def test_fresh_generated_adapters_expose_only_the_current_product_identity(self):
        codex = json.loads((ROOT / "template/.codex/hooks.json").read_text(encoding="utf-8"))
        antigravity = json.loads(
            (ROOT / "template/.agents/hooks.json").read_text(encoding="utf-8")
        )
        cursor_rule = (ROOT / "template/.cursor/rules/beyin.mdc").read_text(
            encoding="utf-8"
        )

        self.assertEqual(set(antigravity), {"respected-brain"})
        self.assertIn("Respected Brain", codex["description"])
        self.assertIn("description: Respected Brain", cursor_rule)
        combined = json.dumps((codex, antigravity), ensure_ascii=False) + cursor_rule
        self.assertNotIn("Respot", combined)
        self.assertNotIn("RESPOT", combined)
        self.assertNotIn("respot", combined)

    def test_bridge_normalizes_provider_inputs_and_outputs(self):
        bridge = load("bridge", ROOT / "template/.beyin/hooks/bridge.py")
        normalized = bridge.normalize("antigravity", {
            "conversationId": "abc", "transcriptPath": "/tmp/t.jsonl",
            "workspacePaths": ["/tmp/project"], "modelName": "gemini-test",
        })
        self.assertEqual(normalized["session_id"], "abc")
        self.assertEqual(normalized["transcript_path"], "/tmp/t.jsonl")
        self.assertEqual(normalized["cwd"], "/tmp/project")
        self.assertEqual(normalized["beyin_provider"], "antigravity")
        captured = io.StringIO()
        with redirect_stdout(captured):
            bridge.output("antigravity", "end", "")
        self.assertEqual(json.loads(captured.getvalue()), {"decision": "stop"})

    def test_antigravity_normalize_resolves_ide_then_cli_transcript(self):
        bridge = load(
            "bridge_transcript",
            ROOT / "template/.beyin/hooks/bridge.py",
        )
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            ide = (
                home
                / ".gemini/antigravity-ide/brain/session-1/.system_generated/logs/transcript.jsonl"
            )
            ide.parent.mkdir(parents=True)
            ide.write_text("{}\n", encoding="utf-8")

            with mock.patch.object(bridge.Path, "home", return_value=home):
                normalized = bridge.normalize(
                    "antigravity",
                    {"conversationId": "session-1"},
                )

            self.assertEqual(normalized["transcript_path"], str(ide))

            cli = (
                home
                / ".gemini/antigravity-cli/brain/session-2/.system_generated/logs/transcript.jsonl"
            )
            cli.parent.mkdir(parents=True)
            cli.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(bridge.Path, "home", return_value=home):
                normalized_cli = bridge.normalize(
                    "antigravity",
                    {"conversationId": "session-2"},
                )
            self.assertEqual(normalized_cli["transcript_path"], str(cli))

    def test_antigravity_transcript_discovery_is_safe_and_explicit_wins(self):
        bridge = load(
            "bridge_transcript_safety",
            ROOT / "template/.beyin/hooks/bridge.py",
        )
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            candidate = (
                home
                / ".gemini/antigravity-ide/brain/session-1/.system_generated/logs/transcript.jsonl"
            )
            candidate.parent.mkdir(parents=True)
            candidate.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(bridge.Path, "home", return_value=home):
                traversal = bridge.normalize(
                    "antigravity",
                    {"conversationId": "../escape"},
                )
                explicit = bridge.normalize(
                    "antigravity",
                    {
                        "conversationId": "session-1",
                        "transcriptPath": "/explicit/transcript.jsonl",
                    },
                )

            self.assertEqual(traversal["transcript_path"], "")
            self.assertEqual(
                explicit["transcript_path"],
                "/explicit/transcript.jsonl",
            )

    def test_bridge_dispatches_to_shared_lifecycle_without_shell_hooks(self):
        bridge = load("bridge_shared_lifecycle", ROOT / "template/.beyin/hooks/bridge.py")
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "Bridge Brain"
            state = vault / ".beyin/engine/.state"
            memory = vault / "🔮 850-Companion"
            state.mkdir(parents=True)
            memory.mkdir(parents=True)
            (vault / "knowledge").mkdir()
            (vault / "daily").mkdir()
            (memory / "Last-Session.md").write_text(
                "## Session: Bridge\nOrtak lifecycle bağlamı.\n## Previous\n",
                encoding="utf-8",
            )
            (vault / ".beyin/engine/flush.py").write_text(
                "# no-op recorder for detached catch-up\n", encoding="utf-8"
            )
            bridge.ROOT = vault

            with mock.patch.object(bridge.LIFECYCLE, "_launch_flush"):
                context = bridge.dispatch("codex", "start", {"session_id": "bridge-session"})

            self.assertIn("Ortak lifecycle bağlamı.", context)
            key = bridge.LIFECYCLE.session_key("bridge-session")
            self.assertEqual((state / f"prompt_count.{key}").read_text().strip(), "0")
            self.assertFalse((vault / ".claude/hooks").exists())

    def test_global_bridge_distinguishes_windows_vault_and_external_paths(self):
        bridge = load("bridge_windows_paths", ROOT / "template/.beyin/hooks/bridge.py")
        with mock.patch.object(bridge, "ROOT", Path("/mnt/c/Users/Ada/Vault")):
            self.assertTrue(bridge.inside_vault("C:\\Users\\Ada\\Vault"))
            self.assertTrue(bridge.inside_vault("C:\\Users\\Ada\\Vault\\nested"))
            self.assertFalse(bridge.inside_vault("C:\\Projects\\unrelated"))
            self.assertFalse(bridge.inside_vault("relative-project"))
        with mock.patch.object(bridge, "ROOT", Path("C:/Users/Ada/Vault")):
            self.assertTrue(bridge.inside_vault("C:\\Users\\Ada\\Vault"))
            self.assertTrue(bridge.inside_vault("C:\\Users\\Ada\\Vault\\nested"))
            self.assertFalse(bridge.inside_vault("C:\\Projects\\unrelated"))
            self.assertFalse(bridge.inside_vault("relative-project"))

    def test_runner_has_windows_user_local_agy_discovery(self):
        runner = (ROOT / "template/.beyin/model_runner.py").read_text(encoding="utf-8")
        self.assertIn('"AppData" / "Local" / "agy" / "bin" / "agy.exe"', runner)

    def test_runner_supports_cursor_headless(self):
        runner = load("model_runner_cursor", ROOT / "template/.beyin/model_runner.py")
        with mock.patch.object(runner.shutil, "which", side_effect=lambda name: "/bin/cursor-agent" if name == "cursor-agent" else None):
            invocation = runner._command("cursor", "özetle", "text")
        self.assertEqual(
            invocation.argv,
            ["/bin/cursor-agent", "-p", "--output-format", "text", "özetle"],
        )
        self.assertIsNone(invocation.stdin)

    def test_runner_keeps_codex_and_antigravity_prompts_on_stdin(self):
        runner = load("model_runner_stdin", ROOT / "template/.beyin/model_runner.py")
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
        runner = load("model_runner_extract", ROOT / "template/.beyin/model_runner.py")
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

    def test_runner_candidate_order_contract_is_unchanged(self):
        runner = load("model_runner_order", ROOT / "template/.beyin/model_runner.py")
        with mock.patch.object(runner, "_configured_provider", return_value="auto"):
            self.assertEqual(
                runner._available("antigravity"),
                ["antigravity", "claude", "codex", "cursor"],
            )
        with mock.patch.object(runner, "_configured_provider", return_value="cursor"):
            self.assertEqual(
                runner._available("antigravity"),
                ["cursor", "antigravity", "claude", "codex"],
            )

    def test_wsl_windows_cli_receives_translatable_profile_environment(self):
        runner = load("model_runner_wsl_env", ROOT / "template/.beyin/model_runner.py")
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
            result = runner.run_model("prompt", cwd, "text", 10)

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

    def test_wsl_windows_cli_falls_back_to_windows_temp_when_cwd_is_linux_path(self):
        runner = load("model_runner_fallback_cwd", ROOT / "template/.beyin/model_runner.py")
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
            result = runner.run_model("prompt", linux_cwd, "text", 10)

        self.assertEqual(result, ("özet", None, "antigravity"))
        self.assertIs(called.call_args.kwargs["cwd"], mock_fallback)

    def test_wsl_windows_cli_retains_windows_cwd_when_already_under_windows_root(self):
        runner = load("model_runner_keep_cwd", ROOT / "template/.beyin/model_runner.py")
        invocation = runner.Invocation(
            ["/mnt/c/bin/agy.exe", "--print"],
            "prompt",
            True,
        )
        completed = SimpleNamespace(returncode=0, stdout="özet", stderr="")
        win_cwd = Path("/mnt/c/Users/Ada/Documents/RespectedOS")

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
            result = runner.run_model("prompt", win_cwd, "text", 10)

        self.assertEqual(result, ("özet", None, "antigravity"))
        self.assertEqual(called.call_args.kwargs["cwd"], win_cwd)

    def test_summary_provider_can_be_persisted_and_overrides_current_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "My Vault"
            (root / ".beyin").mkdir(parents=True)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/set_summary_provider.py"), "cursor", "--root", str(root)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((root / ".beyin/config.json").read_text())["summary_provider"], "cursor")
        runner = load("model_runner_config", ROOT / "template/.beyin/model_runner.py")
        with mock.patch.object(runner, "_configured_provider", return_value="cursor"):
            self.assertEqual(runner._available("codex")[:2], ["cursor", "codex"])

    def test_public_docs_describe_provider_neutral_setup(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        setup = (ROOT / "SETUP.md").read_text(encoding="utf-8")
        for required in ("Agent değiştirmek", "set_summary_provider.py", "install_global.py", "Vault'un adı"):
            self.assertIn(required, readme)
        self.assertIn("Claude is not mandatory", setup)
        self.assertIn("PHASE 3B: Optional global multi-agent connection", setup)
        self.assertIn("PHASE U7: Optional global access", setup)
        self.assertIn("directly to Respected Brain", setup)
        self.assertIn("Do **not**\nrun a second `enable_multiai.py` migration", setup)
        self.assertNotIn("Claude aboneliğinin", setup)
        self.assertNotIn("claude CLI YOK", setup)

    def test_public_spec_and_template_have_no_stale_claude_only_setup(self):
        paths = (
            ROOT / "docs/SPEC-V2.md",
            ROOT / "docs/beyin-v2.md",
            ROOT / "template/🎯 100-Command-Center/Dashboard.md",
            ROOT / "template/🔮 850-Companion/Last-Session.md",
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
            "github.com/respected0/respectedbrain",
            "summary_provider",
            "cursor-agent",
            "Windows + WSL",
            "Antigravity",
            "Codex",
        ):
            self.assertIn(required, text)

    def test_public_docs_define_all_three_profiles_and_native_limits(self):
        paths = (
            ROOT / "README.md",
            ROOT / "SETUP.md",
            ROOT / "MULTI_AI.md",
            ROOT / "SETUP-WINDOWS.md",
            ROOT / "docs/SPEC-V2.md",
            ROOT / "docs/beyin-v2.md",
        )
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for required in (
            "portable",
            "windows-wsl",
            "windows-native",
            "py.exe -3",
            "1.2.0",
            "Damgasız v1",
            "Claude zorunlu değildir",
            "Restic",
        ):
            self.assertIn(required, text)

    def test_runner_falls_back_only_for_retryable_provider_errors(self):
        runner = load("model_runner_fallback", ROOT / "template/.beyin/model_runner.py")
        commands = {
            "antigravity": runner.Invocation(["agy"], None),
            "claude": runner.Invocation(["claude"], "prompt"),
        }
        with mock.patch.object(runner, "_available", return_value=["antigravity", "claude"]), \
             mock.patch.object(runner, "_command", side_effect=lambda provider, prompt, mode: commands[provider]), \
             mock.patch.object(runner.subprocess, "run", side_effect=[
                 SimpleNamespace(returncode=1, stdout="", stderr="429 quota exceeded"),
                 SimpleNamespace(returncode=0, stdout="özet", stderr=""),
             ]):
            output, error, provider = runner.run_model("prompt", ROOT, "text", 10, preferred="antigravity")
        self.assertEqual((output, error, provider), ("özet", None, "claude"))

        with mock.patch.object(runner, "_available", return_value=["antigravity", "claude"]), \
             mock.patch.object(runner, "_command", side_effect=lambda provider, prompt, mode: commands[provider]), \
             mock.patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="authentication failed")) as run:
            output, error, provider = runner.run_model("prompt", ROOT, "text", 10, preferred="antigravity")
        self.assertEqual((output, error, provider), (None, "antigravity-exit-1", "antigravity"))
        self.assertEqual(run.call_count, 1)

    def test_canonical_skills_are_identical_for_all_agents(self):
        canonical_root = ROOT / "template/.beyin/skills"
        for source in sorted(canonical_root.glob("*/SKILL.md")):
            content = source.read_bytes()
            name = source.parent.name
            self.assertEqual(
                content,
                (ROOT / "template/.agents/skills" / name / "SKILL.md").read_bytes(),
            )
            self.assertEqual(
                content,
                (ROOT / "template/.claude/skills" / name / "SKILL.md").read_bytes(),
            )

    def test_maintenance_skills_are_canonical_and_discoverable(self):
        canonical = ROOT / "template/.beyin/skills"
        inbox = canonical / "inbox-duzenle/SKILL.md"
        self.assertTrue(inbox.is_file())
        self.assertTrue((canonical / "beyin-doktor/SKILL.md").is_file())
        builder = load("maintenance_skill_map", ROOT / "template/.beyin/map_builder.py")
        rendered = builder.render_skills_map(ROOT / "template")
        self.assertIn("`inbox-duzenle`", rendered)
        self.assertIn("`beyin-doktor`", rendered)

    def test_global_antigravity_installer_preserves_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "windows-user"
            config = home / ".gemini/config"
            config.mkdir(parents=True)
            (config / "hooks.json").write_text(
                json.dumps({"my-existing-hook": {"enabled": True}}),
                encoding="utf-8",
            )
            (home / ".gemini/GEMINI.md").write_text(
                "# Kendi global kuralım\n",
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(ROOT / "scripts/install_antigravity_global.py"),
                str(ROOT / "template"),
                "--antigravity-home",
                str(home),
                "--apply",
            ]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            hooks = json.loads((config / "hooks.json").read_text(encoding="utf-8"))
            self.assertIn("my-existing-hook", hooks)
            self.assertIn("respected-brain", hooks)
            rule = (home / ".gemini/GEMINI.md").read_text(encoding="utf-8")
            self.assertIn("# Kendi global kuralım", rule)
            self.assertEqual(rule.count("<!-- RESPECTED-GLOBAL:BEGIN -->"), 1)
            for source in sorted((ROOT / "template/.beyin/skills").glob("*/SKILL.md")):
                installed = config / "skills" / source.parent.name / "SKILL.md"
                self.assertEqual(source.read_bytes(), installed.read_bytes())
            snapshot = {
                path.relative_to(home): path.read_bytes()
                for path in home.rglob("*")
                if path.is_file() and ".respected-backups" not in path.parts
            }
            second = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            repeated = {
                path.relative_to(home): path.read_bytes()
                for path in home.rglob("*")
                if path.is_file() and ".respected-backups" not in path.parts
            }
            self.assertEqual(snapshot, repeated)

    def test_generic_global_installer_accepts_any_vault_name_and_all_providers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Ada Brain"
            shutil.copytree(ROOT / "template", vault)
            home = root / "user"
            home.mkdir()
            (home / ".codex").mkdir()
            (home / ".codex/AGENTS.md").write_text("# Kendi Codex kuralım\n", encoding="utf-8")
            (home / ".cursor").mkdir()
            (home / ".cursor/hooks.json").write_text(json.dumps({"version": 1, "hooks": {"sessionStart": [{"command": "existing"}]}}), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts/install_global.py"), str(vault), "--home", str(home), "--providers", "all", "--apply"]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertIn("Ayarlar > Hooks", first.stdout)
            self.assertIn("/hooks", first.stdout)
            self.assertIn("Ada Brain", (home / ".codex/AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("# Kendi Codex kuralım", (home / ".codex/AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("existing", (home / ".cursor/hooks.json").read_text(encoding="utf-8"))
            self.assertTrue((home / ".gemini/config/hooks.json").is_file())
            self.assertTrue((home / ".claude/settings.json").is_file())
            self.assertTrue((home / ".agents/skills/beyin-doktor/SKILL.md").is_file())
            self.assertTrue((home / ".cursor/skills/gecmis-import/SKILL.md").is_file())
            managed_files = {path.relative_to(home): path.read_bytes() for path in home.rglob("*") if path.is_file() and ".respected-backups" not in path.parts}
            second = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            repeated = {path.relative_to(home): path.read_bytes() for path in home.rglob("*") if path.is_file() and ".respected-backups" not in path.parts}
            self.assertEqual(managed_files, repeated)

    def test_global_installer_manages_explicit_antigravity_homes_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Ada Brain"
            shutil.copytree(ROOT / "template", vault)
            primary = root / "windows-user"
            wsl = root / "wsl-user"
            primary.mkdir()
            wsl.mkdir()
            command = [
                sys.executable,
                str(ROOT / "scripts/install_global.py"),
                str(vault),
                "--home",
                str(primary),
                "--antigravity-home",
                str(wsl),
                "--platform",
                "windows-wsl",
                "--providers",
                "all",
                "--apply",
            ]

            environment = os.environ.copy()
            environment["HOME"] = str(wsl)
            environment["USERPROFILE"] = str(wsl)
            first = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertTrue((primary / ".gemini/config/hooks.json").is_file())
            self.assertTrue((wsl / ".gemini/config/hooks.json").is_file())
            self.assertTrue((primary / ".codex/hooks.json").is_file())
            self.assertFalse((wsl / ".codex").exists())
            self.assertTrue((wsl / ".agents/skills/beyin-doktor/SKILL.md").is_file())
            snapshot = {
                (home.name, path.relative_to(home)): path.read_bytes()
                for home in (primary, wsl)
                for path in home.rglob("*")
                if path.is_file() and ".respected-backups" not in path.parts
            }
            second = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            repeated = {
                (home.name, path.relative_to(home)): path.read_bytes()
                for home in (primary, wsl)
                for path in home.rglob("*")
                if path.is_file() and ".respected-backups" not in path.parts
            }
            self.assertEqual(snapshot, repeated)

    def test_windows_wsl_codex_only_syncs_shared_skills_to_runtime_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Ada Brain"
            shutil.copytree(ROOT / "template", vault)
            windows_home = root / "windows-user"
            wsl_home = root / "wsl-user"
            windows_home.mkdir()
            wsl_home.mkdir()
            environment = os.environ.copy()
            environment["HOME"] = str(wsl_home)
            environment["USERPROFILE"] = str(wsl_home)

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/install_global.py"),
                    str(vault),
                    "--home",
                    str(windows_home),
                    "--platform",
                    "windows-wsl",
                    "--providers",
                    "codex",
                    "--apply",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((windows_home / ".codex/hooks.json").is_file())
            self.assertTrue((wsl_home / ".agents/skills/gecmis-import/SKILL.md").is_file())
            self.assertFalse((wsl_home / ".codex").exists())

    def test_global_installer_multi_home_preview_is_deduplicated_and_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Ada Brain"
            shutil.copytree(ROOT / "template", vault)
            home = root / "user"
            home.mkdir()
            command = [
                sys.executable,
                str(ROOT / "scripts/install_global.py"),
                str(vault),
                "--home",
                str(home),
                "--antigravity-home",
                str(home),
                "--providers",
                "all",
            ]

            result = subprocess.run(command, capture_output=True, text=True, check=False)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count(f"kullanıcı kökü: {home.resolve()}"), 1)
            self.assertFalse((home / ".gemini").exists())

    def test_global_installer_rejects_missing_extra_home_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Ada Brain"
            shutil.copytree(ROOT / "template", vault)
            home = root / "user"
            home.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/install_global.py"),
                    str(vault),
                    "--home",
                    str(home),
                    "--antigravity-home",
                    str(root / "missing"),
                    "--providers",
                    "all",
                    "--apply",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((home / ".gemini").exists())

    def test_compatibility_antigravity_installer_accepts_multiple_homes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            windows_home = root / "windows-user"
            wsl_home = root / "wsl-user"
            windows_home.mkdir()
            wsl_home.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/install_antigravity_global.py"),
                    str(ROOT / "template"),
                    "--antigravity-home",
                    str(windows_home),
                    "--antigravity-home",
                    str(wsl_home),
                    "--apply",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for home in (windows_home, wsl_home):
                self.assertTrue((home / ".gemini/config/hooks.json").is_file())
                self.assertFalse((home / ".codex").exists())

    def test_native_windows_global_command_is_absolute_and_shell_free(self):
        installer = load("install_global_native_command", ROOT / "scripts/install_global.py")
        vault = PureWindowsPath(r"C:\Users\Ada\Ada Brain")

        command = installer.bridge_command(vault, "codex", "start", "windows-native")

        self.assertIn("py.exe -3", command)
        self.assertIn(r"C:\Users\Ada\Ada Brain\.beyin\hooks\bridge.py", command)
        self.assertIn("--provider codex", command)
        self.assertIn("--event start", command)
        self.assertIn("--global-hook", command)
        for forbidden in ("wsl.exe", "bash", ".sh", "/mnt/"):
            self.assertNotIn(forbidden, command)

    def test_native_windows_global_installer_is_selective_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "Ada Brain"
            shutil.copytree(ROOT / "template", vault)
            home = root / "user"
            (home / ".codex").mkdir(parents=True)
            (home / ".codex/AGENTS.md").write_text(
                "# Kendi Codex kuralım\n", encoding="utf-8"
            )
            (home / ".cursor").mkdir()
            (home / ".cursor/hooks.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {"sessionStart": [{"command": "existing"}]},
                    }
                ),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(ROOT / "scripts/install_global.py"),
                str(vault),
                "--home",
                str(home),
                "--platform",
                "windows-native",
                "--providers",
                "codex,cursor",
                "--apply",
            ]

            first = subprocess.run(command, capture_output=True, text=True, check=False)

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            codex_rule = (home / ".codex/AGENTS.md").read_text(encoding="utf-8")
            cursor_hooks = (home / ".cursor/hooks.json").read_text(encoding="utf-8")
            combined = codex_rule + cursor_hooks
            self.assertIn("# Kendi Codex kuralım", codex_rule)
            self.assertIn("existing", cursor_hooks)
            self.assertIn("py.exe -3", combined)
            self.assertNotIn("wsl.exe", combined)
            self.assertFalse((home / ".gemini").exists())
            self.assertFalse((home / ".claude").exists())
            snapshot = {
                path.relative_to(home): path.read_bytes()
                for path in home.rglob("*")
                if path.is_file() and ".respected-backups" not in path.parts
            }

            second = subprocess.run(command, capture_output=True, text=True, check=False)
            repeated = {
                path.relative_to(home): path.read_bytes()
                for path in home.rglob("*")
                if path.is_file() and ".respected-backups" not in path.parts
            }

            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(snapshot, repeated)

    def test_installer_preserves_personalized_instruction_as_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            vault.mkdir()
            (vault / ".beyin-version").write_text("2.0.0\n", encoding="utf-8")
            (vault / "CLAUDE.md").write_text("# AdaOS\n\nKişisel talimat.\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/enable_multiai.py"), str(vault), "--platform", "windows-wsl", "--apply"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            canonical = (vault / ".beyin/instructions.md").read_text(encoding="utf-8")
            self.assertEqual(canonical, "# AdaOS\n\nKişisel talimat.\n")
            self.assertIn(canonical, (vault / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertTrue((vault / ".codex/hooks.json").is_file())
            self.assertTrue((vault / ".cursor/hooks.json").is_file())
            self.assertTrue((vault / ".agents/hooks.json").is_file())
            antigravity = (vault / ".agents/hooks.json").read_text(encoding="utf-8")
            self.assertIn("wsl.exe --cd", antigravity)
            codex = json.loads((vault / ".codex/hooks.json").read_text(encoding="utf-8"))
            self.assertIn("commandWindows", json.dumps(codex))
            selected = subprocess.run(
                [sys.executable, str(vault / "scripts/set_summary_provider.py"), "cursor"],
                cwd=vault,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
            repeated = subprocess.run(
                [sys.executable, str(ROOT / "scripts/enable_multiai.py"), str(vault), "--platform", "windows-wsl", "--apply"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
            config = json.loads((vault / ".beyin/config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["summary_provider"], "cursor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
