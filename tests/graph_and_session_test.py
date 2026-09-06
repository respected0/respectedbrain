import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# .beyin gizli klasör olduğu için sys.path'e ekliyoruz
BEYIN_DIR = Path(__file__).resolve().parent.parent / "template" / ".beyin"
sys.path.insert(0, str(BEYIN_DIR))

from graph_analysis import analyze_graph, build_graph, find_bridge_nodes  # type: ignore[import-not-found]
from graphrag import build_index, find_path, query_vault  # type: ignore[import-not-found]
from session_brain import SessionBrain  # type: ignore[import-not-found]


class TestGraphAnalysis(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Test vault'u oluştur: A -> B -> C ve D (yetim)
        (self.temp_dir / "Page A.md").write_text("# Page A\nBağlantı: [[Page B]]\n", encoding="utf-8")
        (self.temp_dir / "Page B.md").write_text("# Page B\nBağlantı: [[Page C]]\n", encoding="utf-8")
        (self.temp_dir / "Page C.md").write_text("# Page C\nSon nokta, [[NonExistent]] kırık link.\n", encoding="utf-8")
        (self.temp_dir / "Orphan.md").write_text("# Orphan\nHiçbir yere bağlanmıyor.\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_graph_construction_and_orphans(self):
        res = analyze_graph(self.temp_dir)
        self.assertEqual(res["total_pages"], 4)
        self.assertIn("Orphan", res["orphans"])
        self.assertEqual(res["broken_links_count"], 1)
        self.assertIn("NonExistent", res["broken_links"].get("Page C", []))

    def test_hub_and_degree(self):
        res = analyze_graph(self.temp_dir)
        hubs = {h["title"]: h for h in res["hubs"]}
        self.assertIn("Page B", hubs)
        self.assertEqual(hubs["Page B"]["in_degree"], 1)
        self.assertEqual(hubs["Page B"]["out_degree"], 1)

    def test_synthesis_gaps(self):
        # A -> B ve C -> B (A ile C arasında link yok ama ortak komşu B)
        res = analyze_graph(self.temp_dir)
        gaps = res.get("synthesis_gaps", [])
        self.assertGreater(len(gaps), 0)
        pair = {gaps[0]["node_a"], gaps[0]["node_b"]}
        self.assertIn("Page A", pair)
        self.assertIn("Page C", pair)

    def test_cross_link_vault(self):
        from graph_analysis import cross_link_vault  # type: ignore[import-not-found]
        # Orphan içine "Burada Page A anlatılıyor." yazalım
        (self.temp_dir / "Orphan.md").write_text("# Orphan\nBurada Page A kavramı geçiyor.", encoding="utf-8")
        
        # 1. Dry run kontrolü
        report = cross_link_vault(self.temp_dir, apply_changes=False)
        self.assertIn("Page A", report["suggestions"].get("Orphan", []))
        
        # 2. Apply kontrolü
        cross_link_vault(self.temp_dir, apply_changes=True)
        updated_text = (self.temp_dir / "Orphan.md").read_text(encoding="utf-8")
        self.assertIn("[[Page A]]", updated_text)


class TestGraphRAG(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        
        (self.temp_dir / "Auth.md").write_text(
            "---\ntitle: Kimlik Doğrulama\ntags: [auth, security, jwt]\nsummary: JWT tabanlı oturum yönetimi mimarisi.\n---\n# Auth\nDetaylar...",
            encoding="utf-8"
        )
        (self.temp_dir / "Database.md").write_text(
            "---\ntitle: Veritabanı\ntags: [postgres, sql]\nsummary: PostgreSQL bağlantı havuzu ve şema.\n---\n# DB\nDetaylar...",
            encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_ranking_and_index_only(self):
        res = query_vault(self.temp_dir, "JWT oturum yönetimi nasıl çalışır?")
        self.assertGreater(len(res["candidates"]), 0)
        top = res["candidates"][0]
        self.assertEqual(top["title"], "Kimlik Doğrulama")
        # Özet soruyu karşıladığı için index_only True olmalı
        self.assertTrue(res["index_only"])

    def test_path_finding(self):
        # A -> B -> C bağlantısı ekle
        (self.temp_dir / "NodeA.md").write_text("# NodeA\n[[NodeB]]", encoding="utf-8")
        (self.temp_dir / "NodeB.md").write_text("# NodeB\n[[NodeC]]", encoding="utf-8")
        (self.temp_dir / "NodeC.md").write_text("# NodeC\nBitiş", encoding="utf-8")
        
        idx = build_index(self.temp_dir)
        p = find_path(idx, "NodeA", "NodeC")
        self.assertEqual(p, ["NodeA", "NodeB", "NodeC"])

    def test_path_finding_unreachable_and_missing_nodes_return_none(self):
        (self.temp_dir / "NodeA.md").write_text("# NodeA\n[[NodeB]]", encoding="utf-8")
        (self.temp_dir / "NodeB.md").write_text("# NodeB\nSon", encoding="utf-8")
        (self.temp_dir / "Isolated.md").write_text("# Isolated\nBağımsız", encoding="utf-8")

        idx = build_index(self.temp_dir)
        # 1. Unreachable destination
        self.assertIsNone(find_path(idx, "NodeA", "Isolated"))
        # 2. Non-existent destination
        self.assertIsNone(find_path(idx, "NodeA", "NonExistent"))
        # 3. Non-existent source
        self.assertIsNone(find_path(idx, "NonExistent", "NodeA"))


class TestSessionBrain(unittest.TestCase):
    def setUp(self):
        self.temp_sidecar = Path(tempfile.mkdtemp())
        self.temp_data = Path(tempfile.mkdtemp())
        
        # Test JSONL oturumu oluştur
        sample_jsonl = self.temp_data / "sessions.jsonl"
        lines = [
            json.dumps({"id": "sess-1", "title": "OAuth Bug Fix", "text": "Token refresh loop sorunu giderildi ve refresh token süresi uzatıldı.", "timestamp": 1700000000}),
            json.dumps({"id": "sess-2", "title": "Docker Setup", "text": "Container network konfigürasyonu ve Docker compose port ayarları.", "timestamp": 1700000000})
        ]
        sample_jsonl.write_text("\n".join(lines), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_sidecar, ignore_errors=True)
        shutil.rmtree(self.temp_data, ignore_errors=True)

    def test_ingest_and_query(self):
        sb = SessionBrain(self.temp_sidecar)
        count = sb.ingest_file(self.temp_data / "sessions.jsonl")
        self.assertEqual(count, 2)
        self.assertEqual(len(sb.sessions), 2)
        
        # Arama testi
        results = sb.query("OAuth refresh token loop")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["id"], "sess-1")
        self.assertIn("Token refresh loop", results[0]["snippet"])

    def test_ingest_skips_corrupt_jsonl_lines(self):
        corrupt_jsonl = self.temp_data / "corrupt.jsonl"
        corrupt_jsonl.write_text(
            '{"id": "valid-1", "title": "Valid One", "text": "Content one"}\n'
            '{"id": "broken", invalid json line\n'
            '{"id": "valid-2", "title": "Valid Two", "text": "Content two"}\n',
            encoding="utf-8",
        )
        sb = SessionBrain(self.temp_sidecar)
        count = sb.ingest_file(corrupt_jsonl)
        # Should ingest 2 valid items without throwing on the corrupt middle line
        self.assertEqual(count, 2)
        self.assertIn("valid-1", sb.sessions)
        self.assertIn("valid-2", sb.sessions)

    def test_session_viz_renders_html(self):
        from session_viz import render_html  # type: ignore[import-not-found]
        sb = SessionBrain(self.temp_sidecar)
        sb.ingest_file(self.temp_data / "sessions.jsonl")
        
        out_html = self.temp_data / "graph.html"
        render_html(sb.index_file, out_html)
        self.assertTrue(out_html.is_file())
        content = out_html.read_text(encoding="utf-8")
        self.assertIn("vis-network", content)
        self.assertIn("OAuth Bug Fix", content)


if __name__ == "__main__":
    unittest.main()
