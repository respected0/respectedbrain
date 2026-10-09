"""Real WAL migration with temporary payloads and explicit external fakes."""
from contextlib import contextmanager
from dataclasses import replace
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from respectedbrain.core.config import ConfigStore
from respectedbrain.core.paths import Roots
from respectedbrain.integrations.backend import ExternalChange, IntegrationProfile
from respectedbrain.installation.ownership import digest, read_manifest
from tests.foundation_install_support import seed_package
from tests.foundation_migration_preview_test import seed_legacy, ALL_FALSE, UUID_TEXT
from tests.foundation_support import snapshot, note_hashes, write_json
from tests.foundation_transactions_test import Backend as BaseBackend

PHASES = ("lock", "backup", "stage", "activate", "state", "config", "integrations", "health", "cleanup")

class Backend(BaseBackend):
    def preview(self, ctx, *, desired, profile):
        return (ExternalChange("task", "fixture-task", self.read("task", "fixture-task"), b"new-registration"),)

class FoundationMigrationApplyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.vault, self.legacy = self.root / "Türkçe 🧠 Vault", self.root / "legacy"
        self.vault.mkdir()
        for name in ("daily", "knowledge", "🔮 850-Companion", "🏰 300-Projects", "📋 Templates", ".obsidian"):
            (self.vault / name).mkdir()
            (self.vault / name / "user.md").write_bytes(b"irreplaceable note")
        self.roots = Roots(self.root / "app", self.root / "data", self.vault)
        self.package = seed_package(self.root / "package")
        self.backend = Backend()
        self.profile = IntegrationProfile("windows-native", (str(self.roots.app_root / "respectedbrain.exe"),), self.root / "home")
        seed_legacy(self.legacy, layout="flat")
        write_json(self.legacy / "config.json", {"summary_provider":"codex", "provider_priority":["codex", "gemini"], "provider_fallback":False, "integrations":ALL_FALSE, "custom":7})
        write_json(self.vault / ".respected.json", {"schema_version":2,"vault_id":UUID_TEXT,"runtime_path":str(self.legacy),"custom_marker":9})
        self.health = patch("respectedbrain.installation.payload.validate_installed_health", return_value=None)
        self.health.start()
        self.addCleanup(self.health.stop)
    def module(self):
        module = importlib.import_module("respectedbrain.installation.migration")
        self.assertTrue(callable(getattr(module, "apply_migration", None)), "Transactional migration service missing")
        return module
    def plan(self):
        return importlib.import_module("respectedbrain.installation.migration").plan_migration(self.legacy, self.vault, roots=self.roots, backend=self.backend, profile=self.profile)
    def apply(self, plan=None, **kwargs):
        kwargs.setdefault("require_provenance", False)
        return self.module().apply_migration(plan or self.plan(), roots=self.roots, package=self.package, backend=self.backend, **kwargs)
    def test_migration_preserves_notes_preferences_and_overrides(self):
        before = note_hashes(self.vault)
        plan = self.plan()
        self.assertEqual(plan.conflicts, ())
        result = self.apply(plan)
        self.assertTrue(result.success, result.conflicts)
        self.assertEqual(note_hashes(self.vault), before)
        config = ConfigStore(self.roots.data_root).read()
        self.assertEqual(config["integrations"], ALL_FALSE)
        self.assertEqual(config["preferences"]["summary_provider"], "codex")
        self.assertFalse(config["preferences"]["provider_fallback"])
        self.assertEqual(config["preferences"]["custom"], 7)
        for entry in plan.entries:
            if entry.action in ("copy-state", "preserve-override"):
                self.assertEqual(entry.target.read_bytes(), entry.source.read_bytes())
            if entry.action == "remove-owned":
                self.assertFalse(entry.source.exists())
        marker = json.loads((self.vault / ".respected.json").read_text())
        self.assertEqual(marker["schema_version"], 3)
        self.assertEqual(marker["vault_id"], plan.vault_id)
        self.assertEqual(marker["custom_marker"], 9)
        self.assertNotIn("runtime_path", marker)
        self.assertEqual(config["vaults"][plan.vault_id]["legacy_metadata"]["runtime_path"], str(self.legacy))
        manifest = read_manifest(self.roots.data_root / "install-manifest.json")
        self.assertTrue(any(item.path == self.roots.data_root / "config.json" for item in manifest.files))
        self.assertFalse(any(item.path.is_relative_to(self.vault) for item in manifest.files))
        self.assertEqual(self.backend.read("task", "fixture-task"), b"new-registration")
        self.assertTrue((self.legacy / "events.py").exists())
        self.assertFalse(any(path.name == "search_index.db" for path in (self.roots.data_root / "vaults").rglob("*")))
    def test_each_phase_failure_rolls_back(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                before_app, before_vault, before_legacy = snapshot(self.roots.app_root), snapshot(self.vault), snapshot(self.legacy)
                config = self.roots.data_root / "config.json"
                before_config = config.read_bytes() if config.exists() else None
                before_external = dict(self.backend.records)
                def fault(name):
                    if name == phase:
                        raise OSError("fault:" + phase)
                result = self.apply(fault=fault)
                self.assertFalse(result.success)
                self.assertTrue(any("fault:" + phase in item for item in result.conflicts), result.conflicts)
                self.assertEqual(snapshot(self.roots.app_root), before_app)
                self.assertEqual(snapshot(self.vault), before_vault)
                self.assertEqual(snapshot(self.legacy), before_legacy)
                self.assertEqual(config.read_bytes() if config.exists() else None, before_config)
                self.assertEqual({key:value for key,value in self.backend.records.items() if value is not None}, {key:value for key,value in before_external.items() if value is not None})
                journals = list((self.roots.data_root / "backups").glob("tx-*/journal.json"))
                self.assertTrue(journals)
                self.assertTrue(all(json.loads(item.read_text())["status"] == "rolled-back" for item in journals))
    def test_reapply_does_not_duplicate_sessions(self):
        plan = self.plan()
        first = self.apply(plan)
        self.assertTrue(first.success, first.conflicts)
        before_state = snapshot(self.roots.data_root / "vaults" / plan.vault_id)
        before_notes = note_hashes(self.vault)
        second = self.apply(plan)
        self.assertTrue(second.success, second.conflicts)
        self.assertEqual(snapshot(self.roots.data_root / "vaults" / plan.vault_id), before_state)
        self.assertEqual(note_hashes(self.vault), before_notes)
        self.assertEqual(first.tx_id, second.tx_id)
    def test_changed_or_new_user_file_survives_cleanup(self):
        plan = self.plan()
        changed = next(row.source for row in plan.entries if row.action == "remove-owned")
        sentinel = self.legacy / "keep.py"
        before_notes = note_hashes(self.vault)
        def concurrent(name):
            if name == "cleanup":
                changed.write_bytes(b"concurrent user edit")
                sentinel.write_bytes(b"new user file")
        result = self.apply(plan, fault=concurrent)
        self.assertFalse(result.success)
        self.assertEqual(changed.read_bytes(), b"concurrent user edit")
        self.assertEqual(sentinel.read_bytes(), b"new user file")
        self.assertEqual(note_hashes(self.vault), before_notes)
        self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
    def test_conflict_or_live_writer_prevents_activation(self):
        plan = self.plan()
        before = snapshot(self.root)
        result = self.apply(replace(plan, conflicts=("unresolved-state",)))
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.root), before)
        self.backend.busy = True
        result = self.apply(plan)
        self.assertFalse(result.success)
        self.assertIn("writer-active", result.conflicts)
        self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
    def test_sources_targets_and_external_are_revalidated(self):
        for source_type in ("state", "metadata", "absent", "external", "target"):
            with self.subTest(source_type=source_type):
                plan = self.plan()
                state = next(row for row in plan.entries if row.action == "copy-state")
                if source_type == "state":
                    state.source.write_bytes(b"changed-source")
                elif source_type == "metadata":
                    (self.vault / ".respected.json").write_bytes(b"changed-marker")
                elif source_type == "absent":
                    write_json(self.roots.data_root / "config.json", {"user_new":True})
                elif source_type == "external":
                    self.backend.records[("task", "fixture-task")] = b"user-external"
                else:
                    state.target.parent.mkdir(parents=True)
                    state.target.write_bytes(b"user-target")
                before_app = snapshot(self.roots.app_root)
                result = self.apply(plan)
                self.assertFalse(result.success, source_type)
                self.assertEqual(snapshot(self.roots.app_root), before_app)
                if source_type == "state":
                    state.source.write_bytes(b'{"session_id":"saved","status":"ok"}')
                elif source_type == "metadata":
                    write_json(self.vault / ".respected.json", {"schema_version":2,"vault_id":UUID_TEXT,"runtime_path":str(self.legacy),"custom_marker":9})
                elif source_type == "absent":
                    (self.roots.data_root / "config.json").unlink()
                elif source_type == "external":
                    self.backend.records.pop(("task", "fixture-task"))
                else:
                    state.target.unlink()
    def test_old_uninstaller_is_never_executed(self):
        from respectedbrain.installation.legacy import INNO_KEY
        old = self.legacy / "unins000.exe"
        old.write_bytes(b"MZ-old-uninstaller")
        old.with_suffix(".dat").write_bytes(b"old-uninstaller-data")
        old.with_suffix(".txt").write_bytes(b"user installer notes")
        before = json.dumps({"values":{"InstallLocation":{"type":1,"data":str(self.legacy)},"UninstallString":{"type":1,"data":'"' + str(old) + '"'}},"subkeys":{}}).encode()
        after = json.dumps({"values":{"InstallLocation":{"type":1,"data":str(self.roots.app_root)},"UninstallString":{"type":1,"data":'"' + str(self.roots.app_root / "respectedbrain.exe") + '" uninstall'}},"subkeys":{}}).encode()
        self.backend.records[("registry", INNO_KEY)] = before
        original = self.backend.preview
        self.backend.preview = lambda ctx,**kw: (*original(ctx,**kw), ExternalChange("registry",INNO_KEY,before,after))
        with patch("subprocess.run", side_effect=AssertionError("migration executed a subprocess")):
            result = self.apply()
        self.assertTrue(result.success, result.conflicts)
        self.assertFalse(old.exists())
        self.assertFalse(old.with_suffix(".dat").exists())
        self.assertEqual(self.backend.read("registry", INNO_KEY), after)
        self.assertTrue(old.with_suffix(".txt").exists(), "Inno-like user file deleted")
        self.assertEqual(old.with_suffix(".txt").read_bytes(), b"user installer notes")
    def test_failed_health_restores_existing_config_and_application(self):
        first = self.apply()
        self.assertTrue(first.success, first.conflicts)
        # New preview over the retained user/state sources is independently safe.
        plan = self.plan()
        before_app = snapshot(self.roots.app_root)
        before_config = (self.roots.data_root / "config.json").read_bytes()
        with patch("respectedbrain.installation.payload.validate_installed_health", side_effect=OSError("health-failed")):
            result = self.apply(plan)
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.roots.app_root), before_app)
        self.assertEqual((self.roots.data_root / "config.json").read_bytes(), before_config)

    def test_real_child_writer_lease_prevents_activation(self):
        from respectedbrain.core.coordination import quiesce_writers
        self.backend.quiesce = lambda vault_id: quiesce_writers(self.roots.data_root, vault_id)
        plan = self.plan()
        source = """import sys
from pathlib import Path
from respectedbrain.core.context import AppContext
from respectedbrain.core.paths import AppPaths
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.core.coordination import writer_lease
p=AppPaths(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4])
with writer_lease(AppContext(p,{},ResourceCatalog())):
 print('ready',flush=True)
 sys.stdin.readline()
"""
        child = subprocess.Popen([sys.executable,"-c",source,str(self.roots.app_root),str(self.roots.data_root),str(self.vault),plan.vault_id], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            self.assertEqual(child.stdout.readline().strip(), "ready")
            result = self.apply(plan)
            self.assertFalse(result.success)
            self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
        finally:
            child.communicate("release\n", timeout=10)
        self.assertEqual(child.returncode, 0)
    def test_hardlinked_source_target_or_payload_cannot_activate(self):
        import os
        for variant in ("source", "target", "payload"):
            with self.subTest(variant=variant):
                plan = self.plan()
                row = next(item for item in plan.entries if item.action == "copy-state")
                link = self.root / ("hardlink-" + variant)
                target = row.source if variant == "source" else row.target if variant == "target" else self.package / "respectedbrain.exe"
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(row.source.read_bytes())
                os.link(target, link)
                try:
                    result = self.apply(plan)
                    self.assertFalse(result.success, variant)
                    self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
                finally:
                    link.unlink()
                    if variant == "target":
                        target.unlink()
    def test_completed_receipt_does_not_hide_later_source_or_receipt_edits(self):
        plan = self.plan()
        self.assertTrue(self.apply(plan).success)
        receipt = next((self.roots.data_root / "vaults" / plan.vault_id / "state/migration-receipts").glob("*.json"))
        original = receipt.read_bytes()
        receipt.write_bytes(original + b" ")
        self.assertFalse(self.apply(plan).success)
        receipt.write_bytes(original)
        row = next(item for item in plan.entries if item.action == "copy-state")
        row.source.write_bytes(b"new-source-content")
        self.assertFalse(self.apply(plan).success)
        self.assertEqual(row.source.read_bytes(), b"new-source-content")
        self.assertNotEqual(row.target.read_bytes(), b"new-source-content")
    def test_external_readback_mismatch_rolls_back_without_user_loss(self):
        before = snapshot(self.vault)
        def no_write(change):
            pass
        self.backend.apply = no_write
        result = self.apply()
        self.assertFalse(result.success)
        self.assertTrue(any("readback" in conflict for conflict in result.conflicts))
        self.assertEqual(snapshot(self.vault), before)
        self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
    def test_old_uninstaller_retained_without_active_new_app_registration(self):
        from respectedbrain.installation.legacy import INNO_KEY
        old = self.legacy / "unins000.exe"
        old.write_bytes(b"MZ-old")
        before = json.dumps({"values":{"InstallLocation":{"type":1,"data":str(self.legacy)},"UninstallString":{"type":1,"data":str(old)}},"subkeys":{}}).encode()
        self.backend.records[("registry",INNO_KEY)] = before
        result = self.apply()
        self.assertFalse(result.success)
        self.assertEqual(old.read_bytes(), b"MZ-old")
        self.assertEqual(self.backend.read("registry",INNO_KEY), before)

    def test_fault_at_every_phase_preserves_concurrent_legacy_edits(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                plan = self.plan()
                changed = next(row.source for row in plan.entries if row.action == "remove-owned")
                original = changed.read_bytes()
                sentinel = self.legacy / "keep.py"
                before_notes, before_app = note_hashes(self.vault), snapshot(self.roots.app_root)
                def fault(name):
                    if name == phase:
                        changed.write_bytes(b"concurrent-owned-edit")
                        sentinel.write_bytes(b"concurrent-new-file")
                        raise OSError("phase-user-edit:" + phase)
                result = self.apply(plan, fault=fault)
                self.assertFalse(result.success)
                self.assertEqual(changed.read_bytes(), b"concurrent-owned-edit")
                self.assertEqual(sentinel.read_bytes(), b"concurrent-new-file")
                self.assertEqual(note_hashes(self.vault), before_notes)
                self.assertEqual(snapshot(self.roots.app_root), before_app)
                changed.write_bytes(original)
                sentinel.unlink()
    def test_hardlink_created_at_health_cannot_be_committed(self):
        import os
        link = self.root / "late-hardlink"
        def fault(name):
            if name == "health":
                os.link(self.roots.app_root / "respectedbrain.exe", link)
        try:
            result = self.apply(fault=fault)
            self.assertFalse(result.success)
            self.assertEqual(link.read_bytes(), b"MZ-fixture")
        finally:
            link.unlink(missing_ok=True)

    def test_external_changed_after_health_is_preserved_and_not_committed(self):
        def fault(name):
            if name == "health":
                self.backend.records[("task", "fixture-task")] = b"concurrent-external"
        result = self.apply(fault=fault)
        self.assertFalse(result.success)
        self.assertEqual(self.backend.read("task", "fixture-task"), b"concurrent-external")
        self.assertTrue((self.legacy / "model_runner.py").exists())
        self.assertFalse((self.roots.app_root / "respectedbrain.exe").exists())
    def test_cleanup_phase_application_edit_is_preserved_and_not_committed(self):
        def fault(name):
            if name == "cleanup":
                (self.roots.app_root / "respectedbrain.exe").write_bytes(b"concurrent-app-edit")
        result = self.apply(fault=fault)
        self.assertFalse(result.success)
        self.assertEqual((self.roots.app_root / "respectedbrain.exe").read_bytes(), b"concurrent-app-edit")
        self.assertTrue((self.legacy / "model_runner.py").exists())
