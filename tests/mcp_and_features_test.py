#!/usr/bin/env python3
"""RespectedOS yeni nesil yeteneklerin testleri.

Test edilen bileşenler:
1. SQLite FTS5 yerel arama motoru (SearchEngine)
2. Global MCP Vault Sunucusu (RespectedMcpServer)
3. Çapraz Ajan Geçmiş Madencisi (AgentHistoryMiner)
4. Bi-Temporal ve AI-First Not Şablonu
5. Yeni Düşünme ve Madencilik Becerileri (Skills)
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for p in (ROOT, SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from scripts.arama import SearchEngine
    from scripts.vault_mcp_server import RespectedMcpServer
    from scripts.mine_agent_history import AgentHistoryMiner
except ImportError:
    from arama import SearchEngine  # type: ignore[import-not-found]
    from vault_mcp_server import RespectedMcpServer  # type: ignore[import-not-found]
    from mine_agent_history import AgentHistoryMiner  # type: ignore[import-not-found]


class SearchEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)
        (self.vault / "knowledge").mkdir(parents=True)
        (self.vault / "🏰 300-Projects").mkdir(parents=True)

        # Örnek test notları
        (self.vault / "knowledge" / "Python_Mimarisi.md").write_text(
            "---\ntitle: Python Mimarisi\ntags: [python, backend]\nvalid_at: 2026-09-01\nfreshness: timeless\n---\n"
            "# Python Mimarisi\nRespectedOS mimarisinde Python standart kütüphanesi tercih edilir.",
            encoding="utf-8",
        )
        (self.vault / "🏰 300-Projects" / "Auth_ADR.md").write_text(
            "---\ntitle: Auth Kararı\ntags: [auth, security]\nvalid_at: 2026-09-02\nfreshness: dated\n---\n"
            "# Auth Kararı\nJWT token yerine oturum tabanlı cookie kararı alındı.",
            encoding="utf-8",
        )

        self.engine = SearchEngine(self.vault)

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_indexing_and_search(self) -> None:
        stats = self.engine.index_vault()
        self.assertEqual(stats["indexed"], 2)
        self.assertEqual(stats["deleted"], 0)

        # Arama testi
        results = self.engine.search("Python mimarisi")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["title"], "Python Mimarisi")
        self.assertIn("RespectedOS", results[0]["snippet"])

        # Auth araması
        auth_results = self.engine.search("token cookie")
        self.assertTrue(len(auth_results) >= 1)
        self.assertEqual(auth_results[0]["title"], "Auth Kararı")

    def test_incremental_skip(self) -> None:
        self.engine.index_vault()
        # İkinci indekslemede dosyalar değişmediği için atlanmalı
        stats2 = self.engine.index_vault()
        self.assertEqual(stats2["indexed"], 0)
        self.assertEqual(stats2["skipped"], 2)

    def test_category_filter(self) -> None:
        self.engine.index_vault()
        res = self.engine.search("karar", category="🏰 300-Projects")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "Auth Kararı")


class McpServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)
        (self.vault / "🔮 850-Companion").mkdir(parents=True)
        (self.vault / "🔮 850-Companion" / "Core.md").write_text("# Core\nJarvis düşünme ortağı.", encoding="utf-8")
        (self.vault / "🔮 850-Companion" / "Kurallar.md").write_text("- kural: Direkt ol", encoding="utf-8")
        (self.vault / "🔮 850-Companion" / "Last-Session.md").write_text("Son oturum özeti.", encoding="utf-8")
        (self.vault / "🔮 850-Companion" / "Threads.md").write_text("Açık konular.", encoding="utf-8")

        self.server = RespectedMcpServer(self.vault)
        self.server.search_engine.index_vault()

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_tools_manifest(self) -> None:
        manifest = self.server.get_tools_manifest()
        tool_names = {t["name"] for t in manifest}
        self.assertIn("respected_search", tool_names)
        self.assertIn("respected_get_note", tool_names)
        self.assertIn("respected_get_decisions", tool_names)
        self.assertIn("respected_get_companion_context", tool_names)
        self.assertIn("respected_quick_capture", tool_names)

    def test_companion_context_tool(self) -> None:
        out = self.server.call_tool("respected_get_companion_context", {})
        self.assertIn("Jarvis düşünme ortağı", out)
        self.assertIn("Direkt ol", out)
        self.assertIn("Son oturum özeti", out)

    def test_safe_note_read_and_path_traversal(self) -> None:
        # Geçerli okuma
        out = self.server.call_tool("respected_get_note", {"path": "🔮 850-Companion/Core.md"})
        self.assertIn("Jarvis düşünme ortağı", out)

        # Path traversal atağı engellenmeli
        attack_out = self.server.call_tool("respected_get_note", {"path": "../../etc/passwd"})
        self.assertIn("bulunamadı", attack_out)

    def test_quick_capture_tool(self) -> None:
        out = self.server.call_tool(
            "respected_quick_capture",
            {"title": "Yeni Fikir", "content": "Harika bir test fikri", "tags": ["fikir", "test"]},
        )
        self.assertIn("Başarılı", out)

        dump_dir = self.vault / "📥 000-Inbox" / "Dump"
        dump_files = list(dump_dir.glob("*.md"))
        self.assertEqual(len(dump_files), 1)
        captured_text = dump_files[0].read_text(encoding="utf-8")
        self.assertIn("Harika bir test fikri", captured_text)
        self.assertIn("fikir", captured_text)


class AgentHistoryMinerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)
        (self.vault / "daily").mkdir(parents=True)
        self.miner = AgentHistoryMiner(self.vault)

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_parse_and_import(self) -> None:
        # Sahte JSONL oturumu
        session_file = Path(self.temp_dir.name) / "test_session.jsonl"
        records = [
            {"type": "USER_INPUT", "content": "<USER_REQUEST>Python FTS5 nasıl kurulur?</USER_REQUEST>"},
            {"type": "PLANNER_RESPONSE", "content": "SQLite FTS5 dahili olarak mevcuttur ve hafiftir."},
        ]
        with session_file.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        session_info = {
            "agent": "antigravity",
            "id": "antigravity_test123",
            "path": session_file,
            "mtime": dt.datetime.now(),
        }

        parsed = self.miner.parse_session(session_info)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["agent"], "antigravity")
        self.assertIn("Python FTS5 nasıl kurulur?", parsed["title"])

        written_file = self.miner.import_session(parsed, target_folder="daily")
        self.assertIsNotNone(written_file)
        self.assertTrue(written_file.is_file())
        content = written_file.read_text(encoding="utf-8")
        self.assertIn("antigravity_test123", content)
        self.assertIn("valid_at:", content)
        self.assertIn("freshness: dated", content)

        # Tekrar import edilmemeli (deduplication)
        self.assertIn("antigravity_test123", self.miner.imported_ids)


class TemplateAndSkillsTest(unittest.TestCase):
    def test_note_template_has_bitemporal_and_aifirst(self) -> None:
        note_template = ROOT / "template" / "📋 Templates" / "Note.md"
        self.assertTrue(note_template.is_file())
        content = note_template.read_text(encoding="utf-8")
        self.assertIn("valid_at:", content)
        self.assertIn("recorded_at:", content)
        self.assertIn("freshness:", content)
        self.assertIn("Gelecek Ajan İçin", content)

    def test_new_skills_exist_and_valid(self) -> None:
        skills_to_check = ["beyin-meydan-oku", "beyin-oruntu", "ajan-gecmis-tara"]
        for s in skills_to_check:
            for parent in [".beyin", ".agents", ".claude"]:
                skill_file = ROOT / "template" / parent / "skills" / s / "SKILL.md"
                self.assertTrue(skill_file.is_file(), f"Skill file missing: {skill_file}")
                text = skill_file.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---"))
                self.assertIn(f"name: {s}", text)
                self.assertIn("description:", text)

    def test_skills_map_within_lifecycle_cap(self) -> None:
        skills_map = ROOT / "template" / "🎯 100-Command-Center" / "Skills-Map.md"
        self.assertTrue(skills_map.is_file())
        text = skills_map.read_text(encoding="utf-8")
        self.assertLessEqual(
            len(text),
            1500,
            f"Skills-Map.md ({len(text)} chars) exceeds the 1,500-char lifecycle hook cap, which triggers truncation notes.",
        )


if __name__ == "__main__":
    unittest.main()
