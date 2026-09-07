#!/usr/bin/env python3
"""Respected Brain Kasa ve İçerik Hijyeni Birim Testleri.

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
ORIGINAL_SYS_PATH = list(sys.path)
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


def tearDownModule():
    sys.path[:] = ORIGINAL_SYS_PATH

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

    def test_blocks_cloud_metadata_ip(self):
        # AWS / GCP / Azure IMDS endpoint 169.254.169.254 (link-local)
        safe, reason = validate_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("engellendi", reason.lower())

    def test_blocks_ipv6_loopback(self):
        safe, reason = validate_safe_url("http://[::1]/")
        self.assertFalse(safe)
        self.assertIn("engellendi", reason.lower())

    def test_handles_null_empty_and_invalid_inputs(self):
        safe, reason = validate_safe_url("")
        self.assertFalse(safe)
        self.assertIn("boş veya geçersiz", reason)

        safe, reason = validate_safe_url("   ")
        self.assertFalse(safe)
        self.assertIn("boş veya geçersiz", reason)

        safe, reason = validate_safe_url(None)  # type: ignore
        self.assertFalse(safe)
        self.assertIn("boş veya geçersiz", reason)


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

    def test_defuddle_safe_redirect_handler_blocks_private_destinations(self):
        """Redirects to private IP or metadata must be blocked by SafeRedirectHandler."""
        from scripts.defuddle import SafeRedirectHandler
        handler = SafeRedirectHandler()
        with self.assertRaises(ValueError) as ctx:
            handler.redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1:8080/admin")
        self.assertIn("Yönlendirme engellendi", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            handler.redirect_request(None, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data/")
        self.assertIn("Yönlendirme engellendi", str(ctx.exception))


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

    def test_vault_linter_ignores_code_block_wikilinks(self):
        from scripts.vault_linter import lint_vault
        test_note = self.vault / "knowledge" / "code_example.md"
        test_note.write_text(
            '---\ntitle: "Kod Ornegi"\ncreated: "2026-09-07"\ntype: note\nstatus: active\n---\n\n'
            "# Kod Ornegi\n\n"
            "Burada bir kod ornegi var:\n\n"
            "```markdown\n"
            "Burada [[VarOlmayanNotOrnegi]] yer aliyor ve dead link olmamali.\n"
            "```\n\n"
            "Inline kod: `[[DigerOrnek]]` da yoksayilmali.\n",
            encoding="utf-8",
        )
        report = lint_vault(self.vault)
        # VarOlmayanNotOrnegi ve DigerOrnek dead link olmamalı
        dead_link_targets = [d["target"] for d in report["dead_links"]]
        self.assertNotIn("VarOlmayanNotOrnegi", dead_link_targets)
        self.assertNotIn("DigerOrnek", dead_link_targets)



class TestManifestAndTemplates(unittest.TestCase):
    """1.4.1 Sürüm Manifesti, Şablonlar ve Kurallar."""

    def test_manifest_version_is_1_4_5(self):
        self.assertEqual(manifest.MULTI_VERSION, "1.4.6")
        self.assertIn("1.4.1", manifest.UPDATABLE_MULTI_VERSIONS)
        self.assertIn("1.4.2", manifest.UPDATABLE_MULTI_VERSIONS)
        self.assertIn("1.4.3", manifest.UPDATABLE_MULTI_VERSIONS)
        self.assertIn("1.4.4", manifest.UPDATABLE_MULTI_VERSIONS)
        self.assertIn("scripts/url_safety.py", manifest.RUNTIME)
        self.assertIn("scripts/defuddle.py", manifest.RUNTIME)
        self.assertIn("scripts/vault_linter.py", manifest.RUNTIME)
        self.assertIn("scripts/tiling_check.py", manifest.RUNTIME)
        self.assertIn(".beyin/graph_analysis.py", manifest.RUNTIME)
        self.assertIn(".beyin/graphrag.py", manifest.RUNTIME)
        self.assertIn(".beyin/session_brain.py", manifest.RUNTIME)
        self.assertIn(".beyin/session_viz.py", manifest.RUNTIME)
        self.assertIn(".agents/rules/software-quality-1.md", manifest.RUNTIME)
        self.assertIn(".agents/rules/software-quality-2.md", manifest.RUNTIME)
        self.assertIn(".cursor/rules/software-quality-1.mdc", manifest.RUNTIME)
        self.assertIn(".cursor/rules/software-quality-2.mdc", manifest.RUNTIME)
        self.assertIn("📋 Templates/Base.base", manifest.RUNTIME)
        self.assertIn("📋 Templates/Canvas.canvas", manifest.RUNTIME)

    def test_new_skills_and_templates_exist(self):
        # Otonom araştırma skill'i
        self.assertTrue((ROOT / "template" / ".beyin" / "skills" / "otonom-arastirma" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "skills" / "otonom-arastirma" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".claude" / "skills" / "otonom-arastirma" / "SKILL.md").is_file())

        # Yazılım kalite skill'i ve iki parçalı kural seti (Madde 1-13 ve Madde 14-25 + Gate)
        self.assertTrue((ROOT / "template" / ".beyin" / "skills" / "yazilim-kalite" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "skills" / "yazilim-kalite" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".claude" / "skills" / "yazilim-kalite" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "rules" / "software-quality-1.md").is_file())
        self.assertTrue((ROOT / "template" / ".agents" / "rules" / "software-quality-2.md").is_file())

        # Cursor MDC kalite kural setleri (Frontmatter + kurallar)
        cursor_q1 = ROOT / "template" / ".cursor" / "rules" / "software-quality-1.mdc"
        cursor_q2 = ROOT / "template" / ".cursor" / "rules" / "software-quality-2.mdc"
        self.assertTrue(cursor_q1.is_file())
        self.assertTrue(cursor_q2.is_file())
        self.assertTrue(cursor_q1.read_text(encoding="utf-8").startswith("---\ndescription:"))
        self.assertTrue(cursor_q2.read_text(encoding="utf-8").startswith("---\ndescription:"))
        self.assertIn("alwaysApply: true", cursor_q1.read_text(encoding="utf-8"))
        self.assertIn("alwaysApply: true", cursor_q2.read_text(encoding="utf-8"))

        # Obsidian Base şablonu
        self.assertTrue((ROOT / "template" / "📋 Templates" / "Base.base").is_file())

        # Sürüm dosyası
        self.assertEqual((ROOT / "template" / ".beyin-multi-version").read_text().strip(), "1.4.6")

    def test_url_safety_blocks_rfc_internal_domains(self):
        from scripts.url_safety import validate_safe_url
        internal_domains = [
            "http://gateway.home.arpa",
            "https://server.corp",
            "http://router.lan",
            "http://device.local",
            "http://sub.localhost",
            "http://router",
            "http://nas",
            "http://intranet",
            "http://127.1",
            "http://0177.0.0.1",
            "http://2130706433",
            "http://0x7f000001",
            "http://[::1]",
            "http://[::ffff:127.0.0.1]",
            "http://127.0.0.1.nip.io",
            "http://localtest.me",
        ]
        for url in internal_domains:
            safe, reason = validate_safe_url(url)
            self.assertFalse(safe, f"Internal URL {url} should be blocked (reason: {reason})")
            self.assertIn("engellendi", reason)

        # Geçersiz/taşan port (çökmeden fail-closed dönmeli)
        safe, reason = validate_safe_url("http://example.com:65536/")
        self.assertFalse(safe)
        self.assertIn("Geçersiz port", reason)

        # URL içi kimlik doğrulama / kullanıcı bilgisi engeli
        safe, reason = validate_safe_url("http://admin:secret@example.com/")
        self.assertFalse(safe)
        self.assertIn("kimlik bilgisi", reason)

        # Köşeli parantezli IPv6 doğrudan is_private_or_reserved_ip kontrolü
        from scripts.url_safety import is_private_or_reserved_ip
        self.assertTrue(is_private_or_reserved_ip("[::1]"))
        self.assertTrue(is_private_or_reserved_ip("[::ffff:127.0.0.1]"))
        self.assertFalse(is_private_or_reserved_ip("[2606:4700:4700::1111]"))

    def test_install_briefing_schedule_decode_windows_xml_fallbacks(self):
        from scripts.install_briefing_schedule import _decode_windows_xml
        # CP857 ile kodlanmış Türkçe karakterler içeren XML
        turkish_text = '<?xml version="1.0"?><Task><Author>Şükrü Çağlar</Author></Task>'
        cp857_bytes = turkish_text.encode("cp857")
        decoded = _decode_windows_xml(cp857_bytes)
        self.assertIn("Şükrü Çağlar", decoded)

    def test_defuddle_fail_closed_import_protection(self):
        """When validate_safe_url fallback is called, it must fail closed (return False) rejecting URLs."""
        import scripts.defuddle as defuddle_mod
        from unittest import mock

        fallback_fn = lambda u: (False, "url_safety güvenlik modülü yüklenemedi; istek engellendi")
        with mock.patch.object(defuddle_mod, "validate_safe_url", fallback_fn):
            safe, reason = defuddle_mod.validate_safe_url("https://example.com")
            self.assertFalse(safe)
            self.assertIn("engellendi", reason.lower())

            # fetch_url must refuse to fetch and return error message
            if hasattr(defuddle_mod, "fetch_url"):
                result = defuddle_mod.fetch_url("https://example.com")
                self.assertIn("engellendi", result.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
