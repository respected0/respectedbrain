"""Tests for Respected Brain Update CLI wrapper (update.py)."""

from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import update


class TestUpdateCli(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="respected-update-cli-test-"))
        self.fake_vault = self.tmp_dir / "RespectedOS"
        self.fake_vault.mkdir(parents=True, exist_ok=True)
        (self.fake_vault / ".respectedbrain-version").write_text("0.0.1\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_detect_default_vault_finds_vault(self):
        with patch("pathlib.Path.home", return_value=self.tmp_dir):
            detected = update._detect_default_vault()
            self.assertEqual(detected, self.fake_vault)

    @patch("subprocess.run")
    def test_update_main_runs_preview_and_apply(self, mock_run):
        mock_run.return_value.returncode = 0

        exit_code = update.main([
            "--vault-path", str(self.fake_vault),
            "--apply",
            "--platform", "portable",
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(mock_run.call_count, 2)  # preview + apply


if __name__ == "__main__":
    unittest.main(verbosity=2)
