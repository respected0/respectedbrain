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

    def test_bridge_dispatches_to_shared_lifecycle_without_shell_hooks(self):
        bridge = load("bridge_shared_lifecycle", ROOT / "template/.beyin/hooks/bridge.py")
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "Bridge Brain"
            state = vault / ".claude/scripts/.state"
            memory = vault / "🔮 850-Companion"
            state.mkdir(parents=True)
            memory.mkdir(parents=True)
            (vault / "knowledge").mkdir()
            (vault / "daily").mkdir()
            (memory / "Last-Session.md").write_text(
                "## Session: Bridge\nOrtak lifecycle bağlamı.\n## Previous\n",
                encoding="utf-8",
            )
            (vault / ".claude/scripts/flush.py").write_text(
                "# no-op recorder for detached catch-up\n", encoding="utf-8"
            )
            bridge.ROOT = vault

            context = bridge.dispatch("codex", "start", {"session_id": "bridge-session"})

            self.assertIn("Ortak lifecycle bağlamı.", context)
            key = bridge.LIFECYCLE.session_key("bridge-session")
            self.assertEqual((state / f"prompt_count.{key}").read_text().strip(), "0")
            self.assertFalse((vault / ".claude/hooks").exists())

    def test_global_bridge_distinguishes_windows_vault_and_external_paths(self):
        bridge = load("bridge_windows_paths", ROOT / "template/.beyin/hooks/bridge.py")
        parts = bridge.ROOT.parts
        self.assertGreaterEqual(len(parts), 4)
        native_root = f"{parts[2].upper()}:\\" + "\\".join(parts[3:])
        self.assertTrue(bridge.inside_vault(native_root))
        self.assertTrue(bridge.inside_vault(native_root + "\\nested"))
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
        self.assertNotIn(prompt, agy_text.argv)
        self.assertEqual(agy_text.stdin, prompt)
        self.assertIn("--print", agy_text.argv)
        self.assertIn("--input-format", agy_text.argv)
        self.assertIn("--sandbox", agy_text.argv)
        self.assertNotIn("--mode", agy_text.argv)
        self.assertIn("--mode", agy_workspace.argv)
        self.assertIn("accept-edits", agy_workspace.argv)
        self.assertIn("--dangerously-skip-permissions", agy_workspace.argv)
        self.assertTrue(agy_workspace.windows_executable)

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
