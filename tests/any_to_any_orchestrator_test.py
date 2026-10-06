#!/usr/bin/env python3
"""Tests for Respected Brain Any-to-Any AI Orchestrator."""

from __future__ import annotations

import json
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import sys

from respectedbrain.orchestration.runner import OrchestrationRun, slugify, get_cli_command


class AnyToAnyOrchestratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name) / "test_repo"
        self.repo.mkdir(parents=True)

        # Initialize test git repo
        subprocess.run(["git", "init"], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, capture_output=True, check=True)

        (self.repo / "README.md").write_text("# Test Repo\nInitial content\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo, capture_output=True, check=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_slugify(self) -> None:
        self.assertEqual(slugify("Add SQLite FTS Index!"), "add-sqlite-fts-index")
        self.assertEqual(slugify("   multiple   spaces  --- "), "multiple-spaces")

    def test_worktree_isolation_setup(self) -> None:
        run = OrchestrationRun(
            task="Add Feature X",
            master="codex",
            worker="antigravity",
            repo_root=self.repo,
            state_root=Path(self.temp_dir.name) / "data-state",
        )
        success = run.setup_worktree()
        self.assertTrue(success)
        self.assertTrue(run.worktree_dir.is_dir())
        self.assertTrue((run.worktree_dir / "README.md").is_file())
        # Instructions live in run state; a repository TASK_SPEC may be user-owned.
        self.assertTrue((run.run_dir / "TASK_SPEC.md").is_file())
        self.assertTrue((run.run_dir / "metadata.json").is_file())

        meta = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["master"], "codex")
        self.assertEqual(meta["worker"], "antigravity")
        self.assertEqual(meta["status"], "setting_up")

        # Cleanup
        run.cleanup_worktree()
        self.assertFalse(run.worktree_dir.is_dir())

    def test_patch_collection(self) -> None:
        run = OrchestrationRun(
            task="Update Readme",
            master="user",
            worker="user",
            repo_root=self.repo,
            state_root=Path(self.temp_dir.name) / "data-state",
        )
        self.assertTrue(run.setup_worktree())

        # Simulate worker modification inside worktree
        (run.worktree_dir / "README.md").write_text("# Test Repo\nModified by worker!\n", encoding="utf-8")

        # Collect patch
        with contextlib.redirect_stdout(io.StringIO()):
            run.collect_patch(exit_code=0, test_passed=True, duration=1.5)

        patch_file = run.run_dir / "worker.patch"
        self.assertTrue(patch_file.is_file())
        patch_text = patch_file.read_text(encoding="utf-8")
        self.assertIn("+Modified by worker!", patch_text)

        result_file = run.run_dir / "result.json"
        self.assertTrue(result_file.is_file())
        res = json.loads(result_file.read_text(encoding="utf-8"))
        self.assertEqual(res["status"], "completed")
        self.assertTrue(res["has_patch"])

        run.cleanup_worktree()


if __name__ == "__main__":
    unittest.main()
