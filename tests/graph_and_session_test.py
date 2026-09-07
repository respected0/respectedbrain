import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ORIGINAL_SYS_PATH = None

# .beyin gizli klasör olduğu için sys.path'e ekliyoruz
BEYIN_DIR = Path(__file__).resolve().parent.parent / "template" / ".beyin"
if str(BEYIN_DIR) not in sys.path:
    sys.path.insert(0, str(BEYIN_DIR))


def setUpModule() -> None:
    global ORIGINAL_SYS_PATH
    ORIGINAL_SYS_PATH = list(sys.path)
    if str(BEYIN_DIR) not in sys.path:
        sys.path.insert(0, str(BEYIN_DIR))


def tearDownModule() -> None:
    if ORIGINAL_SYS_PATH is not None:
        sys.path[:] = ORIGINAL_SYS_PATH


from graph_analysis import analyze_graph, build_graph, find_bridge_nodes, cross_link_vault  # type: ignore[import-not-found]
from graphrag import build_index, find_path, query_vault  # type: ignore[import-not-found]
from session_brain import SessionBrain  # type: ignore[import-not-found]
from session_viz import render_html  # type: ignore[import-not-found]


class TestGraphAnalysis(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir_obj.name)

        # Test vault'u oluştur: A -> B -> C ve D (yetim)
        (self.temp_dir / "Page A.md").write_text("# Page A\nBağlantı: [[Page B]]\n", encoding="utf-8")
        (self.temp_dir / "Page B.md").write_text("# Page B\nBağlantı: [[Page C]]\n", encoding="utf-8")
        (self.temp_dir / "Page C.md").write_text("# Page C\nSon nokta, [[NonExistent]] kırık link.\n", encoding="utf-8")
        (self.temp_dir / "Orphan.md").write_text("# Orphan\nHiçbir yere bağlanmıyor.\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._temp_dir_obj.cleanup()

    def test_graph_construction_and_orphans(self) -> None:
        res = analyze_graph(self.temp_dir)
        self.assertEqual(res["total_pages"], 4)
        self.assertIn("Orphan", res["orphans"])
        self.assertEqual(res["broken_links_count"], 1)
        self.assertIn("NonExistent", res["broken_links"].get("Page C", []))

    def test_hub_and_degree(self) -> None:
        res = analyze_graph(self.temp_dir)
        hubs = {h["title"]: h for h in res["hubs"]}
        self.assertIn("Page B", hubs)
        self.assertEqual(hubs["Page B"]["in_degree"], 1)
        self.assertEqual(hubs["Page B"]["out_degree"], 1)

    def test_synthesis_gaps(self) -> None:
        res = analyze_graph(self.temp_dir)
        gaps = res.get("synthesis_gaps", [])
        self.assertGreater(len(gaps), 0)
        pair = {gaps[0]["node_a"], gaps[0]["node_b"]}
        self.assertIn("Page A", pair)
        self.assertIn("Page C", pair)

    def test_cross_link_vault(self) -> None:
        (self.temp_dir / "Orphan.md").write_text("# Orphan\nBurada Page A kavramı geçiyor.", encoding="utf-8")

        # 1. Dry run kontrolü
        report = cross_link_vault(self.temp_dir, apply_changes=False)
        self.assertIn("Page A", report["suggestions"].get("Orphan", []))

        # 2. Apply kontrolü
        cross_link_vault(self.temp_dir, apply_changes=True)
        updated_text = (self.temp_dir / "Orphan.md").read_text(encoding="utf-8")
        self.assertIn("[[Page A]]", updated_text)

    def test_wikilinks_with_aliases_and_section_anchors(self) -> None:
        # [[Page B|Görünen Metin]] ve [[Page C#Alt Başlık]]
        (self.temp_dir / "Page A.md").write_text(
            "# Page A\nBkz: [[Page B|Takma Ad]] ve [[Page C#Giriş]] ve bozuk: [[]] [[   ]]\n",
            encoding="utf-8",
        )
        g = build_graph(self.temp_dir)
        # Page A -> Page B ve Page C'ye yönlendirmeli
        self.assertIn("page-b", g["adj"]["page-a"])
        self.assertIn("page-c", g["adj"]["page-a"])
        # Boş wikilink [[]] ya da [[  ]] kırık link olarak eklenmemeli
        for broken in g["broken_links"].get("page-a", []):
            self.assertTrue(bool(broken.strip()), f"Blank link found in broken_links: {broken!r}")

    def test_self_referencing_link_does_not_create_self_loop(self) -> None:
        (self.temp_dir / "SelfRef.md").write_text("# Self\nBkz: [[SelfRef]]", encoding="utf-8")
        g = build_graph(self.temp_dir)
        self.assertNotIn("selfref", g["adj"]["selfref"])


class TestGraphRAG(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir_obj.name)

        (self.temp_dir / "Auth.md").write_text(
            "---\ntitle: Kimlik Doğrulama\ntags: [auth, security, jwt]\nsummary: JWT tabanlı oturum yönetimi mimarisi.\n---\n# Auth\nDetaylar...",
            encoding="utf-8",
        )
        (self.temp_dir / "Database.md").write_text(
            "---\ntitle: Veritabanı\ntags: [postgres, sql]\nsummary: PostgreSQL bağlantı havuzu ve şema.\n---\n# DB\nDetaylar...",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._temp_dir_obj.cleanup()

    def test_query_ranking_and_index_only(self) -> None:
        res = query_vault(self.temp_dir, "JWT oturum yönetimi nasıl çalışır?")
        self.assertGreater(len(res["candidates"]), 0)
        top = res["candidates"][0]
        self.assertEqual(top["title"], "Kimlik Doğrulama")
        self.assertTrue(res["index_only"])

    def test_query_vault_zero_relevance_returns_gracefully(self) -> None:
        res = query_vault(self.temp_dir, "uzay gemisi mars roket yakıtı")
        self.assertIsInstance(res, dict)
        self.assertIn("candidates", res)
        # Low or zero relevance should not trigger index_only summary confidence
        self.assertFalse(res.get("index_only", False))

    def test_path_finding(self) -> None:
        (self.temp_dir / "NodeA.md").write_text("# NodeA\n[[NodeB]]", encoding="utf-8")
        (self.temp_dir / "NodeB.md").write_text("# NodeB\n[[NodeC]]", encoding="utf-8")
        (self.temp_dir / "NodeC.md").write_text("# NodeC\nBitiş", encoding="utf-8")

        idx = build_index(self.temp_dir)
        p = find_path(idx, "NodeA", "NodeC")
        self.assertEqual(p, ["NodeA", "NodeB", "NodeC"])

    def test_path_finding_unreachable_and_missing_nodes_return_none(self) -> None:
        (self.temp_dir / "NodeA.md").write_text("# NodeA\n[[NodeB]]", encoding="utf-8")
        (self.temp_dir / "NodeB.md").write_text("# NodeB\nSon", encoding="utf-8")
        (self.temp_dir / "Isolated.md").write_text("# Isolated\nBağımsız", encoding="utf-8")

        idx = build_index(self.temp_dir)
        self.assertIsNone(find_path(idx, "NodeA", "Isolated"))
        self.assertIsNone(find_path(idx, "NodeA", "NonExistent"))
        self.assertIsNone(find_path(idx, "NonExistent", "NodeA"))


class TestSessionBrain(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_sidecar_obj = tempfile.TemporaryDirectory()
        self._temp_data_obj = tempfile.TemporaryDirectory()
        self.temp_sidecar = Path(self._temp_sidecar_obj.name)
        self.temp_data = Path(self._temp_data_obj.name)

        sample_jsonl = self.temp_data / "sessions.jsonl"
        lines = [
            json.dumps({"id": "sess-1", "title": "OAuth Bug Fix", "text": "Token refresh loop sorunu giderildi ve refresh token süresi uzatıldı.", "timestamp": 1700000000}),
            json.dumps({"id": "sess-2", "title": "Docker Setup", "text": "Container network konfigürasyonu ve Docker compose port ayarları.", "timestamp": 1700000000}),
        ]
        sample_jsonl.write_text("\n".join(lines), encoding="utf-8")

    def tearDown(self) -> None:
        self._temp_sidecar_obj.cleanup()
        self._temp_data_obj.cleanup()

    def test_ingest_and_query(self) -> None:
        sb = SessionBrain(self.temp_sidecar)
        count = sb.ingest_file(self.temp_data / "sessions.jsonl")
        self.assertEqual(count, 2)
        self.assertEqual(len(sb.sessions), 2)

        results = sb.query("OAuth refresh token loop")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["id"], "sess-1")
        self.assertIn("Token refresh loop", results[0]["snippet"])

    def test_ingest_skips_corrupt_jsonl_lines(self) -> None:
        corrupt_jsonl = self.temp_data / "corrupt.jsonl"
        corrupt_jsonl.write_text(
            '{"id": "valid-1", "title": "Valid One", "text": "Content one"}\n'
            '{"id": "broken", invalid json line\n'
            '{"id": "valid-2", "title": "Valid Two", "text": "Content two"}\n',
            encoding="utf-8",
        )
        sb = SessionBrain(self.temp_sidecar)
        count = sb.ingest_file(corrupt_jsonl)
        self.assertEqual(count, 2)
        self.assertIn("valid-1", sb.sessions)
        self.assertIn("valid-2", sb.sessions)

    def test_ingest_nonexistent_and_empty_file_returns_zero(self) -> None:
        sb = SessionBrain(self.temp_sidecar)
        self.assertEqual(sb.ingest_file(self.temp_data / "does_not_exist.jsonl"), 0)
        empty_file = self.temp_data / "empty.jsonl"
        empty_file.write_text("", encoding="utf-8")
        self.assertEqual(sb.ingest_file(empty_file), 0)

    def test_ingest_json_array_format(self) -> None:
        json_file = self.temp_data / "sessions_array.json"
        json_file.write_text(
            json.dumps([
                {"id": "arr-1", "title": "Array Sess", "content": "GraphQL batching optimization", "timestamp": 1700000000}
            ]),
            encoding="utf-8",
        )
        sb = SessionBrain(self.temp_sidecar)
        count = sb.ingest_file(json_file)
        self.assertEqual(count, 1)
        res = sb.query("GraphQL batching")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "arr-1")

    def test_query_no_matches_returns_empty_list(self) -> None:
        sb = SessionBrain(self.temp_sidecar)
        sb.ingest_file(self.temp_data / "sessions.jsonl")
        results = sb.query("xyzqwerty nonexistentterm123")
        self.assertEqual(results, [])

    def test_session_viz_renders_html(self) -> None:
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
