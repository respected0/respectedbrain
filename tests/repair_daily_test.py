#!/usr/bin/env python3
"""Comprehensive unit and CLI tests for scripts/repair_daily.py."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/repair_daily.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REPAIR_DAILY = load_module("repair_daily_module", SCRIPT_PATH)


class RepairDailyTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="repair-daily-test-")
        self.vault = Path(self.temporary.name)
        self.daily = self.vault / "daily"
        self.daily.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_repair_daily_file_not_found(self):
        non_existent = self.daily / "2026-01-01.md"
        with self.assertRaises(FileNotFoundError):
            REPAIR_DAILY.repair_daily_file(non_existent, self.vault)

    def test_repair_daily_file_single_block_creates_backup_and_returns_unmodified(self):
        target = self.daily / "2026-09-01.md"
        content = (
            "# Günlük Not: 2026-09-01\n\n"
            "### Oturum (10:00)\n\n"
            "## Bağlam\nTek oturum bağlamı.\n\n"
            "## Kararlar\nKarar 1.\n"
        )
        target.write_text(content, encoding="utf-8")

        modified, backup_path = REPAIR_DAILY.repair_daily_file(target, self.vault)

        self.assertFalse(modified)
        self.assertTrue(backup_path.is_file())
        self.assertEqual(backup_path.read_text(encoding="utf-8"), content)
        self.assertEqual(target.read_text(encoding="utf-8"), content)

    def test_repair_daily_file_exact_duplicate_blocks(self):
        target = self.daily / "2026-09-02.md"
        content = (
            "# Günlük Not: 2026-09-02\n\n"
            "### Oturum (10:00)\n\n"
            "## Bağlam\nÖnemli geliştirme bağlamı.\n\n"
            "## Kararlar\nYeni mimariye geçildi.\n\n"
            "### Oturum (10:05)\n\n"
            "## Bağlam\nÖnemli geliştirme bağlamı.\n\n"
            "## Kararlar\nYeni mimariye geçildi.\n"
        )
        target.write_text(content, encoding="utf-8")

        modified, backup_path = REPAIR_DAILY.repair_daily_file(target, self.vault)

        self.assertTrue(modified)
        self.assertTrue(backup_path.is_file())
        self.assertEqual(backup_path.read_text(encoding="utf-8"), content)

        repaired = target.read_text(encoding="utf-8")
        self.assertEqual(repaired.count("### Oturum"), 1)
        self.assertIn("### Oturum (10:00)", repaired)
        self.assertIn("Yeni mimariye geçildi.", repaired)

    def test_repair_daily_file_near_duplicate_picks_richer_body(self):
        target = self.daily / "2026-09-03.md"
        content = (
            "# Günlük Not: 2026-09-03\n\n"
            "### Oturum (14:00)\n\n"
            "## Bağlam\nMimari geliştirme ve test suite kurulumu.\n\n"
            "## Kararlar\nKarar 1.\n\n"
            "### Oturum (14:15)\n\n"
            "## Bağlam\nMimari geliştirme ve test suite kurulumu.\n\n"
            "## Kararlar\nKarar 1 ve ek olarak karar 2.\n"
        )
        target.write_text(content, encoding="utf-8")

        modified, backup_path = REPAIR_DAILY.repair_daily_file(target, self.vault)

        self.assertTrue(modified)
        repaired = target.read_text(encoding="utf-8")
        self.assertEqual(repaired.count("### Oturum"), 1)
        self.assertIn("### Oturum (14:00)", repaired)  # Earliest header
        self.assertIn("Karar 1 ve ek olarak karar 2.", repaired)  # Richer body

    def test_repair_daily_file_distinct_sessions_preserved(self):
        target = self.daily / "2026-09-04.md"
        content = (
            "# Günlük Not: 2026-09-04\n\n"
            "### Oturum (09:00)\n\n"
            "## Bağlam\nSabah brifingi.\n\n"
            "### Oturum (16:00)\n\n"
            "## Bağlam\nAkşam değerlendirmesi tamamen farklı bir konu.\n"
        )
        target.write_text(content, encoding="utf-8")

        modified, backup_path = REPAIR_DAILY.repair_daily_file(target, self.vault)

        self.assertFalse(modified)
        repaired = target.read_text(encoding="utf-8")
        self.assertEqual(repaired.count("### Oturum"), 2)
        self.assertIn("### Oturum (09:00)", repaired)
        self.assertIn("### Oturum (16:00)", repaired)

    def test_repair_all_daily_files_handles_missing_dir_and_hidden_files(self):
        empty_vault = Path(tempfile.mkdtemp())
        try:
            results = REPAIR_DAILY.repair_all_daily_files(empty_vault)
            self.assertEqual(results, [])

            # Create daily with .gitkeep
            (empty_vault / "daily").mkdir(parents=True)
            (empty_vault / "daily" / ".gitkeep").write_text("", encoding="utf-8")
            results = REPAIR_DAILY.repair_all_daily_files(empty_vault)
            self.assertEqual(results, [])
        finally:
            shutil.rmtree(empty_vault, ignore_errors=True)

    def test_repair_all_daily_files_processes_multiple_files(self):
        # File 1 has duplicate
        file1 = self.daily / "2026-08-01.md"
        file1.write_text(
            "### Oturum (10:00)\n\nİçerik.\n\n### Oturum (10:10)\n\nİçerik.\n",
            encoding="utf-8",
        )
        # File 2 is clean
        file2 = self.daily / "2026-08-02.md"
        file2.write_text("### Oturum (11:00)\n\nFarklı içerik.\n", encoding="utf-8")

        results = REPAIR_DAILY.repair_all_daily_files(self.vault)

        self.assertEqual(len(results), 2)
        r1_path, r1_modified, r1_backup = results[0]
        r2_path, r2_modified, r2_backup = results[1]

        self.assertEqual(r1_path.name, "2026-08-01.md")
        self.assertTrue(r1_modified)
        self.assertTrue(r1_backup.is_file())

        self.assertEqual(r2_path.name, "2026-08-02.md")
        self.assertFalse(r2_modified)
        self.assertTrue(r2_backup.is_file())

    def test_main_cli_help(self):
        with self.assertRaises(SystemExit) as cm:
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                REPAIR_DAILY.main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_main_cli_date_flag_missing_file_returns_1(self):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            rc = REPAIR_DAILY.main(
                ["--vault-root", str(self.vault), "--date", "2099-01-01"]
            )
        self.assertEqual(rc, 1)
        self.assertIn("bulunamadı", mock_stderr.getvalue())

    def test_main_cli_date_flag_success(self):
        target = self.daily / "2026-09-10.md"
        target.write_text(
            "### Oturum (08:00)\n\nTekrar.\n\n### Oturum (08:10)\n\nTekrar.\n",
            encoding="utf-8",
        )

        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            rc = REPAIR_DAILY.main(
                ["--vault-root", str(self.vault), "--date", "2026-09-10"]
            )
        self.assertEqual(rc, 0)
        self.assertIn("2026-09-10.md: temizlendi", mock_stdout.getvalue())

        # Second run: already clean
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            rc = REPAIR_DAILY.main(
                ["--vault-root", str(self.vault), "--date", "2026-09-10"]
            )
        self.assertEqual(rc, 0)
        self.assertIn("2026-09-10.md: değişiklik gerekmedi", mock_stdout.getvalue())

    def test_main_cli_vault_root_batch(self):
        target = self.daily / "2026-09-11.md"
        target.write_text("### Oturum (12:00)\n\nÖzet.\n", encoding="utf-8")

        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            rc = REPAIR_DAILY.main(["--vault-root", str(self.vault)])
        self.assertEqual(rc, 0)
        self.assertIn("2026-09-11.md: değişiklik gerekmedi", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
