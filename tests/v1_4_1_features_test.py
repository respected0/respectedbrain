#!/usr/bin/env python3
"""Respected Brain 1.4.1 Yeni Özellikler Birim Testleri.

url_safety, defuddle, vault_linter, tiling_check, yeni skill'ler ve
Obsidian Bases şablonlarının sözleşmelerini doğrular.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.url_safety import validate_safe_url
from scripts.defuddle import clean_html
from scripts.vault_linter import lint_vault
from scripts.tiling_check import check_tiling, jaccard_similarity, tokenize
import scripts.respected_manifest as manifest


class TestUrlSafety(unittest.TestCase):
    """URL Güvenlik ve SSRF Kalkanı Testleri."""

    def test_safe_public_urls(self):
        safe, _ = validate_safe_url("https://github.com/AgriciDaniel/claude-obsidian")
        self.assertTrue(safe)

        safe, _ = validate_safe_url("http://example.com/test?page=1")
        self.assertTrue(safe)

    def test_blocks_localhost_and_loopback(self):
        safe, reason = validate_safe_url("http://localhost:8080/admin")
        self.assertFalse(safe)
        self.assertIn("engellendi", reason.lower())

        safe, reason = validate_safe_url("http://127.0.0.1/api")
        self.assertFalse(safe)
        self.assertIn("engellendi", reason.lower())

    def test_blocks_private_subnets(self):
        safe, _ = validate_safe_url("http://192.168.1.1/router")
        self.assertFalse(safe)

        safe, _ = validate_safe_url("http://10.0.0.5/secrets")
        self.assertFalse(safe)

        safe, _ = validate_safe_url("http://172.16.0.1/db")
        self.assertFalse(safe)

    def test_blocks_unsafe_ports_and_schemes(self):
        safe, reason = validate_safe_url("ftp://example.com/file.zip")
        self.assertFalse(safe)
        self.assertIn("protokol", reason.lower())

        safe, reason = validate_safe_url("https://example.com:22/ssh")
        self.assertFalse(safe)
        self.assertIn("port", reason.lower())


class TestDefuddle(unittest.TestCase):
    """Defuddle HTML Temizleyici Testleri."""

    def test_cleans_scripts_and_styles(self):
        html = """
        <html>
          <head>
            <style>body { color: red; }</style>
            <script>alert("hack");</script>
          </head>
          <body>
            <nav><a href="/menu">Menü</a></nav>
            <h1>Başlık 1</h1>
            <p>Bu önemli bir <b>paragraf</b>.</p>
            <script>console.log("ignore");</script>
            <footer>Telif Hakkı 2026</footer>
          </body>
        </html>
        """
        md = clean_html(html)
        self.assertNotIn("alert", md)
        self.assertNotIn("color: red", md)
        self.assertNotIn("Telif Hakkı", md)
        self.assertIn("# Başlık 1", md)
        self.assertIn("Bu önemli bir paragraf.", md)

    def test_converts_lists_and_code(self):
        html = """
        <div>
          <h2>Özellikler</h2>
          <ul>
            <li>Madde 1</li>
            <li>Madde 2</li>
          </ul>
          <pre><code>def test(): return True</code></pre>
          <p>Daha fazla bilgi için <a href="https://example.com">Tıklayın</a>.</p>
        </div>
        """
        md = clean_html(html)
        self.assertIn("## Özellikler", md)
        self.assertIn("- Madde 1", md)
        self.assertIn("```", md)
        self.assertIn("def test(): return True", md)
        self.assertIn("[Tıklayın](https://example.com)", md)


class TestVaultLinterAndTiling(unittest.TestCase):
    """Vault Linter ve Tiling Benzerlik Testleri."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="respected_lint_test_")
        self.vault = Path(self.temp_dir)
        (self.vault / "knowledge").mkdir(parents=True)
        (self.vault / ".beyin").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detects_dead_links_and_orphans(self):
        # Dosya A, Dosya B'ye ve OlmayanC'ye link veriyor
        file_a = self.vault / "knowledge" / "NotA.md"
        file_a.write_text("# Not A\n\nBakınız: [[NotB]] ve [[OlmayanNotC]]", encoding="utf-8")

        file_b = self.vault / "knowledge" / "NotB.md"
        file_b.write_text("# Not B\n\nİçerik burada.", encoding="utf-8")

        # Dosya D yetim (hiçbir linki yok, hiçbir yerden link almıyor)
        file_d = self.vault / "knowledge" / "YetimNot.md"
        file_d.write_text("# Yetim Not\n\nTek başına.", encoding="utf-8")

        results = lint_vault(self.vault)
        self.assertEqual(results["total_markdown_files"], 3)
        self.assertEqual(results["dead_links_count"], 1)
        self.assertEqual(results["dead_links"][0]["target"], "OlmayanNotC")
        self.assertIn("knowledge/YetimNot.md", results["orphan_pages"])

    def test_tiling_detects_similar_notes(self):
        content_1 = """
        # Docker Optimizasyonu
        Docker konteyner optimizasyonu için multi-stage build kullanımı çok önemlidir.
        Alpine veya slim imajlar tercih edilmeli, katman sayısı minimumda tutulmalıdır.
        Cache mekanizması düzgün yapılandırılmalı ve güvenli kullanıcı tanımlanmalıdır.
        """
        content_2 = """
        # Docker Container Optimizasyonu
        Docker konteyner optimizasyonu için multi-stage build kullanımı oldukça önemlidir.
        Alpine ve slim base imajlar seçilmeli, katman sayısı minimumda tutulmalıdır.
        Cache yönetimi doğru yapılandırılmalı ve root olmayan güvenli kullanıcı tanımlanmalıdır.
        """
        file_1 = self.vault / "knowledge" / "DockerOpt1.md"
        file_1.write_text(content_1, encoding="utf-8")

        file_2 = self.vault / "knowledge" / "DockerOpt2.md"
        file_2.write_text(content_2, encoding="utf-8")

        results = check_tiling(self.vault, threshold=0.50)
        self.assertGreaterEqual(results["duplicate_pairs_count"], 1)
        pair = results["pairs"][0]
        self.assertIn("docker", pair["common_terms"])
        self.assertGreaterEqual(pair["similarity_pct"], 50.0)


class TestManifestAndTemplates(unittest.TestCase):
    """1.4.1 Sürüm Manifesti, Şablonlar ve Kurallar."""

    def test_manifest_version_is_1_4_1(self):
        self.assertEqual(manifest.MULTI_VERSION, "1.4.1")
        self.assertIn("1.4.1", manifest.UPDATABLE_MULTI_VERSIONS)
        self.assertIn("scripts/url_safety.py", manifest.RUNTIME)
        self.assertIn("scripts/defuddle.py", manifest.RUNTIME)
        self.assertIn("scripts/vault_linter.py", manifest.RUNTIME)
        self.assertIn("scripts/tiling_check.py", manifest.RUNTIME)

    def test_new_skills_and_templates_exist(self):
        # Otonom araştırma skill'i
        self.assertTrue((ROOT / "template" / ".beyin" / "skills" / "otonom-arastirma" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "skills" / "otonom-arastirma" / "SKILL.md").is_file())

        # Yazılım kalite skill'i ve iki parçalı kural seti (Madde 1-13 ve Madde 14-25 + Gate)
        self.assertTrue((ROOT / "template" / ".beyin" / "skills" / "yazilim-kalite" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "skills" / "yazilim-kalite" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "rules" / "software-quality-1.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "rules" / "software-quality-2.md").is_file())

        # Obsidian Base şablonu
        self.assertTrue((ROOT / "template" / "📋 Templates" / "Base.base").is_file())

        # Sürüm dosyası
        self.assertEqual((ROOT / "template" / ".beyin-multi-version").read_text().strip(), "1.4.1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
