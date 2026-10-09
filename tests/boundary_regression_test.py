#!/usr/bin/env python3
"""Tests for boundary regressions (unsafe staging) and tracked bytecode cleanup (Faz 1)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from respectedbrain.core.config import ConfigStore
from respectedbrain.core.errors import SelectionError
from respectedbrain.core.paths import Roots
from respectedbrain.integrations.backend import IntegrationProfile
from respectedbrain.installation.migration import plan_migration, apply_migration
from respectedbrain.installation.transaction import Transaction
from tests.foundation_install_support import seed_package
from tests.foundation_migration_apply_test import Backend
from tests.foundation_migration_preview_test import seed_legacy, ALL_FALSE
from tests.foundation_support import snapshot


class BoundaryRegressionTest(unittest.TestCase):
    def setUp(self):
        from respectedbrain.memory import compile
        self.compile = compile
        temporary = tempfile.TemporaryDirectory(prefix="boundary-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.vault, self.legacy = self.root / "vault", self.root / "legacy"
        self.vault.mkdir()
        seed_legacy(self.legacy, layout="flat")
        (self.legacy / "config.json").write_text(json.dumps({"integrations": ALL_FALSE}), encoding="utf-8")
        self.roots = Roots(self.root / "app", self.root / "data", self.vault)
        self.backend = Backend()
        self.profile = IntegrationProfile("windows-native", (str(self.roots.app_root / "respectedbrain.exe"),), self.root / "home")

    def plan(self):
        return plan_migration(self.legacy, self.vault, roots=self.roots, backend=self.backend, profile=self.profile)

    def test_staging_inside_vault_is_rejected_before_model_call(self):
        """If temporary staging directory falls inside vault root, compile must abort immediately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir).resolve()
            state_dir = vault_root / ".beyin" / "engine" / ".state"
            state_dir.mkdir(parents=True, exist_ok=True)
            daily_dir = vault_root / "daily"
            daily_dir.mkdir(parents=True, exist_ok=True)
            daily_file = daily_dir / "2026-09-01.md"
            daily_file.write_text("# Test Daily\n\nSome content", encoding="utf-8")
            knowledge_dir = vault_root / "knowledge"
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            (knowledge_dir / "index.md").write_text("# Index", encoding="utf-8")

            # Simulate staging created inside vault
            inside_stage = vault_root / "accidental_internal_staging"
            inside_stage.mkdir(parents=True, exist_ok=True)

            with mock.patch("tempfile.mkdtemp", return_value=str(inside_stage)), \
                 mock.patch.object(self.compile, "_run_model") as mock_model:

                with self.assertRaises(self.compile.PolicyError) as cm:
                    self.compile._prepare_stage(vault_root, state_dir, daily_file, Path(tempfile.gettempdir()).resolve())

                self.assertIn("staging-inside-vault", str(cm.exception))
                self.assertEqual(mock_model.call_count, 0)

    def test_migration_preserves_unknown_tracked_bytecode_and_gitignore(self):
        """Unknown bytecode remains user-owned; migration never alters the user's Git index."""
        if shutil.which("git") is None:
            self.skipTest("git is not available")
        subprocess.run(["git", "init"], cwd=self.vault, check=True, capture_output=True)
        for key, value in (("user.email", "test@example.com"), ("user.name", "Test Runner")):
            subprocess.run(["git", "config", key, value], cwd=self.vault, check=True, capture_output=True)
        bytecode = self.vault / ".beyin/__pycache__/custom.cpython-311.pyc"
        bytecode.parent.mkdir(parents=True)
        bytecode.write_bytes(b"user bytecode")
        root_pyc = self.vault / "custom.pyc"
        root_pyc.write_bytes(b"user root bytecode")
        ignore = self.vault / ".gitignore"
        ignore.write_bytes(b".env\n")
        subprocess.run(["git", "add", "."], cwd=self.vault, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "user files"], cwd=self.vault, check=True, capture_output=True)
        index_before = (self.vault / ".git/index").read_bytes()
        plan = self.plan()
        retained = {entry.source for entry in plan.entries if entry.action == "retain-user"}
        self.assertIn(bytecode, retained)
        package = seed_package(self.root / "package")
        with mock.patch("respectedbrain.installation.payload.validate_installed_health", return_value=None):
            result = apply_migration(plan, roots=self.roots, package=package, backend=self.backend, require_provenance=False)
        self.assertTrue(result.success, result.conflicts)
        self.assertEqual(bytecode.read_bytes(), b"user bytecode")
        self.assertEqual(root_pyc.read_bytes(), b"user root bytecode")
        self.assertEqual(ignore.read_bytes(), b".env\n")
        self.assertEqual((self.vault / ".git/index").read_bytes(), index_before)

    def test_migration_preserves_custom_preferences_and_uses_installed_launcher(self):
        """Unknown legacy options survive preview while registrations use the selected application."""
        for command in (["/home/ada/.pyenv/shims/python3"], [], ["custom-py"]):
            with self.subTest(command=command):
                (self.legacy / "config.json").write_text(json.dumps({"python_command": command, "integrations": ALL_FALSE}), encoding="utf-8")
                before = snapshot(self.root)
                plan = self.plan()
                self.assertEqual(plan.conflicts, ())
                self.assertEqual(plan.config["preferences"]["python_command"], command)
                self.assertEqual(plan.config["integrations"], ALL_FALSE)
                self.assertEqual(snapshot(self.root), before)
                self.assertEqual(self.profile.launcher, (str(self.roots.app_root / "respectedbrain.exe"),))
        store = ConfigStore(self.roots.data_root)
        store.update(lambda document: document["preferences"].update(custom_python=["user-shim"]))
        store.update(lambda document: document["preferences"].update(summary_provider="codex"))
        self.assertEqual(store.read()["preferences"]["custom_python"], ["user-shim"])

    def test_corrupt_configuration_fails_closed_without_mutation(self):
        (self.legacy / "config.json").write_text('{invalid_json: true,}\n', encoding="utf-8")
        before = snapshot(self.root)
        plan = self.plan()
        self.assertTrue(plan.conflicts)
        self.assertTrue(any("legacy-source" in conflict for conflict in plan.conflicts))
        result = apply_migration(plan, roots=self.roots, package=self.root / "unused", backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.root), before)
        self.roots.data_root.mkdir()
        (self.roots.data_root / "config.json").write_text('{invalid_json: true,}\n', encoding="utf-8")
        with self.assertRaises(SelectionError):
            ConfigStore(self.roots.data_root).read()

    def test_transaction_backups_are_outside_vault_and_overlap_fails_before_write(self):
        before = snapshot(self.root)
        with self.assertRaises(SelectionError):
            Roots(self.roots.app_root, self.vault / "unsafe-backups", self.vault)
        self.assertEqual(snapshot(self.root), before)
        note = self.vault / "note.md"
        note.write_bytes(b"user note")
        with Transaction(self.roots.data_root, self.backend) as tx:
            tx.backup(note)
            self.assertTrue(tx.directory.is_relative_to(self.roots.data_root / "backups"))
            self.assertFalse(tx.directory.is_relative_to(self.vault))
            tx.commit()
        self.assertEqual(note.read_bytes(), b"user note")

    def test_install_antigravity_global_accepts_non_windows_vault_path(self):
        """install_antigravity_global must not reject Linux/POSIX vault paths where windows_path is None."""
        from respectedbrain.integrations.backend import IntegrationProfile, NativeBackend
        from respectedbrain.integrations import rendering
        from respectedbrain.installation.transaction import Transaction
        from tests.foundation_memory_test import make_context
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            ctx = make_context(base / "Ada Brain")
            home = base / "home"
            home.mkdir()
            backend = NativeBackend(ctx.paths.data_root, user_home=home)
            profile = IntegrationProfile("posix", ("/opt/respectedbrain/bin/respectedbrain",), home)
            with mock.patch.object(rendering, "windows_path", return_value=None):
                changes = rendering.plan_integrations(ctx, profile, {"global": True}, backend)
            with Transaction(ctx.paths.data_root, backend) as tx:
                for change in changes:
                    tx.apply_external(change)
                tx.commit()
            hooks = home / ".gemini/config/hooks.json"
            self.assertTrue(hooks.is_file())
            self.assertIn(ctx.paths.vault_id, hooks.read_text(encoding="utf-8"))
            self.assertIn("/opt/respectedbrain/bin/respectedbrain", hooks.read_text(encoding="utf-8"))
            self.assertFalse((ctx.paths.vault_root / ".beyin").exists())


if __name__ == "__main__":
    unittest.main()
