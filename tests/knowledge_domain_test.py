#!/usr/bin/env python3
"""Tests for knowledge domain tagging and multi-domain concept isolation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
from types import ModuleType
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPILE_PATH = REPO_ROOT / "template" / ".beyin" / "engine" / "compile.py"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class KnowledgeDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = load_module("compile_domain_test", COMPILE_PATH)
        self.temporary = tempfile.TemporaryDirectory()
        self.vault = Path(self.temporary.name)
        self.knowledge = self.vault / "knowledge"
        self.concepts = self.knowledge / "concepts"
        self.connections = self.knowledge / "connections"
        self.daily = self.vault / "daily"

        self.concepts.mkdir(parents=True)
        self.connections.mkdir(parents=True)
        self.daily.mkdir(parents=True)

        (self.knowledge / "index.md").write_text(
            "# Bilgi Tabanı İndeksi\n\n| Makale | Alan (Domain) | Özet | Kaynak | Güncellendi |\n| --- | --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
        (self.knowledge / "log.md").write_text("# Derleme Günlüğü\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_compile_prompt_specifies_domain_tagging_and_index_structure(self) -> None:
        prompt = self.compiler.COMPILE_PROMPT
        self.assertIn("Alan (Domain) Ayrımı ve Context-Tagging:", prompt)
        self.assertIn("* core: İkinci beyin çekirdek hafıza", prompt)
        self.assertIn("* finance: Kişisel finans (bütçe, muhasebe", prompt)
        self.assertIn("title, domain, aliases, tags", prompt)
        self.assertIn("* project/<slug>:", prompt)
        self.assertIn("* general:", prompt)
        self.assertIn("Makale | Alan (Domain) | Özet | Kaynak |", prompt)

    def test_template_index_markdown_has_domain_column(self) -> None:
        template_index = REPO_ROOT / "template" / "knowledge" / "index.md"
        text = template_index.read_text(encoding="utf-8")
        self.assertIn("| Makale | Alan (Domain) | Özet | Kaynak | Güncellendi |", text)

    def test_allowed_output_file_permits_nested_domain_concepts(self) -> None:
        is_allowed = self.compiler._is_allowed_output_file
        self.assertTrue(is_allowed("knowledge/index.md"))
        self.assertTrue(is_allowed("knowledge/log.md"))
        self.assertTrue(is_allowed("knowledge/concepts/general-slug.md"))
        self.assertTrue(is_allowed("knowledge/concepts/finance/butce-ve-muhasebe.md"))
        self.assertTrue(is_allowed("knowledge/concepts/core/hafiza-ve-hooklar.md"))
        self.assertTrue(is_allowed("knowledge/concepts/project/ecommerce/sepet.md"))
        self.assertTrue(is_allowed("knowledge/connections/a--b.md"))

        self.assertFalse(is_allowed("daily/2026-09-11.md"))
        self.assertFalse(is_allowed("SETUP.md"))
        self.assertFalse(is_allowed(".beyin/engine/compile.py"))
        self.assertFalse(is_allowed("knowledge/concepts/test.txt"))
        self.assertFalse(is_allowed("knowledge/unauthorized.md"))

    def test_allowed_output_directory_permits_domain_subdirectories(self) -> None:
        is_allowed_dir = self.compiler._is_allowed_output_directory
        self.assertTrue(is_allowed_dir("knowledge/concepts"))
        self.assertTrue(is_allowed_dir("knowledge/concepts/finance"))
        self.assertTrue(is_allowed_dir("knowledge/concepts/core"))
        self.assertTrue(is_allowed_dir("knowledge/connections"))

        self.assertFalse(is_allowed_dir("knowledge"))
        self.assertFalse(is_allowed_dir("daily"))
        self.assertFalse(is_allowed_dir(".beyin"))

    def test_atomic_promotion_creates_domain_subdirectories_in_live_vault(self) -> None:
        stage_dir = Path(tempfile.mkdtemp(prefix="stage-test-"))
        try:
            finance_concept_content = (
                "---\n"
                "title: Çift Taraflı Muhasebe\n"
                "domain: finance\n"
                "sources: [2026-09-11.md]\n"
                "---\n"
                "# Çift Taraflı Muhasebe\n"
                "Varlık ve borç eşitliği.\n"
            )
            core_concept_content = (
                "---\n"
                "title: Event Rotasyon Mimarisi\n"
                "domain: core\n"
                "sources: [2026-09-11.md]\n"
                "---\n"
                "# Event Rotasyon Mimarisi\n"
                "20 event rotasyon kuralı.\n"
            )

            stage_knowledge = stage_dir / "knowledge"
            stage_finance = stage_knowledge / "concepts" / "finance"
            stage_core = stage_knowledge / "concepts" / "core"
            stage_finance.mkdir(parents=True)
            stage_core.mkdir(parents=True)

            (stage_finance / "cift-tarafli-muhasebe.md").write_text(
                finance_concept_content, encoding="utf-8"
            )
            (stage_core / "event-rotasyon-mimarisi.md").write_text(
                core_concept_content, encoding="utf-8"
            )

            changed_files = [
                "knowledge/concepts/finance/cift-tarafli-muhasebe.md",
                "knowledge/concepts/core/event-rotasyon-mimarisi.md",
            ]
            live_baseline: dict[str, str | None] = {
                "knowledge/concepts/finance/cift-tarafli-muhasebe.md": None,
                "knowledge/concepts/core/event-rotasyon-mimarisi.md": None,
            }

            # Promotes from stage into self.vault
            self.compiler._promote_changes(
                stage_dir, self.vault, changed_files, live_baseline
            )

            live_finance = (
                self.vault / "knowledge/concepts/finance/cift-tarafli-muhasebe.md"
            )
            live_core = (
                self.vault / "knowledge/concepts/core/event-rotasyon-mimarisi.md"
            )

            self.assertTrue(live_finance.is_file())
            self.assertEqual(
                live_finance.read_text(encoding="utf-8"), finance_concept_content
            )

            self.assertTrue(live_core.is_file())
            self.assertEqual(
                live_core.read_text(encoding="utf-8"), core_concept_content
            )
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
