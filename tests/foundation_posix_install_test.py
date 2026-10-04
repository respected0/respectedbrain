"""POSIX installation contracts with isolated fake payloads; no native build claim."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from respectedbrain.core.config import ConfigStore
from respectedbrain.core.paths import Roots
from respectedbrain.vault.registry import build_context
from respectedbrain.installation.setup import setup
from respectedbrain.installation.update import update
from respectedbrain.installation.repair import repair
from respectedbrain.installation.uninstall import uninstall
from respectedbrain.installation.ownership import read_manifest, prove_ownership
from tests.foundation_install_support import seed_package
from tests.foundation_support import note_hashes
from tests.foundation_transactions_test import Backend

class FoundationPosixInstallTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "Ada's home 🧠"
        self.home.mkdir()
        self.vault = self.root / "vault"
        self.roots = Roots(self.root / "app", self.root / "data", self.vault)
        self.backend = Backend()
        self.flags = dict.fromkeys(("global", "mcp", "schedule", "shortcut"), False)
        self.profile = {"platform":"posix", "user_home":str(self.home)}
        self.package = seed_package(self.root / "package")
        executable = self.package / "respectedbrain.exe"
        executable.rename(self.package / "respectedbrain")
        manifest = json.loads((self.package / "distribution.json").read_text())
        manifest["platform"] = "linux"
        manifest["launcher"] = "respectedbrain"
        manifest["files"]["respectedbrain"] = manifest["files"].pop("respectedbrain.exe")
        (self.package / "distribution.json").write_text(json.dumps(manifest))
        (self.package / "respectedbrain").chmod(0o755)
        for fake in (patch("sys.platform", "linux"), patch("respectedbrain.installation.payload.validate_installed_health", return_value=None)):
            fake.start()
            self.addCleanup(fake.stop)
        self.launcher = self.home / ".local/bin/respectedbrain"
    def install(self):
        result = setup(self.roots, self.vault, profile=self.profile, desired=self.flags, backend=self.backend, package=self.package)
        self.assertTrue(result.success, result.conflicts)
        return build_context(self.roots, ConfigStore(self.roots.data_root), vault=self.vault, vault_id=None, env={})
    def test_unknown_distribution_manifest_is_never_overwritten(self):
        self.roots.app_root.mkdir()
        target = self.roots.app_root / "distribution.json"
        target.write_bytes(b"user-owned-sentinel")
        result = setup(self.roots, self.vault, profile=self.profile, desired=self.flags, backend=self.backend, package=self.package)
        self.assertFalse(result.success)
        self.assertEqual(target.read_bytes(), b"user-owned-sentinel")

    def test_default_linux_profile_persists_resolved_platform(self):
        self.profile.pop("platform")
        ctx = self.install()
        from respectedbrain.installation.operations import validate_manifest_roots
        self.assertEqual(ctx.config["vaults"][ctx.paths.vault_id]["settings"].get("platform"), "posix")
        validate_manifest_roots(ctx, read_manifest(ctx.paths.data_root / "install-manifest.json"))

    def test_posix_schedule_files_are_kept_when_global_is_disabled(self):
        ctx = self.install()
        ConfigStore(ctx.paths.data_root).update(lambda value: value["integrations"].update(schedule=True))
        from respectedbrain.installation.ownership import OwnershipManifest
        from respectedbrain.installation.operations import plan_connections
        from respectedbrain.integrations.backend import ExternalChange
        name = "respected-morning-briefing-" + ctx.paths.vault_id
        rows = tuple(ExternalChange("file", str(self.home / ".config/systemd/user" / (name + suffix)), None, b"owned schedule") for suffix in (".service", ".timer"))
        for row in rows:
            self.backend.records[(row.kind, row.key)] = row.after
        with patch("respectedbrain.integrations.rendering.plan_integrations", return_value=()):
            changes, owned = plan_connections(ctx, self.backend, OwnershipManifest(3, (), rows))
        self.assertEqual(changes, ())
        self.assertEqual(owned, rows)

    def test_migration_preview_uses_planned_personalized_resources(self):
        from tests.foundation_migration_preview_test import seed_legacy
        from respectedbrain.integrations.backend import IntegrationProfile
        from respectedbrain.installation.migration import plan_migration
        legacy = self.root / "legacy"
        seed_legacy(legacy, layout="flat")
        self.vault.mkdir()
        original = (legacy / "instructions.md").read_text()
        class PreviewBackend(Backend):
            def preview(self, ctx, *, desired, profile):
                self.selected = ctx.resources.read_text("instructions/default.md")
                self.skills = ctx.resources.iter_files("skills")
                return ()
        backend = PreviewBackend()
        plan = plan_migration(legacy, self.vault, roots=self.roots, backend=backend, profile=IntegrationProfile("posix", (str(self.roots.app_root / "respectedbrain"),), self.home))
        self.assertEqual(plan.conflicts, ())
        self.assertEqual(backend.selected, original)
        self.assertIn("custom/SKILL.md", backend.skills)
        self.assertFalse(self.roots.data_root.exists())

    def test_required_launcher_is_owned_independent_of_all_disabled_integrations(self):
        ctx = self.install()
        self.assertTrue(self.launcher.is_file(), "Linux install must create the required PATH launcher")
        text = self.launcher.read_text()
        self.assertTrue(text.startswith("#!/bin/sh\n"))
        self.assertIn("respectedbrain", text)
        self.assertIn('"$@"', text)
        manifest = read_manifest(self.roots.data_root / "install-manifest.json")
        self.assertTrue(any(item.role == "launcher" and item.path == self.launcher for item in manifest.files))
        self.assertTrue(prove_ownership(self.launcher, manifest))
        self.assertEqual(ConfigStore(ctx.paths.data_root).read()["integrations"], self.flags)
        self.assertFalse((self.vault / ".beyin").exists())
    def test_unknown_launcher_collision_is_retained_and_install_rolls_back(self):
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_bytes(b"user launcher")
        result = setup(self.roots, self.vault, profile=self.profile, desired=self.flags, backend=self.backend, package=self.package)
        self.assertFalse(result.success)
        self.assertEqual(self.launcher.read_bytes(), b"user launcher")
        self.assertFalse((self.roots.app_root / "respectedbrain").exists())
    def test_update_repair_and_uninstall_keep_notes_and_manage_launcher(self):
        ctx = self.install()
        before = note_hashes(self.vault)
        self.assertTrue(update(ctx, package=self.package, backend=self.backend).success)
        self.assertTrue(self.launcher.is_file())
        self.launcher.unlink()
        result = repair(ctx, backend=self.backend)
        self.assertTrue(result.success, result.conflicts)
        self.assertTrue(self.launcher.is_file())
        self.assertTrue(uninstall(ctx, backend=self.backend).success)
        self.assertFalse(self.launcher.exists())
        self.assertEqual(note_hashes(self.vault), before)
    def test_application_permission_changes_break_ownership_proof(self):
        self.install()
        binary = self.roots.app_root / "respectedbrain"
        original = stat.S_IMODE(binary.stat().st_mode)
        binary.chmod(0o444)
        try:
            self.assertFalse(prove_ownership(binary, read_manifest(self.roots.data_root / "install-manifest.json")))
        finally:
            binary.chmod(original)

    def test_owned_launcher_user_content_edit_is_retained(self):
        ctx = self.install()
        self.assertTrue(self.launcher.is_file(), "Required launcher missing")
        self.launcher.write_bytes(b"user edit")
        result = update(ctx, package=self.package, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(self.launcher.read_bytes(), b"user edit")
        result = uninstall(ctx, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(self.launcher.read_bytes(), b"user edit")
    def test_owned_launcher_permission_edit_is_retained(self):
        ctx = self.install()
        self.assertTrue(self.launcher.is_file(), "Required launcher missing")
        self.launcher.chmod(0o444)
        try:
            manifest = read_manifest(self.roots.data_root / "install-manifest.json")
            self.assertFalse(prove_ownership(self.launcher, manifest))
            result = repair(ctx, backend=self.backend)
            self.assertFalse(result.success)
            self.assertEqual(stat.S_IMODE(self.launcher.stat().st_mode) & 0o222, 0)
        finally:
            self.launcher.chmod(0o666)
    def test_fresh_health_failure_removes_only_product_launcher(self):
        sentinel = self.home / "sentinel"
        sentinel.write_bytes(b"user")
        with patch("respectedbrain.installation.payload.validate_installed_health", side_effect=OSError("fault")):
            result = setup(self.roots, self.vault, profile=self.profile, desired=self.flags, backend=self.backend, package=self.package)
        self.assertFalse(result.success)
        self.assertFalse(self.launcher.exists())
        self.assertEqual(sentinel.read_bytes(), b"user")
    @unittest.skipIf(os.name == "nt", "POSIX shell/executable permissions require an actual POSIX host")
    def test_required_launcher_is_executable_and_quotes_application_path(self):
        ctx = self.install()
        self.assertTrue(os.access(self.launcher, os.X_OK))
        import shlex
        command = self.launcher.read_text().splitlines()[1]
        self.assertEqual(shlex.split(command)[:2], ["exec", str(self.roots.app_root / "respectedbrain")])

class PosixPackagingEntrypointsTest(unittest.TestCase):
    def test_native_setup_entrypoints_exist_and_forward_to_shared_frozen_cli(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("packaging/linux/setup.sh", "packaging/macos/setup.command"):
            path = root / name
            self.assertTrue(path.is_file(), name)
            self.assertNotIn(b"\r", path.read_bytes(), "POSIX shebang files require LF line endings")
            text = path.read_text()
            self.assertIn("setup", text)
            self.assertIn("--package", text)
            self.assertIn('"$@"', text)
            self.assertNotIn("python", text.lower())


import tests.foundation_migration_apply_test as migration_fixtures

class MigrationFinalBoundaryTest(unittest.TestCase):
    setUp = migration_fixtures.FoundationMigrationApplyTest.setUp
    module = migration_fixtures.FoundationMigrationApplyTest.module
    plan = migration_fixtures.FoundationMigrationApplyTest.plan
    apply = migration_fixtures.FoundationMigrationApplyTest.apply
    def test_legacy_state_modified_after_copy_cannot_commit(self):
        for phase in ("health", "cleanup"):
            with self.subTest(phase=phase):
                plan = self.plan()
                row = next(item for item in plan.entries if item.action == "copy-state")
                original = row.source.read_bytes()
                def fault(name):
                    if name == phase:
                        row.source.write_bytes(b"concurrent legacy writer")
                try:
                    result = self.apply(plan, fault=fault)
                    self.assertFalse(result.success)
                    self.assertEqual(row.source.read_bytes(), b"concurrent legacy writer")
                    self.assertFalse(row.target.exists())
                finally:
                    row.source.write_bytes(original)
    def test_retired_legacy_registration_is_not_resurrected_on_uninstall(self):
        from dataclasses import replace
        from respectedbrain.integrations.backend import ExternalChange
        self.backend.records[("task", "legacy-task")] = b"legacy task"
        plan = replace(self.plan(), external=(ExternalChange("task", "legacy-task", b"legacy task", None, True, None),))
        result = self.apply(plan)
        self.assertTrue(result.success, result.conflicts)
        manifest = read_manifest(self.roots.data_root / "install-manifest.json")
        task = next(row for row in manifest.external if row.key == "legacy-task")
        self.assertIsNone(task.before)
        ctx = build_context(self.roots, ConfigStore(self.roots.data_root), vault=self.vault, vault_id=None, env={})
        self.assertTrue(uninstall(ctx, backend=self.backend).success)
        self.assertIsNone(self.backend.read("task", "legacy-task"))
