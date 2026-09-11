#!/usr/bin/env python3
"""Adversarial and failure matrix quality tests for Respected Brain 2.1 & 2.2."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_RUNNER_PATH = REPO_ROOT / "template" / ".beyin" / "model_runner.py"
COMPILE_PATH = REPO_ROOT / "template" / ".beyin" / "engine" / "compile.py"
RUNTIME_PATH = REPO_ROOT / "template" / ".beyin" / "runtime_platform.py"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class AdversarialQualityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = load_module("adversarial_runner", MODEL_RUNNER_PATH)
        self.compiler = load_module("adversarial_compiler", COMPILE_PATH)
        self.runtime = load_module("adversarial_runtime", RUNTIME_PATH)

    # -------------------------------------------------------------------------
    # 2.2 Provider & Fallback Adversarial Matrix
    # -------------------------------------------------------------------------

    def test_auto_fallback_exhaustion_returns_last_provider_error(self) -> None:
        """When all providers fail in auto mode, system must not crash and must report last error."""
        commands = {
            "claude": self.runner.Invocation(["claude"], "prompt"),
            "codex": self.runner.Invocation(["codex"], "prompt"),
            "antigravity": self.runner.Invocation(["agy"], None),
        }
        with mock.patch.object(self.runner, "_configured_provider", return_value="auto"), \
             mock.patch.object(self.runner, "_available", return_value=["claude", "codex", "antigravity"]), \
             mock.patch.object(self.runner, "_command", side_effect=lambda p, pr, m: commands[p]), \
             mock.patch.object(self.runner.subprocess, "run", side_effect=[
                 SimpleNamespace(returncode=1, stdout="", stderr="claude auth failed"),
                 SimpleNamespace(returncode=2, stdout="", stderr="codex config error"),
                 SimpleNamespace(returncode=3, stdout="", stderr="antigravity fatal error"),
             ]) as run_mock:
            output, error, provider = self.runner.run_model("prompt", REPO_ROOT, "text", 10, preferred=None)

        self.assertIsNone(output)
        self.assertEqual(error, "antigravity-exit-3")
        self.assertEqual(provider, "antigravity")
        self.assertEqual(run_mock.call_count, 3)

    def test_auto_fallback_handles_timeout_and_advances_to_next_candidate(self) -> None:
        """If provider 1 times out, auto mode must advance to candidate 2 rather than aborting."""
        commands = {
            "claude": self.runner.Invocation(["claude"], "prompt"),
            "codex": self.runner.Invocation(["codex"], "prompt"),
        }
        with mock.patch.object(self.runner, "_configured_provider", return_value="auto"), \
             mock.patch.object(self.runner, "_available", return_value=["claude", "codex"]), \
             mock.patch.object(self.runner, "_command", side_effect=lambda p, pr, m: commands[p]), \
             mock.patch.object(self.runner.subprocess, "run", side_effect=[
                 subprocess.TimeoutExpired(cmd=["claude"], timeout=10),
                 SimpleNamespace(returncode=0, stdout="codex-recovered", stderr=""),
             ]) as run_mock:
            output, error, provider = self.runner.run_model("prompt", REPO_ROOT, "text", 10, preferred=None)

        self.assertEqual((output, error, provider), ("codex-recovered", None, "codex"))
        self.assertEqual(run_mock.call_count, 2)

    def test_auto_fallback_handles_oserror_exec_error_and_advances(self) -> None:
        """If provider binary fails with OSError (permission, corrupted binary), it advances."""
        commands = {
            "claude": self.runner.Invocation(["claude"], "prompt"),
            "codex": self.runner.Invocation(["codex"], "prompt"),
        }
        with mock.patch.object(self.runner, "_configured_provider", return_value="auto"), \
             mock.patch.object(self.runner, "_available", return_value=["claude", "codex"]), \
             mock.patch.object(self.runner, "_command", side_effect=lambda p, pr, m: commands[p]), \
             mock.patch.object(self.runner.subprocess, "run", side_effect=[
                 OSError("Binary corrupted or not executable"),
                 SimpleNamespace(returncode=0, stdout="codex-ok", stderr=""),
             ]) as run_mock:
            output, error, provider = self.runner.run_model("prompt", REPO_ROOT, "text", 10, preferred=None)

        self.assertEqual((output, error, provider), ("codex-ok", None, "codex"))
        self.assertEqual(run_mock.call_count, 2)

    def test_auto_fallback_handles_stream_error_and_advances(self) -> None:
        """If antigravity emits a JSON stream error, auto mode must fall back to next provider."""
        stream_error_payload = '{"event": "result", "result": {"status": "ERROR", "error": "stream-quota-exceeded"}}\n'
        commands = {
            "antigravity": self.runner.Invocation(["agy"], None),
            "codex": self.runner.Invocation(["codex"], "prompt"),
        }
        with mock.patch.object(self.runner, "_configured_provider", return_value="auto"), \
             mock.patch.object(self.runner, "_available", return_value=["antigravity", "codex"]), \
             mock.patch.object(self.runner, "_command", side_effect=lambda p, pr, m: commands[p]), \
             mock.patch.object(self.runner.subprocess, "run", side_effect=[
                 SimpleNamespace(returncode=0, stdout=stream_error_payload, stderr=""),
                 SimpleNamespace(returncode=0, stdout="codex-salvaged", stderr=""),
             ]) as run_mock:
            output, error, provider = self.runner.run_model("prompt", REPO_ROOT, "text", 10, preferred=None)

        self.assertEqual((output, error, provider), ("codex-salvaged", None, "codex"))
        self.assertEqual(run_mock.call_count, 2)

    def test_preferred_provider_still_fails_fast_on_non_retryable_error(self) -> None:
        """When an explicit provider is requested, fail-fast contract MUST be preserved."""
        commands = {
            "codex": self.runner.Invocation(["codex"], "prompt"),
            "claude": self.runner.Invocation(["claude"], "prompt"),
        }
        with mock.patch.object(self.runner, "_available", return_value=["codex", "claude"]), \
             mock.patch.object(self.runner, "_command", side_effect=lambda p, pr, m: commands[p]), \
             mock.patch.object(self.runner.subprocess, "run", return_value=SimpleNamespace(
                 returncode=1, stdout="", stderr="unauthorized api key"
             )) as run_mock:
            output, error, provider = self.runner.run_model("prompt", REPO_ROOT, "text", 10, preferred="codex")

        self.assertEqual((output, error, provider), (None, "codex-exit-1", "codex"))
        self.assertEqual(run_mock.call_count, 1)

    def test_zero_pixel_flags_on_windows(self) -> None:
        """Ensure CREATE_NO_WINDOW flag is guaranteed on Windows for hidden and detached runners."""
        with mock.patch.object(self.runtime.os, "name", "nt"):
            hidden = self.runtime.hidden_process_options()
            self.assertEqual(hidden.get("creationflags"), 0x08000000)

            detached = self.runtime.detached_process_options()
            flags = detached.get("creationflags", 0)
            self.assertTrue(flags & 0x08000000, "CREATE_NO_WINDOW flag must be set in detached processes")

    # -------------------------------------------------------------------------
    # 2.1 Knowledge Domain Isolation & Boundary Adversarial Matrix
    # -------------------------------------------------------------------------

    def test_domain_path_validation_strictly_rejects_unsafe_paths(self) -> None:
        """Adversarial paths (directory traversal, non-md, root escape) must be rejected."""
        is_allowed = self.compiler._is_allowed_output_file
        # Legitimate domain paths
        self.assertTrue(is_allowed("knowledge/concepts/tech/ark.md"))
        self.assertTrue(is_allowed("knowledge/concepts/research/vergi.md"))
        self.assertTrue(is_allowed("knowledge/concepts/project/p1/arch.md"))
        self.assertTrue(is_allowed("knowledge/concepts/genel.md"))
        self.assertTrue(is_allowed("knowledge/connections/c1--c2.md"))
        self.assertTrue(is_allowed("knowledge/index.md"))
        self.assertTrue(is_allowed("knowledge/log.md"))

        # Adversarial / forbidden paths
        self.assertFalse(is_allowed("knowledge/concepts/tech/malicious.exe"))
        self.assertFalse(is_allowed("knowledge/concepts/tech/script.py"))
        self.assertFalse(is_allowed("knowledge/concepts/tech/hook.sh"))
        self.assertFalse(is_allowed("knowledge/concepts/research/data.json"))
        self.assertFalse(is_allowed("knowledge/concepts/research/"))
        self.assertFalse(is_allowed("knowledge/concepts/"))
        self.assertFalse(is_allowed("knowledge/tech.md"))
        self.assertFalse(is_allowed("knowledge/research.md"))
        self.assertFalse(is_allowed("daily/2026-09-11.md"))
        self.assertFalse(is_allowed("SETUP.md"))
        self.assertFalse(is_allowed("CLAUDE.md"))
        self.assertFalse(is_allowed(".agents/rules/test.md"))
        self.assertFalse(is_allowed(".claude/hooks/session-start.sh"))

    def test_promotion_refuses_overwrite_if_live_file_changed_concurrently(self) -> None:
        """If a target file was modified concurrently by the user while staging compiled, abort promotion."""
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            knowledge = vault / "knowledge"
            concepts = knowledge / "concepts" / "research"
            concepts.mkdir(parents=True)
            live_file = concepts / "analiz.md"
            live_file.write_text("initial user content", encoding="utf-8")

            stage_dir = vault / "temp_stage"
            stage_concepts = stage_dir / "knowledge" / "concepts" / "research"
            stage_concepts.mkdir(parents=True)
            staged_file = stage_concepts / "analiz.md"
            staged_file.write_text("compiled content", encoding="utf-8")

            # live_baseline recorded digest from 'initial user content', but user modified it to 'concurrent change'
            live_file.write_text("concurrent change by user", encoding="utf-8")
            live_baseline = {
                "knowledge/concepts/research/analiz.md": "fake-stale-hash",
            }

            with self.assertRaises(self.compiler.PolicyError) as context:
                self.compiler._promote_changes(
                    stage_dir, vault, ["knowledge/concepts/research/analiz.md"], live_baseline
                )
            self.assertIn("live-target-changed", str(context.exception))
            # Verify live file was not overwritten by stale compiled content
            self.assertEqual(live_file.read_text(encoding="utf-8"), "concurrent change by user")


if __name__ == "__main__":
    unittest.main()
