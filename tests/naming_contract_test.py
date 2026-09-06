#!/usr/bin/env python3
"""Behavioral contracts for the Respected Brain namespace migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "respected_manifest.py"
LEGACY_NAMES = ROOT / "scripts" / "legacy_names.py"
FORBIDDEN_BRAND_FRAGMENTS = ("Respot Brain", "RESPOT", "Respot", "respot")


def find_forbidden_occurrences(
    root: Path,
    tracked_paths: tuple[Path, ...],
    allowlist: set[Path],
) -> list[tuple[Path, int, str]]:
    occurrences: list[tuple[Path, int, str]] = []
    for relative in tracked_paths:
        if relative in allowlist:
            continue
        try:
            lines = (root / relative).read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            for fragment in FORBIDDEN_BRAND_FRAGMENTS:
                if fragment in line:
                    occurrences.append((relative, line_number, fragment))
                    break
    return occurrences


def load_manifest():
    if not MANIFEST.is_file():
        return None
    spec = importlib.util.spec_from_file_location("respected_manifest", MANIFEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_legacy_names():
    if not LEGACY_NAMES.is_file():
        return None
    spec = importlib.util.spec_from_file_location("legacy_names", LEGACY_NAMES)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NamingContractTest(unittest.TestCase):
    def test_repository_current_surfaces_have_no_unallowlisted_legacy_brand(self):
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        paths = tuple(
            Path(line)
            for line in result.stdout.decode("utf-8", errors="replace").split("\0")
            if line
        )
        allowlist = {
            Path("docs/superpowers/plans/2026-09-02-respected-brain-rename.md"),
            Path("docs/superpowers/specs/2026-09-02-respected-brain-rename-design.md"),
            Path("tests/install_windows_test.ps1"),
            Path("tests/multiai_test.py"),
            Path("tests/naming_contract_test.py"),
            Path("tests/update_respected_test.py"),
        }

        occurrences = find_forbidden_occurrences(ROOT, paths, allowlist)

        self.assertEqual(occurrences, [])

    def test_current_public_guides_use_the_respected_1_3_contract(self):
        guides = {
            name: (ROOT / name).read_text(encoding="utf-8")
            for name in ("README.md", "SETUP.md", "SETUP-WINDOWS.md", "MULTI_AI.md")
        }
        combined = "\n".join(guides.values())

        for provider in ("Claude", "Codex", "Cursor", "Antigravity"):
            self.assertIn(provider, combined)
        for profile in ("portable", "windows-wsl", "windows-native"):
            self.assertIn(profile, combined)
        self.assertIn("Respected Brain", guides["README.md"])
        self.assertIn("https://github.com/respected0/respectedbrain.git", guides["README.md"])
        self.assertIn("cd respectedbrain", guides["README.md"])
        self.assertIn("scripts/update_respected.py", combined)
        self.assertIn("1.3.1", combined)
        self.assertIn(".respected/schedule-backups", combined)
        self.assertIn(".respected-brain-yedek", combined)
        self.assertIn("önizleme", combined.casefold())
        self.assertIn("--apply", combined)
        self.assertIn("Avenox Beyin", guides["README.md"])
        self.assertIn("MIT", guides["README.md"])

        for fragment in FORBIDDEN_BRAND_FRAGMENTS:
            for name, content in guides.items():
                self.assertNotIn(fragment, content, f"{name}: legacy current-facing name")

    def test_scanner_reports_legacy_brand_only_outside_the_allowlist(self):
        scanner = globals().get("find_forbidden_occurrences")
        self.assertIsNotNone(scanner, "naming-contract scanner is missing")
        with tempfile.TemporaryDirectory(prefix="respected-names-") as temporary:
            root = Path(temporary)
            (root / "current.txt").write_text("Respected Brain\n", encoding="utf-8")
            (root / "legacy.txt").write_text(
                "Respot Brain\nRESPOT-GLOBAL\nrespot-brain\n.respot-backups\n",
                encoding="utf-8",
            )
            (root / "historical.md").write_text("Respot Brain\n", encoding="utf-8")

            occurrences = scanner(
                root,
                (Path("current.txt"), Path("legacy.txt"), Path("historical.md")),
                {Path("historical.md")},
            )

        self.assertEqual(
            occurrences,
            [
                (Path("legacy.txt"), 1, "Respot Brain"),
                (Path("legacy.txt"), 2, "RESPOT"),
                (Path("legacy.txt"), 3, "respot"),
                (Path("legacy.txt"), 4, "respot"),
            ],
        )

    def test_legacy_identifiers_are_reconstructed_by_one_compatibility_module(self):
        legacy = load_legacy_names()

        self.assertIsNotNone(legacy, "scripts/legacy_names.py is missing")
        old_namespace = "res" + "pot"
        old_upper = "RES" + "POT"
        self.assertEqual(legacy.LEGACY_PRODUCT_NAME, "Res" + "pot Brain")
        self.assertEqual(legacy.LEGACY_NAMESPACE, old_namespace)
        self.assertEqual(
            legacy.LEGACY_GLOBAL_BEGIN,
            "<!-- " + old_upper + "-GLOBAL:BEGIN -->",
        )
        self.assertEqual(
            legacy.LEGACY_GLOBAL_END,
            "<!-- " + old_upper + "-GLOBAL:END -->",
        )
        self.assertEqual(legacy.LEGACY_HOOK_NAME, old_namespace + "-brain")
        self.assertEqual(legacy.LEGACY_CURSOR_RULE, old_namespace + "-brain.mdc")
        self.assertEqual(
            legacy.LEGACY_UPDATE_SCRIPT,
            "scripts/update_" + old_namespace + ".py",
        )
        self.assertEqual(
            legacy.LEGACY_MANIFEST_SCRIPT,
            "scripts/" + old_namespace + "_manifest.py",
        )
        self.assertEqual(
            legacy.LEGACY_TASK_PREFIX,
            old_namespace + "-morning-briefing-",
        )
        self.assertEqual(legacy.LEGACY_GLOBAL_BACKUP_ROOT, "." + old_namespace + "-backups")
        self.assertEqual(
            legacy.LEGACY_SCHEDULE_BACKUP_ROOT,
            "." + old_namespace + "/schedule-backups",
        )

    def test_current_manifest_targets_1_4_2_and_accepts_every_stamped_predecessor(self):
        manifest = load_manifest()

        self.assertIsNotNone(manifest, "scripts/respected_manifest.py is missing")
        self.assertEqual(manifest.MULTI_VERSION, "1.4.2")
        self.assertEqual(
            manifest.UPDATABLE_MULTI_VERSIONS,
            ("1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.3.1", "1.3.2", "1.4.0", "1.4.1", "1.4.2"),
        )
        self.assertNotIn("scripts/update_respot.py", manifest.RUNTIME)
        self.assertNotIn("scripts/respot_manifest.py", manifest.RUNTIME)


if __name__ == "__main__":
    unittest.main(verbosity=2)
