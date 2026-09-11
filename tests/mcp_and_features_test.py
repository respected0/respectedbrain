#!/usr/bin/env python3
"""Respected Brain yeni nesil yeteneklerin testleri.

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
ORIGINAL_SYS_PATH = list(sys.path)
for p in (ROOT, SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def tearDownModule():
    sys.path[:] = ORIGINAL_SYS_PATH

try:
    from scripts.arama import SearchEngine, read_head, parse_frontmatter_head
    from scripts.vault_mcp_server import RespectedMcpServer
    from scripts.mine_agent_history import AgentHistoryMiner
except ImportError:
    from arama import SearchEngine, read_head, parse_frontmatter_head  # type: ignore[import-not-found]
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
            "# Python Mimarisi\nİkinci beyin mimarisinde Python standart kütüphanesi tercih edilir.",
            encoding="utf-8",
        )
        (self.vault / "🏰 300-Projects" / "Auth_ADR.md").write_text(
            "---\ntitle: Auth Kararı\ntags: [auth, security]\nvalid_at: 2026-09-02\nfreshness: dated\n---\n"
            "# Auth Kararı\nJWT token yerine oturum tabanlı cookie kararı alındı.",
            encoding="utf-8",
        )

        self.engine = SearchEngine(self.vault)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_indexing_and_search(self) -> None:
        stats = self.engine.index_vault()
        self.assertEqual(stats["indexed"], 2)
        self.assertEqual(stats["deleted"], 0)

        # Arama testi
        results = self.engine.search("Python mimarisi")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["title"], "Python Mimarisi")
        self.assertIn("standart kütüphanesi", results[0]["snippet"])

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

    def test_search_handles_malformed_fts_queries(self):
        """Unclosed quotes or raw FTS5 operators must not crash search engine."""
        self.engine.index_vault()
        # Should gracefully return results or empty list without raising sqlite3.OperationalError
        res1 = self.engine.search('"unclosed quote')
        self.assertIsInstance(res1, list)
        res2 = self.engine.search('AND OR NOT *')
        self.assertIsInstance(res2, list)

    def test_search_non_existent_category_returns_empty(self):
        self.engine.index_vault()
        res = self.engine.search("Python", category="NonExistentCategory")
        self.assertEqual(res, [])


class McpServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)
        (self.vault / "🔮 850-Companion").mkdir(parents=True)
        (self.vault / "🔮 850-Companion" / "Core.md").write_text("# Core\nCompanion düşünme ortağı.", encoding="utf-8")
        (self.vault / "🔮 850-Companion" / "Kurallar.md").write_text("- kural: Direkt ol", encoding="utf-8")
        (self.vault / "🔮 850-Companion" / "Last-Session.md").write_text("Son oturum özeti.", encoding="utf-8")
        (self.vault / "🔮 850-Companion" / "Threads.md").write_text("Açık konular.", encoding="utf-8")

        self.server = RespectedMcpServer(self.vault)
        self.server.search_engine.index_vault()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_tools_manifest(self) -> None:
        manifest = self.server.get_tools_manifest()
        tool_names = {t["name"] for t in manifest}
        self.assertIn("respected_search", tool_names)
        self.assertIn("respected_get_note", tool_names)
        self.assertIn("respected_get_decisions", tool_names)
        self.assertIn("respected_get_companion_context", tool_names)
        self.assertIn("respected_quick_capture", tool_names)
        self.assertIn("respected_remember", tool_names)
        self.assertIn("respected_expand", tool_names)

    def test_unknown_tool_returns_error_message(self) -> None:
        out = self.server.call_tool("unknown_tool_xyz", {})
        self.assertIn("Bilinmeyen araç", out)

    def test_companion_context_tool(self) -> None:
        out = self.server.call_tool("respected_get_companion_context", {})
        self.assertIn("Companion düşünme ortağı", out)
        self.assertIn("Direkt ol", out)
        self.assertIn("Son oturum özeti", out)

    def test_safe_note_read_and_path_traversal(self) -> None:
        # Geçerli okuma
        out = self.server.call_tool("respected_get_note", {"path": "🔮 850-Companion/Core.md"})
        self.assertIn("Companion düşünme ortağı", out)

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

    def test_remember_tool_epistemic(self) -> None:
        out = self.server.call_tool(
            "respected_remember",
            {
                "title": "React Render Gotcha",
                "content": "useEffect içinde setState yaparken dependency array'e dikkat et.",
                "scope": "platform",
                "confidence": "verified",
                "supersedes": ["Eski React Kuralı"],
                "tags": ["react", "frontend"],
            },
        )
        self.assertIn("Başarılı", out)
        self.assertIn("platform", out)
        self.assertIn("verified", out)

        knowledge_dir = self.vault / "🧠 500-Knowledge"
        k_files = list(knowledge_dir.glob("*_React_Render_Gotcha.md"))
        self.assertEqual(len(k_files), 1)
        content = k_files[0].read_text(encoding="utf-8")
        self.assertIn("scope: platform", content)
        self.assertIn("confidence: verified", content)
        self.assertIn('supersedes: ["Eski React Kuralı"]', content)

    def test_remember_tool_blocks_path_traversal(self) -> None:
        """respected_remember must not allow writing outside the vault via project path traversal."""
        out = self.server.call_tool(
            "respected_remember",
            {
                "title": "Malicious Traversal",
                "content": "Malicious content",
                "scope": "project",
                "project": "../../malicious_dir",
            },
        )
        # Slashes and dots are sanitized into safe chars, staying strictly inside 🏰 300-Projects
        self.assertIn("Başarılı", out)
        # Must strictly be inside vault
        malicious_outside = self.vault.parent / "malicious_dir"
        self.assertFalse(malicious_outside.exists())
        # Cleaned project folder must be inside 300-Projects
        project_dir = self.vault / "🏰 300-Projects"
        self.assertTrue(any("malicious_dir" in p.name for p in project_dir.iterdir()))

    def test_expand_tool(self) -> None:
        # Test için birbirine bağlı iki not oluşturalım
        knowledge_dir = self.vault / "🧠 500-Knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        (knowledge_dir / "NodeA.md").write_text("# Node A\nBu not [[NodeB]] bağlantısı içerir.", encoding="utf-8")
        (knowledge_dir / "NodeB.md").write_text("# Node B\nBu not da [[NodeA]] bağlantısı taşır.", encoding="utf-8")

        out = self.server.call_tool("respected_expand", {"title_or_path": "NodeA"})
        self.assertIn("Dış Bağlantılar", out)
        self.assertIn("[[NodeB]]", out)
        self.assertIn("Geri Bağlantılar", out)
        self.assertIn("NodeB.md", out)


class AgentHistoryMinerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)
        (self.vault / "daily").mkdir(parents=True)
        self.miner = AgentHistoryMiner(self.vault)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

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
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed["agent"], "antigravity")
        self.assertIn("Python FTS5 nasıl kurulur?", parsed["title"])
        self.assertTrue(any("SQLite FTS5" in s for s in parsed.get("summaries", [])))

        written_file = self.miner.import_session(parsed, target_folder="daily")
        self.assertIsInstance(written_file, Path)
        self.assertTrue(written_file.is_file())
        content = written_file.read_text(encoding="utf-8")
        self.assertIn("antigravity_test123", content)
        self.assertIn("valid_at:", content)
        self.assertIn("freshness: dated", content)

        # Tekrar import edilmemeli (deduplication)
        self.assertIn("antigravity_test123", self.miner.imported_ids)

    def test_parse_session_empty_and_corrupt_records(self) -> None:
        """Empty session file or corrupt JSON lines must not raise unhandled exceptions."""
        session_file = Path(self.temp_dir.name) / "corrupt_session.jsonl"
        session_file.write_text("{not valid json\n", encoding="utf-8")

        session_info = {
            "agent": "codex",
            "id": "corrupt_123",
            "path": session_file,
            "mtime": dt.datetime.now(),
        }
        parsed = self.miner.parse_session(session_info)
        # Should gracefully return None or safe dict without crashing
        self.assertTrue(parsed is None or isinstance(parsed, dict))


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

    def test_note_template_has_epistemic_fields(self) -> None:
        note_template = ROOT / "template" / "📋 Templates" / "Note.md"
        self.assertTrue(note_template.is_file())
        content = note_template.read_text(encoding="utf-8")
        self.assertIn("scope:", content)
        self.assertIn("confidence:", content)
        self.assertIn("supersedes:", content)

    def test_read_head_and_frontmatter_head(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "big_note.md"
            header = "---\ntitle: Büyük Not\nscope: platform\ntags: [a, b]\n---\n"
            # 50.000 karakterlik gövde
            body = "# Başlık\n" + ("Uzun satır metni.\n" * 2000)
            test_file.write_text(header + body, encoding="utf-8")

            # Yalnızca ilk 1200 karakter okunmalı
            head = read_head(test_file, max_chars=1200)
            self.assertLessEqual(len(head), 1200)
            self.assertIn("title: Büyük Not", head)

            fm, valid = parse_frontmatter_head(test_file, max_chars=1200)
            self.assertTrue(valid)
            self.assertEqual(fm["title"], "Büyük Not")
            self.assertEqual(fm["scope"], "platform")
            self.assertEqual(fm["tags"], ["a", "b"])

    def test_scan_open_loops(self) -> None:
        p1 = str(ROOT / "template" / ".beyin")
        sys.path.insert(0, p1)
        self.addCleanup(lambda: sys.path.remove(p1) if p1 in sys.path else None)
        from morning_briefing import _scan_open_loops  # type: ignore

        with tempfile.TemporaryDirectory() as td:
            v_root = Path(td)
            # 1. 300-Projects altında açık todo
            p_dir = v_root / "🏰 300-Projects" / "ProjectAlpha"
            p_dir.mkdir(parents=True)
            (p_dir / "Tasks.md").write_text("# Tasks\n- [ ] Database migration yap\n- [x] Schema tasarla\n", encoding="utf-8")

            # 2. Daily log altında açık todo
            d_dir = v_root / "daily"
            d_dir.mkdir(parents=True)
            (d_dir / "2026-09-06.md").write_text("# Günlük\n- [ ] Sarah ile 1:1 yap\n", encoding="utf-8")

            # 3. Inbox dump
            i_dir = v_root / "📥 000-Inbox" / "Dump"
            i_dir.mkdir(parents=True)
            (i_dir / "meeting.md").write_text("# Meeting\n", encoding="utf-8")

            loops_text = _scan_open_loops(v_root)
            self.assertIn("Database migration yap", loops_text)
            self.assertIn("Sarah ile 1:1 yap", loops_text)
            self.assertIn("İşlenmeyi bekleyen", loops_text)

    def test_precompact_transcript_backup(self) -> None:
        p2 = str(ROOT / "template" / ".beyin" / "hooks")
        sys.path.insert(0, p2)
        self.addCleanup(lambda: sys.path.remove(p2) if p2 in sys.path else None)
        import lifecycle  # type: ignore

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            v_root = Path(td)
            (v_root / "🔮 850-Companion").mkdir(parents=True)
            (v_root / "🔮 850-Companion" / "Last-Session.md").write_text("## Session: test\n", encoding="utf-8")
            s_dir = v_root / ".claude" / "scripts" / ".state"
            s_dir.mkdir(parents=True)

            # Geçici sahte transkript dosyası
            fake_transcript = Path(td) / "fake_transcript.jsonl"
            fake_transcript.write_text('{"type": "message", "content": "hello"}\n', encoding="utf-8")

            payload = {
                "session_id": "session-xyz123",
                "transcript_path": str(fake_transcript),
            }
            lifecycle._finish_session(v_root, s_dir, payload, "precompact", dt.datetime.now(), "antigravity")

            logs_dir = v_root / "🔮 850-Companion" / "Session-Logs"
            self.assertTrue(logs_dir.is_dir())
            backed_files = list(logs_dir.glob("*.jsonl"))
            self.assertEqual(len(backed_files), 1)
            self.assertIn("hello", backed_files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
