#!/usr/bin/env python3
"""Transactional update tests for stamped Respot Brain vaults."""

from __future__ import annotations

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


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update_respot.py"


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(name for name in directories if name != ".git")
        for name in [*directories, *sorted(files)]:
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            metadata = path.lstat()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(stat.S_IMODE(metadata.st_mode)).encode("ascii"))
            digest.update(b"\0")
            if stat.S_ISLNK(metadata.st_mode):
                digest.update(os.readlink(path).encode("utf-8"))
            elif stat.S_ISREG(metadata.st_mode):
                digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


class UpdateRespotTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respot-update-")
        self.vault = Path(self.temporary.name) / "Ada Brain"
        shutil.copytree(ROOT / "template", self.vault)
        (self.vault / ".beyin-version").write_text("2.0.0\n", encoding="utf-8")
        (self.vault / ".beyin-multi-version").write_text("1.1.0\n", encoding="utf-8")
        self.instructions = "# Ada Brain\n\nKişisel ve kalıcı talimat.\n"
        (self.vault / ".beyin/instructions.md").write_text(self.instructions, encoding="utf-8")
        config = json.loads((self.vault / ".beyin/config.json").read_text(encoding="utf-8"))
        config["summary_provider"] = "cursor"
        config["personal_setting"] = {"keep": True}
        (self.vault / ".beyin/config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.old_bridge = b"# old managed bridge\n"
        (self.vault / ".beyin/hooks/bridge.py").write_bytes(self.old_bridge)
        (self.vault / ".beyin/map_builder.py").unlink()
        (self.vault / ".beyin/morning_briefing.py").unlink()
        self.note = self.vault / "🧠 500-Knowledge" / "personal.md"
        self.note.parent.mkdir(exist_ok=True)
        self.note.write_bytes(b"personal note must survive\n")

    def tearDown(self):
        self.temporary.cleanup()

    def run_update(self, *arguments: str, env: dict[str, str] | None = None):
        environment = os.environ.copy()
        if env:
            environment.update(env)
        return subprocess.run(
            [sys.executable, str(UPDATER), str(self.vault), *arguments],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def backup_directories(self) -> list[Path]:
        root = self.vault / ".beyin/backups"
        return sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []

    def test_preview_is_read_only(self):
        before = tree_digest(self.vault)

        result = self.run_update()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.vault), before)
        self.assertIn("ÖNİZLEME", result.stdout)
        self.assertEqual(self.backup_directories(), [])

    def test_failed_gate_rolls_back_managed_files_and_keeps_old_stamp(self):
        result = self.run_update("--apply", env={"RESPOT_TEST_FAIL_GATE": "render"})

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.vault / ".beyin-multi-version").read_text().strip(), "1.1.0")
        self.assertEqual((self.vault / ".beyin/hooks/bridge.py").read_bytes(), self.old_bridge)
        backups = self.backup_directories()
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / ".beyin/hooks/bridge.py").read_bytes(), self.old_bridge)

    def test_apply_preserves_personal_data_and_stamps_only_after_gates(self):
        instruction_before = (self.vault / ".beyin/instructions.md").read_bytes()
        note_before = self.note.read_bytes()

        result = self.run_update("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.vault / ".beyin-multi-version").read_text().strip(), "1.2.0")
        self.assertEqual((self.vault / ".beyin-version").read_text().strip(), "2.0.0")
        self.assertEqual((self.vault / ".beyin/instructions.md").read_bytes(), instruction_before)
        self.assertEqual(self.note.read_bytes(), note_before)
        config = json.loads((self.vault / ".beyin/config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["summary_provider"], "cursor")
        self.assertEqual(config["personal_setting"], {"keep": True})
        self.assertEqual(config["platform"], "portable")
        self.assertTrue((self.vault / ".beyin/runtime_platform.py").is_file())
        self.assertTrue((self.vault / ".beyin/hooks/lifecycle.py").is_file())
        self.assertTrue((self.vault / ".beyin/map_builder.py").is_file())
        self.assertTrue((self.vault / ".beyin/morning_briefing.py").is_file())
        self.assertTrue((self.vault / "scripts/install_briefing_schedule.py").is_file())
        self.assertIn(self.instructions, (self.vault / "AGENTS.md").read_text(encoding="utf-8"))
        backups = self.backup_directories()
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / ".beyin/hooks/bridge.py").read_bytes(), self.old_bridge)

    def test_unstamped_v1_and_unknown_versions_are_rejected_without_mutation(self):
        cases = (
            (None, "1.0.0"),
            ("9.9.9", "1.0.0"),
            ("2.0.0", "9.9.9"),
        )
        for index, (core, multi) in enumerate(cases):
            vault = Path(self.temporary.name) / f"invalid-{index}"
            shutil.copytree(self.vault, vault)
            core_path = vault / ".beyin-version"
            if core is None:
                core_path.unlink()
            else:
                core_path.write_text(f"{core}\n", encoding="utf-8")
            (vault / ".beyin-multi-version").write_text(f"{multi}\n", encoding="utf-8")
            before = tree_digest(vault)

            result = subprocess.run(
                [sys.executable, str(UPDATER), str(vault), "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(tree_digest(vault), before)
            self.assertIn("sürüm", (result.stdout + result.stderr).casefold())


if __name__ == "__main__":
    unittest.main()
