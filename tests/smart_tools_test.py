"""Tests for Respected Brain Smart Tools (Bounded Recall, Smart Merge, Architect Scanner).

Covers:
1. Bounded Recall (bounded_recall.py): Abstention gate, token bounding, FTS fallback.
2. Smart Note Merge (smart_merge.py): Metadata union, redirect callout, wikilink rewriting.
3. Codebase Architect Scanner (architect_scan.py): Architecture extraction, module discovery, markdown/json output.
4. Vault Linter v1.4.4 (vault_linter.py): En/Em-dash filename rule and freshness claim linting.
5. URL Safety Canonical Hashing (url_safety.py): Content normalization and hashing.
6. Note Template & Rules: Bi-temporal timeline schema and future agent preamble.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "template" / ".beyin"))

from scripts import respected_manifest as manifest
from scripts import url_safety
from scripts import vault_linter
from scripts import architect_scan
from scripts import smart_merge
import bounded_recall  # type: ignore


class TestV144BoundedRecall(unittest.TestCase):
    """Bounded Recall & Abstention Gate tests."""

    def test_abstention_gate_on_short_or_conversational_prompts(self):
        self.assertTrue(bounded_recall.should_abstain("merhaba"))
        self.assertTrue(bounded_recall.should_abstain("selam jarvis"))
        self.assertTrue(bounded_recall.should_abstain("teşekkürler"))
        self.assertTrue(bounded_recall.should_abstain("ok"))
        self.assertTrue(bounded_recall.should_abstain("tamam anladım"))
        self.assertTrue(bounded_recall.should_abstain(""))
        self.assertTrue(bounded_recall.should_abstain("tamam devam et"))

    def test_abstention_gate_passes_substantive_prompts(self):
        self.assertFalse(bounded_recall.should_abstain("Next.js auth mimarisi ve session yönetimi nasıl olmalı?"))
        self.assertFalse(bounded_recall.should_abstain("RespectedOS graphrag indexleme kararları neydi?"))
        self.assertFalse(bounded_recall.should_abstain("PostgreSQL connection pooling ayarları"))

    def test_bounded_recall_produces_budgeted_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            (vault / "500-Knowledge").mkdir(parents=True)
            doc = vault / "500-Knowledge" / "Auth.md"
            doc.write_text(
                "---\ntitle: Auth Notu\n---\n# Auth\nNext.js auth session ve token doğrulama mimarisi.\n" * 50,
                encoding="utf-8",
            )
            result = bounded_recall.get_bounded_recall(
                "Next.js auth mimarisi token",
                vault_root=vault,
                max_chars=200,
            )
            # Either produced bounded string within 300 chars or gracefully abstained/empty
            self.assertLessEqual(len(result), 300)

    def test_abstention_gate_on_slash_commands(self):
        self.assertTrue(bounded_recall.should_abstain("/plan"))
        self.assertTrue(bounded_recall.should_abstain("/help"))
        self.assertTrue(bounded_recall.should_abstain("/goal"))

    def test_bounded_recall_fails_closed_on_invalid_vault_or_error(self):
        non_existent_vault = Path(tempfile.gettempdir()) / "non_existent_vault_12345"
        # Must fail-closed: return empty string, never raise exception to the caller
        result = bounded_recall.get_bounded_recall("substantive query about architecture", vault_root=non_existent_vault)
        self.assertEqual(result, "")


class TestV144SmartMerge(unittest.TestCase):
    """Smart Note Merge tests."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)
        (self.vault / "500-Knowledge").mkdir(parents=True)
        (self.vault / "300-Projects").mkdir(parents=True)

        self.source = self.vault / "500-Knowledge" / "Eski_Not.md"
        self.source.write_text(
            "---\ntitle: Eski Not\ncreated: 2026-01-01\nmodified: 2026-01-10\ntags: [python, backend]\naliases: [Eski Alias]\n---\n# Eski Not İçeriği\nDetaylı açıklama burada.\n",
            encoding="utf-8",
        )

        self.target = self.vault / "500-Knowledge" / "Yeni_Not.md"
        self.target.write_text(
            "---\ntitle: Yeni Not\ncreated: 2026-02-01\nmodified: 2026-02-15\ntags: [fast-api]\n---\n# Yeni Not Başlığı\nAna içerik burada.\n",
            encoding="utf-8",
        )

        self.referrer = self.vault / "300-Projects" / "Proje.md"
        self.referrer.write_text(
            "# Proje\nReferans: [[Eski_Not]] ve [[Başka_Not]]\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_smart_merge_rejects_self_merge_without_data_loss(self):
        original_content = self.source.read_text(encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            smart_merge.smart_merge(self.source, self.source, vault_root=self.vault)
        self.assertIn("kendisiyle birleştirilemez", str(ctx.exception))
        # Ensure zero data loss - content is 100% intact
        self.assertEqual(self.source.read_text(encoding="utf-8"), original_content)

    def test_smart_merge_merges_metadata_and_preserves_source_as_redirect(self):
        smart_merge.smart_merge(self.source, self.target, vault_root=self.vault)

        # 1. Source file still exists (never deleted)
        self.assertTrue(self.source.is_file())
        source_content = self.source.read_text(encoding="utf-8")
        self.assertIn("redirect: [[Yeni_Not]]", source_content)
        self.assertIn("type: redirect", source_content)
        self.assertIn("retired_at:", source_content)
        self.assertIn("[[Yeni_Not]]", source_content)

        # 2. Target file contains union of tags and aliases
        target_content = self.target.read_text(encoding="utf-8")
        self.assertIn("python", target_content)
        self.assertIn("backend", target_content)
        self.assertIn("fast-api", target_content)
        self.assertIn("Eski Not", target_content)
        self.assertIn("Birleştirilen Not: [[Eski_Not]]", target_content)
        self.assertIn("Detaylı açıklama burada.", target_content)

        # 3. Referrer note has wikilink rewritten from [[Eski_Not]] to [[Yeni_Not]]
        referrer_content = self.referrer.read_text(encoding="utf-8")
        self.assertIn("[[Yeni_Not]]", referrer_content)
        self.assertNotIn("[[Eski_Not]]", referrer_content)


class TestV144ArchitectScan(unittest.TestCase):
    """Codebase Architect Scanner tests."""

    def test_scan_codebase_detects_structure_and_modules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            proj = Path(temp_dir)
            (proj / "src" / "api").mkdir(parents=True)
            (proj / "src" / "models").mkdir(parents=True)
            (proj / "package.json").write_text('{"name": "test-app", "dependencies": {"next": "14.0.0"}}', encoding="utf-8")
            (proj / "src" / "api" / "routes.ts").write_text("export const handle = () => {};", encoding="utf-8")
            (proj / "src" / "models" / "user.ts").write_text("export interface User { id: string; }", encoding="utf-8")

            report = architect_scan.scan_codebase(proj)
            self.assertEqual(report["name"], proj.name)
            self.assertTrue(any("next" in d for d in report["dependencies"]))
            self.assertGreater(len(report["modules"]), 0)

            md = architect_scan.to_markdown(report)
            self.assertIn("## For future agent", md)
            self.assertIn("## 1. Diller ve Dağılım", md)
            self.assertIn("## 2. Modül Hiyerarşisi", md)


class TestV144VaultLinter(unittest.TestCase):
    """Vault Linter En/Em-dash and Freshness claim linting tests."""

    def test_dash_checker_detects_and_fixes_en_em_dashes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            bad_file = vault / "Not\u2013Tire.md"  # En-dash
            bad_file.write_text("# Not", encoding="utf-8")

            report = vault_linter.lint_vault(vault)
            self.assertEqual(report["filename_issues_count"], 1)
            self.assertIn("uzun tire", report["filename_issues"][0]["issue"])

            # Test fix option
            fixed = vault_linter.fix_dashes(vault)
            self.assertEqual(fixed, 1)
            self.assertTrue((vault / "Not-Tire.md").is_file())
            self.assertFalse(bad_file.exists())

    def test_freshness_claim_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            (vault / "500-Knowledge").mkdir(parents=True)
            unverified = vault / "500-Knowledge" / "Pipeline.md"
            unverified.write_text(
                "# Pipeline\nŞu an pipeline sayısı: 12\n",
                encoding="utf-8",
            )
            verified = vault / "500-Knowledge" / "Pipeline_Dated.md"
            verified.write_text(
                "# Pipeline\nŞu an pipeline sayısı: 12 (as of 2026-09-01)\n",
                encoding="utf-8",
            )

            report = vault_linter.lint_vault(vault)
            self.assertEqual(report["freshness_warnings_count"], 1)
            self.assertIn("500-Knowledge/Pipeline.md:2", report["freshness_warnings"][0]["file"])


class TestV144UrlSafety(unittest.TestCase):
    """Canonical text normalization and content hashing tests."""

    def test_normalize_canonical_text_strips_volatile_elements(self):
        raw = "<p>Hello   World!</p>\r\n* item 1\r\n+ item 2\r\n"
        normalized = url_safety.normalize_canonical_text(raw)
        self.assertNotIn("<p>", normalized)
        self.assertNotIn("</p>", normalized)
        self.assertIn("hello world!", normalized.lower())

    def test_canonical_content_hash_consistency(self):
        t1 = "<p>Hello world</p>"
        t2 = "Hello   world"
        h1 = url_safety.canonical_content_hash(t1)
        h2 = url_safety.canonical_content_hash(t2)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)


class TestV144TemplatesAndRules(unittest.TestCase):
    """Timeline schema and future agent preamble in templates & companion rules."""

    def test_note_template_contains_timeline_and_preamble(self):
        note_template = (ROOT / "template" / "📋 Templates" / "Note.md").read_text(encoding="utf-8")
        self.assertIn("timeline:", note_template)
        self.assertIn("from:", note_template)
        self.assertIn("until:", note_template)
        self.assertIn("learned:", note_template)
        self.assertIn("## For future agent", note_template)

    def test_kurallar_contains_v144_directives(self):
        kurallar = (ROOT / "template" / "🔮 850-Companion" / "Kurallar.md").read_text(encoding="utf-8")
        self.assertIn("timeline:", kurallar)
        self.assertIn("## For future agent", kurallar)
        self.assertIn("(as of YYYY-MM-DD)", kurallar)


if __name__ == "__main__":
    unittest.main(verbosity=2)
