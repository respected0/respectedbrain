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

    def test_restic_preflight_checks_binary_presence(self):
        """Restic backup must fail closed with clear guidance if restic is missing."""
        with mock.patch("shutil.which", return_value=None):
            installed, message = self.restic.check_prerequisites()
            self.assertFalse(installed)
            self.assertIn("restic kurulu değil", message.lower())

    def test_git_snapshot_secret_guard_aborts_on_forbidden_files(self):
        """Git snapshot must abort immediately if a secret file like .env is present in candidate paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            (vault / ".env").write_text("OPENAI_API_KEY=sk-1234567890", encoding="utf-8")
            (vault / "note.md").write_text("# Regular note", encoding="utf-8")

            safe, forbidden = self.snapshot.check_secret_guard(vault)
            self.assertFalse(safe)
            self.assertIn(".env", forbidden)

    def test_git_snapshot_aborts_on_divergence_without_pulling(self):
        """If local branch has diverged from remote, worker must halt without changing user files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            # Mock rev-parse to return diverged commit hashes
            with mock.patch.object(self.snapshot, "_branch_divergence_status", return_value="diverged"):
                result = self.snapshot.publish_if_due(vault, remote="origin", branch="main")
                self.assertEqual(result.get("status"), "halted:diverged")


if __name__ == "__main__":
    unittest.main()
