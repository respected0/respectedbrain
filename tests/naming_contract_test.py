#!/usr/bin/env python3
"""Behavioral contracts for the Respected Brain namespace migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (ROOT / "runtime" / "scripts" / "respected_manifest.py") if (ROOT / "runtime" / "scripts" / "respected_manifest.py").is_file() else (ROOT / "scripts" / "respected_manifest.py")
LEGACY_NAMES = (ROOT / "runtime" / "scripts" / "legacy_names.py") if (ROOT / "runtime" / "scripts" / "legacy_names.py").is_file() else (ROOT / "scripts" / "legacy_names.py")
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
            and not Path(line).is_relative_to("qa-evidence")
            and not Path(line).is_relative_to("qa-workspaces")
        )
        allowlist = {
            Path("tests/install_windows_test.ps1"),
            Path("tests/multiai_test.py"),
            Path("tests/naming_contract_test.py"),
            Path("tests/update_respected_test.py"),
        }

        occurrences = find_forbidden_occurrences(ROOT, paths, allowlist)

        self.assertEqual(occurrences, [])

    def test_current_public_guides_use_the_modular_native_contract(self):
        guides = {
            name: (ROOT / "docs/guides" / name if name != "README.md" else ROOT / name).read_text(encoding="utf-8")
            for name in ("README.md", "SETUP.md", "SETUP-WINDOWS.md", "MULTI_AI.md", "UPDATE.md")
        }
        combined = "\n".join(guides.values())

        for provider in ("Claude", "Codex", "Cursor", "Antigravity"):
            self.assertIn(provider, combined)
        for profile in ("windows-wsl", "windows-native"):
            self.assertIn(profile, combined)
        self.assertIn("Respected Brain", guides["README.md"])
        self.assertIn("https://github.com/respected0/respectedbrain", guides["README.md"])
        for current in ("respectedbrain", "--vault-id", "DataRoot", "AppRoot"):
            self.assertIn(current, combined)
        for retired in ("scripts/update_respected.py", ".respected/schedule-backups", ".respected/update-backups"):
            self.assertNotIn(retired, combined)
        self.assertIn("önizleme", combined.casefold())
        self.assertIn("--apply", combined)
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

    def test_current_manifest_uses_package_version_and_schema3_uuid_marker(self):
        from importlib.metadata import version
        from tests.foundation_support import make_context
        from uuid import UUID
        import json
        manifest=load_manifest()
        self.assertEqual(manifest.VERSION,version("respectedbrain"))
        with tempfile.TemporaryDirectory() as temporary:
            ctx=make_context(Path(temporary))
            marker=json.loads((ctx.paths.vault_root / ".respected.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["schema_version"],3)
            self.assertEqual(str(UUID(marker["vault_id"])),ctx.paths.vault_id)
            self.assertFalse((ctx.paths.vault_root / ".respectedbrain-version").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
