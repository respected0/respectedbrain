"""Legacy update scenarios now exercise the hash-proved package migration service."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from respectedbrain.core.config import ConfigStore
from respectedbrain.core.paths import Roots
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.installation.migration import plan_migration,apply_migration,plan_document
from respectedbrain.integrations.backend import IntegrationProfile
from tests.foundation_install_support import seed_package
from tests.foundation_migration_apply_test import Backend
from tests.foundation_migration_preview_test import seed_legacy,ALL_FALSE,UUID_TEXT
from tests.foundation_support import snapshot,note_hashes,write_json

ROOT=Path(__file__).resolve().parents[1]

def tree_digest(root):
    return hashlib.sha256(json.dumps(snapshot(root),sort_keys=True).encode()).hexdigest()

class UpdateRespectedTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="respected-update-")
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.vault=self.root / "Ada Brain"
        with ResourceCatalog().materialize("vault-template") as template:
            shutil.copytree(template,self.vault)
        self.legacy=self.vault / ".beyin"
        seed_legacy(self.legacy,layout="flat")
        self.roots=Roots(self.root / "app",self.root / "data",self.vault)
        self.package=seed_package(self.root / "package")
        self.backend=Backend()
        self.profile=IntegrationProfile("windows-native",(str(self.roots.app_root / "respectedbrain.exe"),),self.root / "home")
        write_json(self.vault / ".respected.json",{"schema_version":2,"vault_id":UUID_TEXT,"runtime_dir":str(self.legacy),"custom":9})
        write_json(self.legacy / "config.json",{"summary_provider":"cursor","provider_priority":["cursor"],"provider_fallback":False,"personal_setting":{"keep":True},"integrations":ALL_FALSE})
        self.instructions=b"# Ada Brain\nPersonal instructions.\n"
        (self.legacy / "instructions.md").write_bytes(self.instructions)
        self.note=self.vault / "🧠 500-Knowledge/personal.md"
        self.note.write_bytes(b"personal notebook")
        self.legacy_update=self.vault / "scripts/update_legacy.py"
        self.legacy_update.parent.mkdir()
        self.legacy_update.write_bytes(b"unknown legacy updater")
        self.user_file=self.vault / "🏰 300-Projects/Ada/update_legacy.py"
        self.user_file.parent.mkdir()
        self.user_file.write_bytes(b"user helper")
        self.health=patch("respectedbrain.installation.payload.validate_installed_health",return_value=None)
        self.health.start()
        self.addCleanup(self.health.stop)
    def plan(self):
        return plan_migration(self.legacy,self.vault,roots=self.roots,backend=self.backend,profile=self.profile)
    def apply(self,plan=None,**kwargs):
        return apply_migration(plan or self.plan(),roots=self.roots,package=self.package,backend=self.backend,**kwargs)
    def backups(self):
        return sorted((self.roots.data_root / "backups").glob("tx-*"))
    def test_preview_is_read_only(self):
        before=snapshot(self.root)
        plan=self.plan()
        self.assertEqual(plan.conflicts,())
        self.assertEqual(snapshot(self.root),before)
        self.assertEqual(self.backups(),[])
        self.assertTrue(plan_document(plan)["entries"])
    def test_failed_gate_rolls_back_managed_files_and_keeps_old_marker(self):
        before=snapshot(self.vault)
        def fault(phase):
            if phase=="health": raise OSError("health gate failed")
        result=self.apply(fault=fault)
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.vault),before)
        self.assertEqual(len(self.backups()),1)
        journal=json.loads((self.backups()[0] / "journal.json").read_text())
        self.assertEqual(journal["status"],"rolled-back")
        self.assertTrue(any(row["path"]==str(self.legacy / "model_runner.py") and row["backup"] for row in journal["files"]))
    def test_apply_preserves_personal_data_and_activates_only_after_gates(self):
        before=note_hashes(self.vault)
        plan=self.plan()
        result=self.apply(plan)
        self.assertTrue(result.success,result.conflicts)
        self.assertEqual(note_hashes(self.vault),before)
        self.assertEqual((self.legacy / "instructions.md").read_bytes(),self.instructions)
        self.assertEqual((self.roots.data_root / "vaults" / plan.vault_id / "overrides/instructions/default.md").read_bytes(),self.instructions)
        preferences=ConfigStore(self.roots.data_root).read()["preferences"]
        self.assertEqual(preferences["summary_provider"],"cursor")
        self.assertEqual(preferences["personal_setting"],{"keep":True})
        self.assertFalse((self.vault / "scripts/respectedbrain.py").exists())
        self.assertEqual(self.legacy_update.read_bytes(),b"unknown legacy updater")
        self.assertEqual(self.user_file.read_bytes(),b"user helper")
        self.assertEqual(json.loads((self.roots.app_root / "distribution.json").read_text())["schema_version"],3)
    def test_unknown_exact_legacy_file_is_retained_without_filename_ownership(self):
        target=self.legacy / "model_runner.py"
        target.write_bytes(b"user owned replacement")
        self.assertEqual(next(row for row in self.plan().entries if row.source==target).action,"retain-user")
        result=self.apply()
        self.assertTrue(result.success,result.conflicts)
        self.assertEqual(target.read_bytes(),b"user owned replacement")
    def test_managed_link_is_rejected_without_mutation(self):
        target=self.legacy / "model_runner.py"
        linked=self.legacy / "linked.py"
        os.link(target,linked)
        before=snapshot(self.root)
        plan=self.plan()
        self.assertTrue(plan.conflicts)
        self.assertFalse(self.apply(plan).success)
        self.assertEqual(snapshot(self.root),before)
    def test_backup_and_staging_are_outside_the_vault(self):
        result=self.apply()
        self.assertTrue(result.success,result.conflicts)
        for directory in self.backups():
            self.assertFalse(directory.is_relative_to(self.vault))
            journal=json.loads((directory / "journal.json").read_text())
            stages=[Path(row["path"]) for row in journal["files"] if "/stage/" in row["path"].replace("\\","/")]
            self.assertTrue(stages)
            self.assertTrue(all(not path.is_relative_to(self.vault) for path in stages))
    def test_vault_contained_data_root_is_rejected(self):
        plan=self.plan()
        before=snapshot(self.root)
        from respectedbrain.core.errors import SelectionError
        with self.assertRaises(SelectionError):
            Roots(self.roots.app_root,self.vault / "unsafe-data",self.vault)
        self.assertEqual(snapshot(self.root),before)
    def test_root_target_is_rejected_before_any_scan_or_write(self):
        plan=self.plan()
        config=json.loads(json.dumps(plan.config))
        config["vaults"][plan.vault_id]["path"]=self.vault.anchor
        before=snapshot(self.root)
        result=self.apply(replace(plan,config=config))
        self.assertFalse(result.success)
        self.assertEqual(snapshot(self.root),before)
    def test_already_current_plan_is_successful_without_session_mutation(self):
        plan=self.plan()
        self.assertTrue(self.apply(plan).success)
        before=snapshot(self.roots.data_root / "vaults")
        self.assertTrue(self.apply(plan).success)
        self.assertEqual(snapshot(self.roots.data_root / "vaults"),before)
    def test_preview_output_survives_cp1252_console(self):
        # Fake backend prevents live HKCU/config reads in the child CLI.
        code="""import sys
from unittest.mock import patch
from tests.foundation_migration_apply_test import Backend
from respectedbrain.cli import main
with patch('respectedbrain.integrations.backend.NativeBackend',return_value=Backend()):
 raise SystemExit(main(sys.argv[1:]))
"""
        env={**os.environ,"RESPECTED_APP_DIR":str(self.roots.app_root),"RESPECTED_DATA_DIR":str(self.roots.data_root),"PYTHONIOENCODING":"cp1252"}
        result=subprocess.run([sys.executable,"-c",code,"migrate","--legacy-root",str(self.legacy),"--vault",str(self.vault),"--platform","windows-native"],env=env,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(b"vault_id",result.stdout)
    def test_legacy_vault_receives_package_without_new_engine_copies(self):
        before=note_hashes(self.vault)
        self.assertTrue(self.apply().success)
        self.assertTrue((self.roots.app_root / "respectedbrain.exe").is_file())
        self.assertFalse((self.legacy / "engine/flush.py").exists())
        self.assertEqual(note_hashes(self.vault),before)
    def test_current_vault_can_preview_and_apply_a_new_plan(self):
        self.assertTrue(self.apply().success)
        before=note_hashes(self.vault)
        self.assertTrue(self.apply().success)
        self.assertEqual(note_hashes(self.vault),before)
    def test_unstamped_vault_gets_plan_only_uuid_before_explicit_apply(self):
        marker=self.vault / ".respected.json"
        marker.unlink()
        before=snapshot(self.root)
        plan=self.plan()
        self.assertEqual(plan.conflicts,())
        self.assertEqual(snapshot(self.root),before)
        self.assertFalse(marker.exists())
        self.assertTrue(self.apply(plan).success)
        self.assertEqual(json.loads(marker.read_text())["vault_id"],plan.vault_id)
    def test_legacy_claude_scripts_migrate_only_with_hash_proof_and_preserve_user_code(self):
        scripts=self.vault / ".claude/scripts"
        scripts.mkdir(parents=True)
        managed=scripts / "flush.py"
        managed.write_bytes(b"old proven engine")
        user=scripts / "user_tool.py"
        user.write_bytes(b"custom tool")
        write_json(self.vault / "install-manifest.json",{"schema_version":3,"files":[{"path":str(managed),"sha256":hashlib.sha256(managed.read_bytes()).hexdigest(),"role":"application"}],"external":[]})
        self.assertTrue(self.apply().success)
        self.assertFalse(managed.exists())
        self.assertEqual(user.read_bytes(),b"custom tool")
        self.assertFalse((self.legacy / "engine/flush.py").exists())
    def test_legacy_claude_state_moves_to_uuid_state_without_deleting_source(self):
        state=self.vault / ".claude/scripts/.state/dummy.json"
        state.parent.mkdir(parents=True)
        state.write_bytes(b'{"session":"keep"}')
        plan=self.plan()
        self.assertTrue(self.apply(plan).success)
        destination=self.roots.data_root / "vaults" / plan.vault_id / "state/dummy.json"
        self.assertEqual(destination.read_bytes(),state.read_bytes())
        self.assertEqual(state.read_bytes(),b'{"session":"keep"}')
        self.assertFalse((self.legacy / "engine/.state").is_file())
    def test_changed_cleanup_source_survives_late_gate(self):
        owned=self.legacy / "model_runner.py"
        def fault(phase):
            if phase=="cleanup": owned.write_bytes(b"user edited at cleanup")
        result=self.apply(fault=fault)
        self.assertFalse(result.success)
        self.assertEqual(owned.read_bytes(),b"user edited at cleanup")
    def test_unknown_version_stamps_are_not_deleted_by_name(self):
        stamp=self.vault / ".beyin-version"
        stamp.write_bytes(b"user-stamp")
        self.assertTrue(self.apply().success)
        self.assertEqual(stamp.read_bytes(),b"user-stamp")

if __name__=="__main__":
    unittest.main()
