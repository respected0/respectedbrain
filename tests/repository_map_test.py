"""Exercise inventory drift gates against disposable real Git repositories."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "repository_map.py"


class RepositoryMapTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TOOL.is_file(), "repository inventory generator is missing")
        spec = importlib.util.spec_from_file_location("repository_map_under_test", TOOL)
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "first.py").write_text("print('one')\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("dist/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        self.entries = [self.entry(".gitignore"), self.entry("first.py")]

    def entry(self, path):
        return {"path": path, "role": "Denetim", "purpose": "Git fixture'ının gerçek dosyasını ve kapsam sözleşmesini tanımlar.",
                "relationships": ["Git envanteri tarafından okunur."], "review_sha256": self.tool.content_digest(self.root / path)}

    def errors(self, entries=None):
        return self.tool.validate_inventory(self.root, {"schema": 1, "files": entries if entries is not None else self.entries})

    def test_new_nonignored_file_is_missing_but_build_output_is_excluded(self):
        (self.root / "new.py").write_text("new", encoding="utf-8")
        (self.root / "dist").mkdir()
        (self.root / "dist" / "vendor.py").write_text("third party", encoding="utf-8")
        self.assertEqual(self.errors(), ["MISSING: new.py"])

    def test_ghost_entry_is_rejected(self):
        ghost = dict(self.entries[-1], path="ghost.py")
        self.assertIn("GHOST: ghost.py", self.errors(self.entries + [ghost]))

    def test_duplicate_entry_is_rejected(self):
        self.assertIn("DUPLICATE: first.py", self.errors(self.entries + [self.entries[-1]]))

    def test_changed_content_requires_semantic_review(self):
        (self.root / "first.py").write_text("print('different behavior')\n", encoding="utf-8")
        self.assertIn("STALE_DESCRIPTION: first.py", self.errors())

    def test_line_endings_do_not_create_false_semantic_drift(self):
        (self.root / "first.py").write_bytes(b"print('one')\r\n")
        self.assertEqual(self.errors(), [])

    def test_binary_content_is_not_line_ending_normalized(self):
        binary = self.root / "image.png"
        binary.write_bytes(b"\x89PNG\r\n\xff")
        before = self.tool.content_digest(binary)
        binary.write_bytes(b"\x89PNG\n\xff")
        self.assertNotEqual(self.tool.content_digest(binary), before)

    def test_unreviewed_discovery_is_visible_and_rejected(self):
        (self.root / "new.py").write_text("new", encoding="utf-8")
        inventory = self.tool.update_inventory(self.root, {"schema": 1, "files": self.entries})
        self.assertIn("NEEDS_REVIEW: new.py", self.tool.validate_inventory(self.root, inventory))
        self.assertIn("NEEDS_REVIEW", self.tool.render_map(inventory))

    def test_reviewed_explanation_may_explain_the_review_status_marker(self):
        self.entries[-1]["purpose"] = "Denetim testleri NEEDS_REVIEW durumundaki yeni kaydı reddeder."
        self.assertEqual(self.errors(), [])

    def test_staged_deletion_disappears_from_inventory(self):
        subprocess.run(["git", "-C", str(self.root), "rm", "-f", "first.py"], check=True, capture_output=True)
        updated = self.tool.update_inventory(self.root, {"schema": 1, "files": self.entries})
        self.assertEqual([entry["path"] for entry in updated["files"]], [".gitignore"])
        self.assertEqual(self.tool.validate_inventory(self.root, updated), [])

    def test_unstaged_missing_tracked_file_is_an_error(self):
        (self.root / "first.py").unlink()
        self.assertIn("MISSING_ON_DISK: first.py", self.errors())

    def test_map_drift_returns_failure_and_write_repairs_it(self):
        (self.root / "docs").mkdir()
        data = {"schema": 1, "files": self.entries + [
            {"path": "docs/repository_inventory.json", "role": "Envanter", "purpose": "İnsan açıklamaları için tek kaynak.", "relationships": ["Harita üreticisi okur."], "review_sha256": "generated"},
            {"path": "docs/REPOSITORY_MAP.md", "role": "Harita", "purpose": "Envanterden üretilmiş gezinme belgesi.", "relationships": ["JSON envanterinden üretilir."], "review_sha256": "generated"}]}
        (self.root / "docs/repository_inventory.json").write_text(json.dumps(data), encoding="utf-8")
        (self.root / "docs/REPOSITORY_MAP.md").write_text("outdated", encoding="utf-8")
        self.assertEqual(self.tool.main(["--root", str(self.root), "--check"]), 1)
        self.assertEqual(self.tool.main(["--root", str(self.root), "--write"]), 0)
        self.assertEqual(self.tool.main(["--root", str(self.root), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
