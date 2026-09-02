#!/usr/bin/env python3
"""Transactional migration tests for global Respected Brain identities."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install_global.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEGACY = load("global_migration_legacy_names", ROOT / "scripts/legacy_names.py")
INSTALLER_MODULE = load("global_migration_installer", INSTALLER)


def tree_digest(root: Path, *, exclude_backups: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        if exclude_backups:
            directories[:] = [name for name in directories if name != ".respected-backups"]
        directories.sort()
        for name in sorted(files):
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            metadata = path.lstat()
            digest.update(relative.encode("utf-8"))
            digest.update(str(stat.S_IMODE(metadata.st_mode)).encode("ascii"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


class GlobalBrandMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respected-global-")
        root = Path(self.temporary.name)
        self.vault = root / "Ada Brain"
        self.home = root / "home"
        shutil.copytree(ROOT / "template", self.vault)
        self.home.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def run_installer(self, *arguments: str):
        return subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                str(self.vault),
                "--home",
                str(self.home),
                *arguments,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def legacy_block(self) -> str:
        return (
            f"{LEGACY.LEGACY_GLOBAL_BEGIN}\n"
            "# Legacy managed content\n"
            f"{LEGACY.LEGACY_GLOBAL_END}"
        )

    def seed_legacy_install(self):
        for relative in (".gemini", ".codex", ".claude", ".cursor/rules"):
            (self.home / relative).mkdir(parents=True, exist_ok=True)
        for relative in (".gemini/GEMINI.md", ".codex/AGENTS.md", ".claude/CLAUDE.md"):
            (self.home / relative).write_text(
                "# Personal rule\n\n" + self.legacy_block() + "\n",
                encoding="utf-8",
            )
        (self.home / ".gemini/config").mkdir(parents=True)
        (self.home / ".gemini/config/hooks.json").write_text(
            json.dumps(
                {
                    "personal-hook": {"enabled": True},
                    LEGACY.LEGACY_HOOK_NAME: {"legacy": True},
                }
            ),
            encoding="utf-8",
        )
        (self.home / ".cursor/rules" / LEGACY.LEGACY_CURSOR_RULE).write_text(
            "---\nalwaysApply: true\n---\n\n" + self.legacy_block() + "\n",
            encoding="utf-8",
        )

    def test_preview_is_read_only_and_apply_migrates_all_legacy_identities_idempotently(self):
        self.seed_legacy_install()
        before = tree_digest(self.home)

        preview = self.run_installer("--providers", "all")

        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertEqual(tree_digest(self.home), before)
        self.assertIn("ÖNİZLEME", preview.stdout)

        applied = self.run_installer("--providers", "all", "--apply")

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        for relative in (".gemini/GEMINI.md", ".codex/AGENTS.md", ".claude/CLAUDE.md"):
            content = (self.home / relative).read_text(encoding="utf-8")
            self.assertIn("# Personal rule", content)
            self.assertEqual(content.count("<!-- RESPECTED-GLOBAL:BEGIN -->"), 1)
            self.assertNotIn(LEGACY.LEGACY_GLOBAL_BEGIN, content)
        hooks = json.loads(
            (self.home / ".gemini/config/hooks.json").read_text(encoding="utf-8")
        )
        self.assertIn("personal-hook", hooks)
        self.assertIn("respected-brain", hooks)
        self.assertNotIn(LEGACY.LEGACY_HOOK_NAME, hooks)
        self.assertTrue((self.home / ".cursor/rules/respected-brain.mdc").is_file())
        self.assertFalse((self.home / ".cursor/rules" / LEGACY.LEGACY_CURSOR_RULE).exists())
        self.assertTrue((self.home / ".respected-backups").is_dir())

        first = tree_digest(self.home, exclude_backups=True)
        backup_count = len(tuple((self.home / ".respected-backups").iterdir()))
        repeated = self.run_installer("--providers", "all", "--apply")

        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual(tree_digest(self.home, exclude_backups=True), first)
        self.assertEqual(
            len(tuple((self.home / ".respected-backups").iterdir())),
            backup_count,
        )

    def test_current_and_legacy_blocks_collide_without_mutation(self):
        rule = self.home / ".codex/AGENTS.md"
        rule.parent.mkdir(parents=True)
        rule.write_text(
            self.legacy_block()
            + "\n\n<!-- RESPECTED-GLOBAL:BEGIN -->\ncurrent\n<!-- RESPECTED-GLOBAL:END -->\n",
            encoding="utf-8",
        )
        before = tree_digest(self.home)

        result = self.run_installer("--providers", "codex", "--apply")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.home), before)
        self.assertIn("çakış", (result.stdout + result.stderr).casefold())

    def test_unverified_legacy_cursor_rule_fails_closed(self):
        rule = self.home / ".cursor/rules" / LEGACY.LEGACY_CURSOR_RULE
        rule.parent.mkdir(parents=True)
        rule.write_text("# User-owned file\n", encoding="utf-8")
        before = tree_digest(self.home)

        result = self.run_installer("--providers", "cursor", "--apply")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.home), before)
        self.assertIn("doğrulan", (result.stdout + result.stderr).casefold())

    def test_failed_apply_removes_new_files_and_directories_after_rollback(self):
        writes = [
            (self.home / ".codex/hooks.json", "{}\n"),
            (self.home / ".codex/AGENTS.md", "managed\n"),
        ]
        original_write = INSTALLER_MODULE.write_text
        calls = 0

        def fail_second_write(path: Path, content: str):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected-write-failure")
            original_write(path, content)

        with mock.patch.object(INSTALLER_MODULE, "write_text", side_effect=fail_second_write):
            with self.assertRaisesRegex(OSError, "injected-write-failure"):
                INSTALLER_MODULE.apply_plan(
                    writes,
                    self.home,
                    self.home / ".respected-backups/test",
                )

        self.assertFalse((self.home / ".codex").exists())

    def test_legacy_and_current_backup_roots_conflict_without_merge_or_deletion(self):
        legacy_root = self.home / LEGACY.LEGACY_GLOBAL_BACKUP_ROOT
        current_root = self.home / ".respected-backups"
        legacy_root.mkdir()
        current_root.mkdir()
        (legacy_root / "keep.txt").write_bytes(b"legacy backup\n")
        (current_root / "keep.txt").write_bytes(b"current backup\n")
        before = tree_digest(self.home)

        preview = self.run_installer("--providers", "codex")
        applied = self.run_installer("--providers", "codex", "--apply")

        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertIn("yedek kökleri çakışıyor", (preview.stdout + preview.stderr).casefold())
        self.assertEqual(applied.returncode, 2, applied.stdout + applied.stderr)
        self.assertIn("ayrı migration kararı", (applied.stdout + applied.stderr).casefold())
        self.assertEqual(tree_digest(self.home), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
