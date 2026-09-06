#!/usr/bin/env python3
"""Transactional update tests for stamped Respected Brain vaults."""

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
UPDATER = ROOT / "scripts" / "update_respected.py"


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


class UpdateRespectedTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="respected-update-")
        self.home = Path(self.temporary.name) / "home"
        self.transaction_root = Path(self.temporary.name) / "transactions"
        self.home.mkdir()
        self.transaction_root.mkdir()
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
        self.human_files = {
            "🔮 850-Companion/Core.md": b"# Furkan\n\nidentity\n",
            "🔮 850-Companion/Journal.md": b"# Journal\n\nprivate memory\n",
            "🔮 850-Companion/Threads.md": b"# Threads\n\n- ongoing\n",
            "daily/2026-09-01.md": b"# Yesterday\n\ncompleted item\n",
            "🏰 300-Projects/Ada/project.md": b"# Ada\n\nuser project\n",
        }
        for relative, content in self.human_files.items():
            path = self.vault / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        self.legacy_update = self.vault / "scripts/update_respot.py"
        self.legacy_manifest = self.vault / "scripts/respot_manifest.py"
        self.legacy_update.write_text(
            '#!/usr/bin/env python3\n"""Respot Brain managed updater."""\n'
            "import argparse\n"
            "from respot_manifest import MULTI_VERSION\n"
            "class UpdateError(RuntimeError):\n    pass\n"
            "def update(vault, requested_profile, apply):\n    return 0\n"
            "# supports --apply\n",
            encoding="utf-8",
        )
        self.legacy_manifest.write_text(
            '"""Version manifest shared by Respot migration tools."""\n'
            'CORE_VERSION = "2.0.0"\nMULTI_VERSION = "1.2.0"\n'
            "GENERATED = ()\nRUNTIME = ()\nSKILL_DESTINATIONS = ()\n",
            encoding="utf-8",
        )
        self.similarly_named_user_file = self.vault / "🏰 300-Projects/Ada/update_respot.py"
        self.similarly_named_user_file.write_bytes(b"user-owned helper\n")

    def tearDown(self):
        self.temporary.cleanup()

    def run_update(self, *arguments: str, env: dict[str, str] | None = None):
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "USERPROFILE": str(self.home),
                "TMPDIR": str(self.transaction_root),
                "TMP": str(self.transaction_root),
                "TEMP": str(self.transaction_root),
            }
        )
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
        root = self.home / ".respected" / "update-backups"
        return sorted(root.glob("*/*")) if root.exists() else []

    def transaction_directories(self) -> list[Path]:
        return sorted(self.transaction_root.glob("respected-update-*"))

    def test_preview_is_read_only(self):
        before = tree_digest(self.vault)

        result = self.run_update()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.vault), before)
        self.assertIn("ÖNİZLEME", result.stdout)
        self.assertEqual(self.backup_directories(), [])
        self.assertEqual(self.transaction_directories(), [])

    def test_failed_gate_rolls_back_managed_files_and_keeps_old_stamp(self):
        before = tree_digest(self.vault)

        result = self.run_update("--apply", env={"RESPECTED_TEST_FAIL_GATE": "render"})

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.vault), before)
        backups = self.backup_directories()
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / ".beyin/hooks/bridge.py").read_bytes(), self.old_bridge)
        manifest = json.loads(
            (backups[0] / "respected-update-manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("scripts/update_respot.py", manifest["legacy_removals"])
        self.assertIn(".beyin/config.json", manifest["targets"])
        self.assertEqual(self.transaction_directories(), [])

    def test_apply_preserves_personal_data_and_stamps_only_after_gates(self):
        instruction_before = (self.vault / ".beyin/instructions.md").read_bytes()
        note_before = self.note.read_bytes()

        result = self.run_update("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.vault / ".beyin-multi-version").read_text().strip(), "1.3.2")
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
        self.assertTrue((self.vault / "scripts/update_respected.py").is_file())
        self.assertTrue((self.vault / "scripts/respected_manifest.py").is_file())
        self.assertTrue((self.vault / "scripts/repair_daily.py").is_file())
        self.assertFalse(self.legacy_update.exists())
        self.assertFalse(self.legacy_manifest.exists())
        self.assertEqual(self.similarly_named_user_file.read_bytes(), b"user-owned helper\n")
        self.assertIn(self.instructions, (self.vault / "AGENTS.md").read_text(encoding="utf-8"))
        for relative, content in self.human_files.items():
            self.assertEqual((self.vault / relative).read_bytes(), content)
        backups = self.backup_directories()
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / ".beyin/hooks/bridge.py").read_bytes(), self.old_bridge)
        self.assertEqual(self.transaction_directories(), [])
        self.assertIn("Güncelleme sonrası dış bağlantılar", result.stdout)
        self.assertIn("install_global.py", result.stdout)
        self.assertIn("install_briefing_schedule.py", result.stdout)
        self.assertIn("Ayarlar > Hooks", result.stdout)
        self.assertIn("/hooks", result.stdout)

    def test_unknown_exact_legacy_file_fails_closed_without_mutation(self):
        self.legacy_update.write_bytes(b"user-owned file at an old managed path\n")
        before = tree_digest(self.vault)

        result = self.run_update("--apply")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.vault), before)
        self.assertIn("sahipliği doğrulanamadı", result.stdout + result.stderr)
        self.assertEqual(self.backup_directories(), [])
        self.assertEqual(self.transaction_directories(), [])

    @unittest.skipIf(os.name == "nt", "POSIX symlink semantics")
    def test_managed_symlink_is_rejected_without_mutation(self):
        bridge = self.vault / ".beyin/hooks/bridge.py"
        bridge.unlink()
        bridge.symlink_to(self.note)
        before = tree_digest(self.vault)

        result = self.run_update("--apply")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.vault), before)
        self.assertIn("sembolik bağlantı", result.stdout + result.stderr)
        self.assertEqual(self.backup_directories(), [])

    def test_backup_and_staging_are_outside_the_vault(self):
        result = self.run_update("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backups = self.backup_directories()
        self.assertEqual(len(backups), 1)
        self.assertFalse(backups[0].is_relative_to(self.vault))
        self.assertEqual(self.transaction_directories(), [])

    def test_vault_contained_staging_and_backup_roots_are_rejected(self):
        inside_temp = self.vault / ".transaction-temp"
        inside_temp.mkdir()
        before_staging = tree_digest(self.vault)

        staging_result = self.run_update(
            "--apply",
            env={
                "TMPDIR": str(inside_temp),
                "TMP": str(inside_temp),
                "TEMP": str(inside_temp),
            },
        )

        self.assertNotEqual(staging_result.returncode, 0, staging_result.stdout + staging_result.stderr)
        self.assertEqual(tree_digest(self.vault), before_staging)
        self.assertIn("staging alanı vault dışında", staging_result.stdout + staging_result.stderr)

        before_backup = tree_digest(self.vault)
        backup_result = self.run_update(
            "--apply",
            env={
                "HOME": str(self.vault),
                "USERPROFILE": str(self.vault),
            },
        )

        self.assertNotEqual(backup_result.returncode, 0, backup_result.stdout + backup_result.stderr)
        self.assertEqual(tree_digest(self.vault), before_backup)
        self.assertIn("yedeği vault dışında", backup_result.stdout + backup_result.stderr)

    def test_root_target_is_rejected(self):
        result = subprocess.run(
            [sys.executable, str(UPDATER), Path(self.vault.anchor), "--apply"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("geçersiz vault yolu", result.stdout + result.stderr)

    def test_already_current_vault_returns_three_without_mutation(self):
        (self.vault / ".beyin-multi-version").write_text("1.3.2\n", encoding="utf-8")
        before = tree_digest(self.vault)

        result = self.run_update("--apply")

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(tree_digest(self.vault), before)
        self.assertEqual(self.backup_directories(), [])
        self.assertEqual(self.transaction_directories(), [])
        self.assertIn("Güncelleme sonrası dış bağlantılar", result.stdout)
        self.assertIn("install_global.py", result.stdout)
        self.assertIn("install_briefing_schedule.py", result.stdout)

    def test_post_update_guidance_survives_a_cp1252_windows_console(self):
        (self.vault / ".beyin-multi-version").write_text("1.3.2\n", encoding="utf-8")
        environment = os.environ.copy()
        environment["HOME"] = str(self.home)
        environment["USERPROFILE"] = str(self.home)
        environment["PYTHONIOENCODING"] = "cp1252"

        result = subprocess.run(
            [
                sys.executable,
                str(UPDATER),
                str(self.vault),
                "--platform",
                "portable",
                "--apply",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(b"install_global.py", result.stdout)

    def test_1_3_0_vault_receives_the_patch_release(self):
        (self.vault / ".beyin-multi-version").write_text("1.3.0\n", encoding="utf-8")

        result = self.run_update("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (self.vault / ".beyin-multi-version").read_text().strip(),
            "1.3.2",
        )

    def test_1_3_1_vault_receives_the_patch_release(self):
        (self.vault / ".beyin-multi-version").write_text("1.3.1\n", encoding="utf-8")

        result = self.run_update("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (self.vault / ".beyin-multi-version").read_text().strip(),
            "1.3.2",
        )

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
