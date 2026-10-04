"""Readonly legacy inventory contracts using temporary fixtures and a fake backend."""
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from uuid import UUID

from respectedbrain.core.paths import Roots
from respectedbrain.integrations.backend import ExternalChange, IntegrationProfile
from tests.foundation_support import snapshot, write_json

UUID_TEXT = "11111111-1111-4111-8111-111111111111"
ALL_FALSE = dict.fromkeys(("global", "mcp", "schedule", "shortcut"), False)

class Backend:
    def __init__(self):
        self.applied, self.quiesce_calls, self.reads = [], [], []
        self.documents = {}
    def read(self, kind, key):
        self.reads.append((kind, key))
        return self.documents.get((kind, key))
    def apply(self, change):
        self.applied.append(change)
    def restore(self, change):
        raise AssertionError("preview restored external state")
    @contextmanager
    def quiesce(self, vault_id):
        self.quiesce_calls.append(vault_id)
        yield
    def preview(self, ctx, *, desired, profile):
        return (ExternalChange("task", "test-schedule", self.read("task", "test-schedule"), b"disabled"),)


def seed_legacy(root: Path, *, layout: str):
    engine = root / "runtime" if layout == "nested" else root
    (engine / "engine/.state").mkdir(parents=True, exist_ok=True)
    (engine / "engine/.state/last-flush.json").write_text('{"session_id":"saved","status":"ok"}')
    (engine / "cache").mkdir()
    (engine / "cache/search_index.db").write_bytes(b"cache")
    (engine / "skills/custom").mkdir(parents=True)
    (engine / "skills/custom/SKILL.md").write_text("My personalized skill.")
    (engine / "instructions.md").write_text("My personalized instructions.")
    (engine / "model_runner.py").write_text("# fixture installed code")
    (engine / "events.py").write_text("# user file with product basename")
    write_json(engine / "config.json", {"summary_provider":"gemini", "provider_priority":["gemini","codex"], "integrations":ALL_FALSE, "custom_legacy":7})
    write_json(root / "install-manifest.json", {"schema_version":3, "files":[{"path":str(engine / "model_runner.py"), "sha256":hashlib.sha256((engine / "model_runner.py").read_bytes()).hexdigest(), "role":"application"}], "external":[]})

class FoundationMigrationPreviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.vault, self.legacy = self.root / "Türkçe 🧠 Vault", self.root / "legacy"
        self.vault.mkdir()
        (self.vault / "daily").mkdir()
        (self.vault / "daily/user.md").write_text("User notebook untouched.")
        self.roots = Roots(self.root / "app", self.root / "data", self.vault)
        self.backend = Backend()
        self.profile = IntegrationProfile("windows-native", ("respectedbrain.exe",), self.root / "home")
    def module(self):
        try:
            return importlib.import_module("respectedbrain.installation.migration")
        except ModuleNotFoundError:
            self.fail("Readonly migration service missing")
    def plan(self):
        return self.module().plan_migration(self.legacy, self.vault, roots=self.roots, backend=self.backend, profile=self.profile)
    def test_dry_run_has_zero_side_effects(self):
        seed_legacy(self.legacy, layout="flat")
        before = snapshot(self.root)
        with mock.patch.object(Path, "mkdir", side_effect=AssertionError("preview mkdir")), mock.patch.object(Path, "write_text", side_effect=AssertionError("preview write")):
            plan = self.plan()
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(self.backend.applied, [])
        self.assertEqual(self.backend.quiesce_calls, [])
        self.assertEqual(str(UUID(plan.vault_id)), plan.vault_id)
        self.assertFalse((self.vault / ".respected.json").exists())
        self.assertEqual(plan.external[0].kind, "task")
        doc = self.module().plan_document(plan)
        self.assertTrue(all(set(("source","target","action","sha256","ownership")) <= set(row) for row in doc["entries"]))
        self.assertEqual(doc["desired"], ALL_FALSE)
    def test_flat_nested_and_in_vault_legacy_inventory(self):
        for layout in ("flat","nested","vault","both"):
            with self.subTest(layout=layout):
                root = self.root / layout
                vault = root / "vault"
                vault.mkdir(parents=True)
                legacy = root / "legacy"
                if layout in ("flat","nested","both"):
                    seed_legacy(legacy, layout="nested" if layout == "nested" else "flat")
                if layout in ("vault","both"):
                    seed_legacy(vault / ".beyin", layout="flat")
                    (vault / ".claude/scripts/.state").mkdir(parents=True)
                    (vault / ".claude/scripts/.state/prompt_count.session").write_text("5")
                roots = Roots(root / "app", root / "data", vault)
                before = snapshot(root)
                plan = self.module().plan_migration(legacy, vault, roots=roots, backend=self.backend, profile=self.profile)
                self.assertTrue(any(row.action == "copy-state" for row in plan.entries))
                self.assertTrue(any(row.action == "rebuild-cache" for row in plan.entries))
                self.assertTrue(any(row.action == "preserve-override" for row in plan.entries))
                self.assertFalse(plan.conflicts, plan.conflicts)
                self.assertEqual(snapshot(root), before)
    def test_config_precedence_and_custom_overrides(self):
        seed_legacy(self.legacy, layout="flat")
        write_json(self.vault / ".respected.json", {"schema_version":2,"vault_id":UUID_TEXT,"companion":"Jarvis","custom_marker":9,"runtime_dir":str(self.legacy)})
        write_json(self.roots.data_root / "config.json", {"schema_version":3,"active_vault_id":UUID_TEXT,"vaults":{UUID_TEXT:{"path":str(self.vault),"settings":{},"unknown":42}},"preferences":{"summary_provider":"codex","provider_priority":["codex","claude"]},"integrations":ALL_FALSE,"custom":7})
        plan = self.plan()
        self.assertEqual(plan.vault_id, UUID_TEXT)
        self.assertEqual(plan.config["preferences"]["summary_provider"], "codex")
        self.assertEqual(plan.config["preferences"]["provider_priority"][0], "codex")
        self.assertEqual(plan.config["integrations"], ALL_FALSE)
        self.assertEqual(plan.config["custom"], 7)
        self.assertEqual(plan.config["vaults"][UUID_TEXT]["unknown"], 42)
        overrides = [row for row in plan.entries if row.action == "preserve-override"]
        self.assertTrue(overrides)
        self.assertTrue(all(row.target.is_relative_to(self.roots.data_root / "vaults" / plan.vault_id / "overrides") for row in overrides))
        user = next(row for row in plan.entries if row.source.name == "events.py")
        self.assertEqual((user.action, user.ownership), ("retain-user", "user"))
        owned = next(row for row in plan.entries if row.source.name == "model_runner.py")
        self.assertEqual((owned.action, owned.ownership), ("remove-owned", "manifest-match"))
        self.assertEqual(plan.config["vaults"][UUID_TEXT]["legacy_metadata"]["marker"]["custom_marker"], 9)
    def test_conflicting_state_and_reparse_target_block_activation(self):
        seed_legacy(self.legacy, layout="flat")
        write_json(self.vault / ".respected.json", {"schema_version":3,"vault_id":UUID_TEXT})
        other = self.vault / ".beyin/engine/.state/last-flush.json"
        other.parent.mkdir(parents=True)
        original = (self.legacy / "engine/.state/last-flush.json").read_bytes()
        for payload, conflict in ((original,False),(b"different",True)):
            with self.subTest(conflict=conflict):
                other.write_bytes(payload)
                plan = self.plan()
                self.assertEqual(bool(plan.conflicts), conflict, plan.conflicts)
        other.write_bytes(original)
        outside = self.root / "outside"
        outside.mkdir()
        target = self.roots.data_root / "vaults" / UUID_TEXT
        target.parent.mkdir(parents=True)
        try:
            target.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            if os.name != "nt":
                raise
            result = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(target), str(outside)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        before = snapshot(outside)
        self.assertTrue(self.plan().conflicts)
        self.assertEqual(snapshot(outside), before)
    def test_modified_manifest_owned_file_is_retained(self):
        seed_legacy(self.legacy, layout="flat")
        owned = self.legacy / "model_runner.py"
        owned.write_text("user modification after install")
        plan = self.plan()
        row = next(row for row in plan.entries if row.source == owned)
        self.assertEqual((row.action, row.ownership), ("retain-user", "user"))
    def test_external_preview_dependency_is_not_silently_empty(self):
        seed_legacy(self.legacy, layout="flat")
        self.backend.preview = None
        self.assertTrue(any("external-preview" in item for item in self.plan().conflicts))

    def test_old_data_root_config_and_state_are_preserved(self):
        seed_legacy(self.legacy, layout="flat")
        write_json(self.roots.data_root / "config.json", {"schema_version":2,"summary_provider":"codex","provider_priority":["codex","claude"],"integrations":ALL_FALSE,"custom_old_data":13})
        state = self.roots.data_root / "state/compile-state.json"
        write_json(state, {"cursor":"saved","ingested":{"2026-10-01.md":"digest"}})
        before = snapshot(self.root)
        plan = self.plan()
        self.assertEqual(plan.config["preferences"]["summary_provider"], "codex")
        state_entry = next(row for row in plan.entries if row.source == state)
        self.assertEqual(state_entry.action, "copy-state")
        self.assertEqual(state_entry.target, self.roots.data_root / "vaults" / plan.vault_id / "state/compile-state.json")
        self.assertEqual(snapshot(self.root), before)

    def test_inno_artifacts_require_exact_owned_registration(self):
        from respectedbrain.installation.legacy import INNO_KEY
        seed_legacy(self.legacy, layout="flat")
        executable = self.legacy / "unins000.exe"
        executable.write_bytes(b"old uninstaller never run")
        data = self.legacy / "unins000.dat"
        data.write_bytes(b"inno data")
        for location, expected in ((str(self.vault.parent / "other"), "retain-user"), (str(self.legacy), "remove-owned")):
            with self.subTest(location=location):
                self.backend.documents[("registry", INNO_KEY)] = json.dumps({"values":{"InstallLocation":{"type":1,"value":location},"UninstallString":{"type":1,"value":str(executable)}}}).encode()
                plan = self.plan()
                rows = [row for row in plan.entries if row.source in (executable, data)]
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(row.action == expected for row in rows))
                if expected == "remove-owned":
                    self.assertTrue(all(row.ownership == "registry-match" for row in rows))
        self.assertEqual(self.backend.applied, [])

    def test_invalid_legacy_provider_and_flags_cannot_silently_enable(self):
        seed_legacy(self.legacy, layout="flat")
        write_json(self.legacy / "config.json", {"summary_provider":[], "provider_priority":["unknown"],"provider_fallback":"no","integrations":{"global":"yes", "schedule":False}})
        plan = self.plan()
        self.assertEqual(plan.config["preferences"]["summary_provider"], "auto")
        self.assertEqual(plan.config["integrations"]["global"], False)
        self.assertTrue(any("invalid-integration" in item for item in plan.conflicts))

    def test_malformed_legacy_manifest_is_not_ownership(self):
        seed_legacy(self.legacy, layout="flat")
        write_json(self.legacy / "install-manifest.json", {"schema_version":2,"files":["model_runner.py"]})
        plan = self.plan()
        row = next(row for row in plan.entries if row.source.name == "model_runner.py")
        self.assertEqual(row.action, "retain-user")
        self.assertTrue(any("manifest" in item for item in plan.conflicts))

    def test_marker_and_current_config_have_hashes_for_apply_revalidation(self):
        seed_legacy(self.legacy, layout="flat")
        write_json(self.vault / ".respected.json", {"schema_version":3,"vault_id":UUID_TEXT,"custom":12})
        write_json(self.roots.data_root / "config.json", {"schema_version":3,"active_vault_id":UUID_TEXT,"vaults":{UUID_TEXT:{"path":str(self.vault)}},"preferences":{},"integrations":ALL_FALSE})
        plan = self.plan()
        for path in (self.vault / ".respected.json", self.roots.data_root / "config.json"):
            with self.subTest(path=path):
                row = next((row for row in plan.entries if row.source == path and row.action == "merge-config"), None)
                self.assertIsNotNone(row, "Mutable migration metadata needs a source hash in the preview")
                self.assertEqual(row.sha256, hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(row.target, path)

    def test_absent_marker_and_config_are_explicit_expected_absence(self):
        seed_legacy(self.legacy, layout="flat")
        plan = self.plan()
        for path in (self.vault / ".respected.json", self.roots.data_root / "config.json"):
            with self.subTest(path=path):
                row = next((row for row in plan.entries if row.source == path and row.target == path), None)
                self.assertIsNotNone(row)
                self.assertIsNone(row.sha256)
                self.assertEqual(row.action, "merge-config")
                self.assertFalse(path.exists())
