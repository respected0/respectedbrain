#!/usr/bin/env python3
"""Tests for Respected Brain Auto-Updater."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = (REPO_ROOT / "runtime" / "scripts") if (REPO_ROOT / "runtime" / "scripts").is_dir() else (REPO_ROOT / "scripts")
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from auto_updater import get_installed_version, verify_vault_integrity


class AutoUpdaterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_get_installed_version(self) -> None:
        self.assertEqual(get_installed_version(self.vault), "0.0.1")
        (self.vault / ".respectedbrain-version").write_text("1.2.0\n", encoding="utf-8")
        self.assertEqual(get_installed_version(self.vault), "1.2.0")

    def test_verify_vault_integrity(self) -> None:
        # Fails when missing companion dir
        valid, msg = verify_vault_integrity(self.vault)
        self.assertFalse(valid)
        self.assertIn("🔮 850-Companion", msg)

        # Passes when companion dir exists
        (self.vault / "🔮 850-Companion").mkdir(parents=True)
        valid, msg = verify_vault_integrity(self.vault)
        self.assertTrue(valid)


if __name__ == "__main__":
    unittest.main()
