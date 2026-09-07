#!/usr/bin/env python3
"""Tests for opt-in verified Restic backup and private Git snapshot publisher (Faz 4)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
RESTIC_SCRIPT = ROOT / "scripts/backup_restic.py"
GIT_SNAPSHOT_SCRIPT = ROOT / "scripts/publish_git_snapshot.py"


def load_restic_module():
    spec = importlib.util.spec_from_file_location("restic_module", RESTIC_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_snapshot_module():
    spec = importlib.util.spec_from_file_location("snapshot_module", GIT_SNAPSHOT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BackupAndSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.restic = load_restic_module()
        self.snapshot = load_snapshot_module()

    # --- Restic Backup Tests ---

    def test_restic_preflight_checks_binary_presence(self):
        """Restic backup must fail closed with clear guidance if restic is missing."""
        with mock.patch("shutil.which", return_value=None):
            installed, message = self.restic.check_prerequisites()
            self.assertFalse(installed)
            self.assertIn("restic kurulu değil", message.lower())

    def test_restic_target_safety_aborts_when_inside_vault(self):
        """Restic backup must refuse to initialize repo inside the vault itself."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            inside_target = str(vault / "backups")

            with self.assertRaises(ValueError) as ctx:
                self.restic.check_target_safety(vault, inside_target)
            self.assertIn("vault içinde olamaz", str(ctx.exception))

            with mock.patch.object(self.restic, "check_prerequisites", return_value=(True, "restic")):
                result = self.restic.run_backup(vault, inside_target)
                self.assertEqual(result.get("status"), "error")
                self.assertIn("vault içinde olamaz", result.get("error", ""))

    def test_restic_target_safety_passes_when_outside_vault(self):
        """Restic target safety passes when repository is in an external location."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            vault = temp_path / "vault"
            vault.mkdir()
            outside_target = str(temp_path / "external_backups")

            # Must not raise
            self.restic.check_target_safety(vault, outside_target)

    def test_restic_preview_mode_returns_metadata_without_apply(self):
        """Without apply=True, run_backup returns preview metadata without running restic."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            vault = temp_path / "vault"
            vault.mkdir()
            target = str(temp_path / "backup_repo")

            with mock.patch.object(self.restic, "check_prerequisites", return_value=(True, "restic")):
                result = self.restic.run_backup(vault, target, apply=False)
                self.assertEqual(result.get("status"), "preview")
                self.assertEqual(result.get("vault"), str(vault))
                self.assertEqual(result.get("repo"), target)

    # --- Git Snapshot Tests ---

    def test_git_snapshot_secret_guard_aborts_on_nested_forbidden_files(self):
        """Git snapshot must abort on root and deep-nested secret files (.env, keys, credentials)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            nested = vault / "config" / "credentials"
            nested.mkdir(parents=True)

            (vault / ".env").write_text("API_KEY=123", encoding="utf-8")
            (vault / ".env.production").write_text("PROD_SECRET=456", encoding="utf-8")
            (nested / "aws_credentials.json").write_text('{"key": "secret"}', encoding="utf-8")
            (vault / "id_rsa").write_text("private key", encoding="utf-8")
            (vault / "server.pem").write_text("cert", encoding="utf-8")
            (vault / "note.md").write_text("# Regular note", encoding="utf-8")

            safe, forbidden = self.snapshot.check_secret_guard(vault)
            self.assertFalse(safe)
            self.assertGreaterEqual(len(forbidden), 5)
            self.assertTrue(any(".env" in f for f in forbidden))
            self.assertTrue(any("aws_credentials" in f for f in forbidden))
            self.assertTrue(any("id_rsa" in f for f in forbidden))

    def test_git_snapshot_secret_guard_passes_on_clean_vault(self):
        """Clean vault with standard notes and markdown documents must pass secret guard."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            (vault / "knowledge").mkdir()
            (vault / "knowledge" / "Architect.md").write_text("# Architecture", encoding="utf-8")
            (vault / "daily").mkdir()
            (vault / "daily" / "2026-09-07.md").write_text("# Today", encoding="utf-8")

            safe, forbidden = self.snapshot.check_secret_guard(vault)
            self.assertTrue(safe)
            self.assertEqual(forbidden, [])

    def test_git_snapshot_fails_closed_on_non_git_directory(self):
        """If directory is not a git repo, publish_if_due must halt fail-closed without crashing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            (vault / "note.md").write_text("# Note", encoding="utf-8")

            result = self.snapshot.publish_if_due(vault, remote="origin", branch="main")
            self.assertTrue(result.get("status", "").startswith("halted:"))
            self.assertIn("fail-closed", result.get("detail", "").lower())

    def test_git_snapshot_real_divergence_detection(self):
        """Test real divergence between local and remote git branches using actual git commands."""
        git = shutil.which("git")
        if git is None:
            self.skipTest("git is not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            remote_repo = temp_path / "remote.git"
            local_repo = temp_path / "local"

            # 1. Create bare remote
            subprocess.run([git, "init", "--bare", str(remote_repo)], check=True, capture_output=True)

            # 2. Clone to local
            subprocess.run([git, "clone", str(remote_repo), str(local_repo)], check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "test@test.com"], cwd=local_repo, check=True)
            subprocess.run([git, "config", "user.name", "Tester"], cwd=local_repo, check=True)

            # 3. Create and push initial commit
            (local_repo / "initial.md").write_text("# Initial", encoding="utf-8")
            subprocess.run([git, "add", "."], cwd=local_repo, check=True, capture_output=True)
            subprocess.run([git, "commit", "-m", "initial"], cwd=local_repo, check=True, capture_output=True)
            subprocess.run([git, "branch", "-M", "main"], cwd=local_repo, check=True, capture_output=True)
            subprocess.run([git, "push", "-u", "origin", "main"], cwd=local_repo, check=True, capture_output=True)

            # 4. In clean state, publish_if_due preview should show clean divergence
            preview = self.snapshot.publish_if_due(local_repo, remote="origin", branch="main", apply=False)
            self.assertEqual(preview.get("status"), "preview")
            self.assertEqual(preview.get("divergence"), "clean")

            # 5. Simulate remote advancement via a second clone
            other_clone = temp_path / "other"
            subprocess.run([git, "clone", str(remote_repo), str(other_clone)], check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "test@test.com"], cwd=other_clone, check=True)
            subprocess.run([git, "config", "user.name", "Tester"], cwd=other_clone, check=True)
            (other_clone / "remote_change.md").write_text("# Remote", encoding="utf-8")
            subprocess.run([git, "add", "."], cwd=other_clone, check=True, capture_output=True)
            subprocess.run([git, "commit", "-m", "remote commit"], cwd=other_clone, check=True, capture_output=True)
            subprocess.run([git, "push", "origin", "main"], cwd=other_clone, check=True, capture_output=True)

            # 6. Make competing local commit in local_repo
            (local_repo / "local_change.md").write_text("# Local", encoding="utf-8")
            subprocess.run([git, "add", "."], cwd=local_repo, check=True, capture_output=True)
            subprocess.run([git, "commit", "-m", "local commit"], cwd=local_repo, check=True, capture_output=True)

            # 7. Now local and remote have diverged!
            result = self.snapshot.publish_if_due(local_repo, remote="origin", branch="main", apply=True)
            self.assertEqual(result.get("status"), "halted:diverged")
            self.assertIn("fail-closed", result.get("detail", "").lower())


if __name__ == "__main__":
    unittest.main()
