import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respectedbrain.memory.graph.graph_analysis import analyze_graph, build_graph, find_bridge_nodes, cross_link_vault
from respectedbrain.memory.graph.graphrag import build_index, find_path, query_vault
from respectedbrain.memory.session_brain import SessionBrain
from respectedbrain.memory.session_viz import render_html


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

    def test_duplicate_names_remain_separate_and_explicit_paths_resolve(self):
        for directory in ('one', 'two'):
            (self.temp_dir / directory).mkdir()
            (self.temp_dir / directory / 'Shared.md').write_text('# Shared', encoding='utf-8')
        (self.temp_dir / 'Page A.md').write_text('[[one/Shared.md]] [[two/Shared]] [[Shared]]', encoding='utf-8')
        graph = build_graph(self.temp_dir)
        self.assertEqual(len(graph['nodes']), 6)
        self.assertEqual(len(graph['adj']['page-a']), 2)
        self.assertIn('Shared', graph['broken_links']['page-a'])
        index = build_index(self.temp_dir)
        self.assertEqual(len(index['pages']), 6)
        self.assertEqual(find_path(index, 'Page A', 'two/Shared'), ['Page A', 'Shared'])
        self.assertIsNone(find_path(index, 'Page A', 'Shared'))

    def test_cross_link_preserves_metadata_code_and_existing_links(self):
        note = self.temp_dir / 'Orphan.md'
        protected = '---\ntitle: Page A\n---\n```python\nPage A\n```\n~~~\nPage A\n~~~\n`Page A`\n[[Page B|Page A]]\n[Page A](https://example.test)\n'
        note.write_text(protected + 'Prose contains Page A.\n', encoding='utf-8')
        cross_link_vault(self.temp_dir, apply_changes=True)
        self.assertEqual(note.read_text(encoding='utf-8'), protected + 'Prose contains [[Page A]].\n')

    def test_cross_link_preserves_bom_crlf_and_reference_links(self):
        note = self.temp_dir / 'Orphan.md'
        protected = '\ufeff---\r\ntitle: Page A\r\n---\r\n[Page A][ref]\r\n[ref]: https://example.test/Page-A\r\n'
        note.write_bytes((protected + 'Prose Page A.\r\n').encode('utf-8'))
        cross_link_vault(self.temp_dir, apply_changes=True)
        self.assertEqual(note.read_bytes(), (protected+'Prose [[Page A]].\r\n').encode('utf-8'))

    def test_cross_link_preserves_concurrent_edit(self):
        from respectedbrain.memory.graph import graph_analysis as module
        note = self.temp_dir / 'Orphan.md'
        note.write_text('Page A in prose.', encoding='utf-8')
        real_read = Path.read_bytes
        def reading(path):
            payload = real_read(path)
            if path == note:
                note.write_bytes(b'Human edit')
            return payload
        # The mutation must snapshot bytes before deriving its replacement.
        with mock.patch.object(Path, 'read_bytes', reading):
            with self.assertRaises(OSError):
                module.cross_link_vault(self.temp_dir, apply_changes=True)
        self.assertEqual(note.read_bytes(), b'Human edit')

    def test_bridge_scores_cover_entire_shortest_paths(self):
        nodes = set('ABCDE')
        adj = {n: set() for n in nodes}
        for a, b in zip('ABCD', 'BCDE'):
            adj[a].add(b)
        scores = dict(find_bridge_nodes(nodes, adj))
        self.assertEqual(scores, {'B': 3.0, 'C': 4.0, 'D': 3.0})

    def test_root_duplicate_bare_link_is_reported_ambiguous(self):
        (self.temp_dir / 'nested').mkdir()
        (self.temp_dir / 'Shared.md').write_text('root', encoding='utf-8')
        (self.temp_dir / 'nested/Shared.md').write_text('nested', encoding='utf-8')
        (self.temp_dir / 'Orphan.md').write_text('[[Shared.md]]', encoding='utf-8')
        self.assertEqual(build_graph(self.temp_dir)['broken_links']['orphan'], ['Shared.md'])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction boundary')
    def test_graph_scanners_and_cross_link_reject_external_junction(self):
        import subprocess
        with tempfile.TemporaryDirectory() as outside_name:
            outside = Path(outside_name)
            note = outside / 'External.md'
            note.write_bytes(b'Page A secret outside content')
            link = self.temp_dir / 'escape'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], check=True, capture_output=True)
            try:
                self.assertNotIn('External', [p['title'] for p in build_index(self.temp_dir)['pages'].values()])
                self.assertNotIn('external', build_graph(self.temp_dir)['nodes'])
                cross_link_vault(self.temp_dir, apply_changes=True)
                self.assertEqual(note.read_bytes(), b'Page A secret outside content')
            finally:
                os.rmdir(link)


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

    def test_hub_bonus_does_not_create_irrelevant_candidates(self):
        (self.temp_dir / 'Auth.md').write_text('[[Database]]', encoding='utf-8')
        self.assertEqual(query_vault(self.temp_dir, 'spaceship rocket engine')['candidates'], [])

    def test_nonpositive_read_budget_does_not_return_pages(self):
        for budget in (0, -1):
            with self.subTest(budget=budget):
                result = query_vault(self.temp_dir, 'jwt sql', max_read=budget)
                self.assertEqual(result['candidates'], [])
                self.assertEqual(result['should_read'], [])

    def test_rag_keeps_root_readme_searchable(self):
        (self.temp_dir / 'README.md').write_text('---\nsummary: architecture deployment\n---\n# README', encoding='utf-8')
        self.assertIn('readme', build_index(self.temp_dir)['pages'])


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

    def test_corrupt_or_invalid_index_is_preserved(self):
        for payload in (b'{broken', b'[]', b'{"bad": {"timestamp": "wrong"}}'):
            with self.subTest(payload=payload):
                index = self.temp_sidecar / 'index.json'
                index.write_bytes(payload)
                with self.assertRaises(ValueError):
                    SessionBrain(self.temp_sidecar)
                self.assertEqual(index.read_bytes(), payload)

    def test_stale_instances_merge_without_lost_sessions(self):
        first = SessionBrain(self.temp_sidecar)
        second = SessionBrain(self.temp_sidecar)
        first.ingest_session('first', 'Auth', 'auth refresh token')
        first.save_index()
        second.ingest_session('second', 'Docker', 'docker network')
        second.save_index()
        self.assertEqual(set(SessionBrain(self.temp_sidecar).sessions), {'first', 'second'})

    def test_atomic_index_failure_preserves_previous_bytes(self):
        from respectedbrain.core import config
        brain = SessionBrain(self.temp_sidecar)
        brain.ingest_session('first', 'Auth', 'auth token')
        brain.save_index()
        before = brain.index_file.read_bytes()
        brain.ingest_session('second', 'Docker', 'docker network')
        with mock.patch.object(config.os, 'replace', side_effect=PermissionError('disk denied')):
            with self.assertRaises(OSError):
                brain.save_index()
        self.assertEqual(brain.index_file.read_bytes(), before)

    def test_epoch_timestamp_and_negative_query_limit(self):
        brain = SessionBrain(self.temp_sidecar)
        brain.ingest_session('epoch', 'Auth', 'auth token', timestamp=0)
        self.assertEqual(brain.sessions['epoch']['timestamp'], 0)
        self.assertEqual(brain.query('auth', top_k=-1), [])

    def test_json_array_skips_bad_items_and_keeps_later_valid_items(self):
        path = self.temp_data / 'mixed.json'
        path.write_text(json.dumps([None, {'id':'a','content':'auth token'}, {'id':'bad','content':['wrong type']}, 42, {'id':'b','content':'docker network'}]), encoding='utf-8')
        brain = SessionBrain(self.temp_sidecar)
        self.assertEqual(brain.ingest_file(path), 2)
        self.assertEqual(set(brain.sessions), {'a', 'b'})

    def test_jsonl_epoch_timestamp_is_retained(self):
        path = self.temp_data / 'epoch.jsonl'
        path.write_text(json.dumps({'id':'epoch','content':'auth token','timestamp':0}), encoding='utf-8')
        brain = SessionBrain(self.temp_sidecar)
        self.assertEqual(brain.ingest_file(path), 1)
        self.assertEqual(brain.sessions['epoch']['timestamp'], 0)

    def test_process_writers_preserve_all_sessions(self):
        import subprocess
        gate = self.temp_data / 'start'
        code = """
import sys,time
from pathlib import Path
from respectedbrain.memory.session_brain import SessionBrain
brain=SessionBrain(Path(sys.argv[1]))
brain.ingest_session(sys.argv[2], 'Concurrent Auth', 'auth token')
while not Path(sys.argv[3]).exists(): time.sleep(.01)
brain.save_index()
"""
        processes = [subprocess.Popen([sys.executable,'-c',code,str(self.temp_sidecar),str(n),str(gate)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for n in range(4)]
        gate.touch()
        try:
            for process in processes:
                _, error = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, error.decode(errors='replace'))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        self.assertEqual(set(SessionBrain(self.temp_sidecar).sessions), {'0','1','2','3'})

    def test_viz_payload_cannot_break_out_of_script(self):
        brain = SessionBrain(self.temp_sidecar)
        attack = '</script><img src=x onerror=alert(1)>'
        brain.ingest_session('attack', attack, attack)
        brain.save_index()
        output = self.temp_data / 'attack.html'
        render_html(brain.index_file, output)
        content = output.read_text(encoding='utf-8')
        self.assertNotIn(attack, content)
        self.assertNotIn('.innerHTML', content)
        self.assertIn('textContent', content)

    def test_viz_filters_compose_and_click_renders_text(self):
        import re
        import shutil
        import subprocess
        import time
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node runtime unavailable for generated JavaScript')
        brain = SessionBrain(self.temp_sidecar)
        attack = 'Auth </script><img src=x onerror=alert(1)>'
        brain.ingest_session('recent', attack, attack)
        brain.ingest_session('old', 'Auth old', 'auth token', timestamp=time.time()-86400*100)
        brain.ingest_session('docker', 'Docker', 'docker network')
        brain.save_index()
        output = self.temp_data / 'interactive.html'
        render_html(brain.index_file, output)
        scripts = re.findall(r'<script>(.*?)</script>', output.read_text(encoding='utf-8'), re.DOTALL)
        harness = r'''
const vm = require('vm'), assert = require('assert');
class Element {
  constructor() { this.children=[]; this.style={}; this.value=''; this.events={}; this.textContent=''; }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.children.push(item); return item; }
  replaceChildren(...items) { this.children=items; }
  addEventListener(name, fn) { this.events[name]=fn; }
  set innerHTML(value) { throw Error('HTML injection sink'); }
}
const elements={};
const document={createElement:()=>new Element(),getElementById:id=>elements[id] ||= new Element()};
document.getElementById('timeSlider').value='180';
class DataSet {
  constructor() { this.items=new Map(); }
  add(item) { this.items.set(item.id, item); }
  update(item) { Object.assign(this.items.get(item.id), item); }
  forEach(fn) { this.items.forEach(fn); }
}
let network;
class Network { constructor(container, data) { this.data=data; this.events={}; network=this; } on(name, fn) { this.events[name]=fn; } }
const context={document,vis:{DataSet,Network},Date};
vm.runInNewContext(SCRIPT,context);
const search=elements.search, slider=elements.timeSlider;
search.value='auth'; search.events.input({target:search});
slider.value='1'; slider.events.input({target:slider});
assert.equal(network.data.nodes.items.get('docker').hidden,true);
assert.equal(network.data.nodes.items.get('old').hidden,true);
assert.equal(network.data.nodes.items.get('recent').hidden,false);
search.value=''; search.events.input({target:search});
assert.equal(network.data.nodes.items.get('old').hidden,true);
network.events.click({nodes:['recent']});
function text(element) { return element.textContent + element.children.map(text).join(''); }
assert(text(elements.details).includes(ATTACK));
assert.equal(network.data.nodes.items.get('recent').title.textContent,ATTACK);
'''
        harness = 'const SCRIPT='+json.dumps(scripts[0])+'; const ATTACK='+json.dumps(attack)+';\n'+harness
        result = subprocess.run([node, '-e', harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction boundary')
    def test_context_sidecar_rejects_cache_junction(self):
        import subprocess
        from tests.foundation_support import make_context
        with tempfile.TemporaryDirectory() as tech_name, tempfile.TemporaryDirectory() as vault_name:
            ctx = make_context(Path(tech_name), Path(vault_name))
            ctx.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            link = ctx.paths.cache_dir / 'session-brain'
            subprocess.run(['cmd','/c','mklink','/J',str(link),str(self.temp_sidecar)], check=True, capture_output=True)
            try:
                with self.assertRaises(ValueError):
                    SessionBrain(ctx)
                self.assertEqual(list(self.temp_sidecar.iterdir()), [])
            finally:
                os.rmdir(link)


if __name__ == "__main__":
    unittest.main()
