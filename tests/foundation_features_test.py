"""Feature boundaries: one selected UUID, no executable tree in notes."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tests.foundation_support import make_context, snapshot
from respectedbrain.search.engine import SearchEngine
from respectedbrain.briefing import service
from respectedbrain.vault.maps import rebuild_maps


class FakeModel:
    def __init__(self):
        self.calls = 0

    def run(self, prompt, *, cwd, mode, timeout):
        self.calls += 1
        return SimpleNamespace(text="\n".join(f"## {h}\n- Kanıt." for h in service.HEADINGS), provider="codex", error=None)


class FoundationFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = make_context(self.root)
        self.vault = self.ctx.paths.vault_root
        (self.root / "app").mkdir()
        self.vault2 = self.root / "İkinci Vault"
        self.vault2.mkdir()
        (self.vault / "knowledge").mkdir()
        (self.vault / "knowledge/karar.md").write_text("# Python Mimarisi\nSQLite kararları.", encoding="utf-8")

    def test_index_and_briefing_use_same_uuid_data(self):
        before_app, before_other = snapshot(self.root / "app"), snapshot(self.vault2)
        engine = SearchEngine(self.ctx)
        self.assertEqual(engine.index_vault()["indexed"], 1)
        self.assertEqual(engine.search("SQLite")[0]["path"], "knowledge/karar.md")
        fake = FakeModel()
        now = datetime.fromisoformat("2026-10-04T09:00:00+03:00")
        with patch.object(service, "compile_memory", return_value=0) as compile_call:
            self.assertEqual(service.run_if_due(self.ctx, model=fake, now=now), 0)
            calls = fake.calls
            self.assertEqual(service.run_if_due(self.ctx, model=fake, now=now), 0)
            self.assertEqual(compile_call.call_args.args[0], self.ctx)
            self.assertEqual(compile_call.call_count, 1)
        self.assertEqual(fake.calls, calls)
        self.assertTrue(any(self.ctx.paths.cache_dir.rglob("*.db")))
        self.assertTrue(any(self.ctx.paths.state_dir.iterdir()))
        self.assertFalse((self.vault / ".beyin").exists())
        self.assertFalse(any(self.vault.rglob("*.db")))
        self.assertEqual(snapshot(self.root / "app"), before_app)
        self.assertEqual(snapshot(self.vault2), before_other)

    def test_briefing_before_eight_is_read_only(self):
        before = snapshot(self.root)
        fake = FakeModel()
        self.assertEqual(service.run_if_due(self.ctx, model=fake, now=datetime(2026, 10, 4, 7, 59)), 0)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(snapshot(self.root), before)

    def test_index_detects_changed_content_with_preserved_mtime(self):
        import os
        engine = SearchEngine(self.ctx)
        engine.index_vault()
        note = self.vault / 'knowledge/karar.md'
        stamp = note.stat()
        note.write_text('# Replacement\nuniquechangedterm', encoding='utf-8')
        os.utime(note, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(engine.index_vault()['indexed'], 1)
        self.assertEqual(engine.search('uniquechangedterm')[0]['path'], 'knowledge/karar.md')
        self.assertEqual(engine.search('SQLite'), [])

    def test_nonpositive_search_and_backlink_limits_are_empty(self):
        engine = SearchEngine(self.ctx)
        (self.vault/'knowledge/karar.md').write_text('[[Target]] architecture', encoding='utf-8')
        engine.index_vault()
        for limit in (-1,0):
            self.assertEqual(engine.search('architecture', limit=limit), [])
            self.assertEqual(engine.get_backlinks('Target', limit=limit), [])

    def test_backlinks_support_path_extension_anchor_and_alias(self):
        engine = SearchEngine(self.ctx)
        (self.vault/'knowledge/karar.md').write_text('[[folder/Target.md#Section|Alias]]', encoding='utf-8')
        engine.index_vault()
        self.assertEqual(engine.get_backlinks('folder/Target.md'), ['knowledge/karar.md'])

    def test_fts_fallback_preserves_category_filter(self):
        engine = SearchEngine(self.ctx)
        (self.vault/'knowledge/karar.md').write_text('---\ntitle: Python Architecture\n---\nPython note',encoding='utf-8')
        (self.vault/'other').mkdir()
        (self.vault/'other/Python.md').write_text('Python elsewhere', encoding='utf-8')
        engine.index_vault()
        with engine._get_connection() as connection:
            connection.execute('DROP TABLE vault_fts')
            connection.commit()
        results = engine.search('Python', category='knowledge')
        self.assertEqual([item['path'] for item in results], ['knowledge/karar.md'])

    def test_metadata_delimiters_inside_values_and_body_are_preserved(self):
        from respectedbrain.search.engine import parse_markdown_meta
        metadata, body = parse_markdown_meta('---\ntitle: alpha---beta\n---\nBody\n---\nMore')
        self.assertEqual(metadata['title'], 'alpha---beta')
        self.assertEqual(body, 'Body\n---\nMore')
        metadata, body = parse_markdown_meta('----\nBody\n---\nMore')
        self.assertEqual(metadata, {})
        self.assertEqual(body, '----\nBody\n---\nMore')

    @unittest.skipUnless(__import__('os').name=='nt', 'Windows junction boundary')
    def test_search_rejects_cache_and_note_junctions(self):
        import os, subprocess
        with tempfile.TemporaryDirectory() as outside_name:
            outside = Path(outside_name)
            self.ctx.paths.cache_dir.parent.mkdir(parents=True, exist_ok=True)
            cache = self.ctx.paths.cache_dir
            subprocess.run(['cmd','/c','mklink','/J',str(cache),str(outside)], check=True,capture_output=True)
            try:
                with self.assertRaises(ValueError):
                    SearchEngine(self.ctx)
                self.assertEqual(list(outside.iterdir()), [])
            finally:
                os.rmdir(cache)
            (outside/'secret.md').write_text('externaluniquesecret',encoding='utf-8')
            link = self.vault/'escape'
            subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)], check=True,capture_output=True)
            try:
                engine=SearchEngine(self.ctx)
                engine.index_vault()
                self.assertEqual(engine.search('externaluniquesecret'), [])
            finally:
                os.rmdir(link)

    @unittest.skipUnless(__import__('os').name=='nt', 'Windows junction boundary')
    def test_existing_search_engine_revalidates_changed_paths(self):
        import os,subprocess
        engine=SearchEngine(self.ctx)
        engine.index_vault()
        with tempfile.TemporaryDirectory() as outside_name:
            outside=Path(outside_name)
            notes=self.vault/'knowledge'
            saved_notes=self.vault/'saved-knowledge'
            notes.rename(saved_notes)
            subprocess.run(['cmd','/c','mklink','/J',str(notes),str(outside)],check=True,capture_output=True)
            try:
                self.assertEqual(engine.search('SQLite'),[])
            finally:
                os.rmdir(notes)
                saved_notes.rename(notes)
            cache=self.ctx.paths.cache_dir
            saved_cache=cache.with_name('saved-cache')
            cache.rename(saved_cache)
            subprocess.run(['cmd','/c','mklink','/J',str(cache),str(outside)],check=True,capture_output=True)
            try:
                with self.assertRaises(ValueError):
                    engine.search('SQLite')
                self.assertEqual(list(outside.iterdir()),[])
            finally:
                os.rmdir(cache)
                saved_cache.rename(cache)

    def test_skills_map_uses_uuid_overrides_without_touching_package(self):
        custom = self.ctx.paths.overrides_dir / "skills/beyin-doktor/SKILL.md"
        custom.parent.mkdir(parents=True)
        custom.write_text("---\nname: beyin-doktor\ndescription: Kişisel kontrol.\n---\n", encoding="utf-8")
        before_app = snapshot(self.root / "app")
        rebuild_maps(self.ctx)
        skills = (self.vault / "🎯 100-Command-Center/Skills-Map.md").read_text(encoding="utf-8")
        self.assertIn("Kişisel kontrol.", skills)
        self.assertIn("ajan-gecmis-tara", skills)
        self.assertEqual(skills.count("`beyin-doktor`"), 1)
        self.assertEqual(snapshot(self.root / "app"), before_app)

    def test_dashboard_user_collision_fails_without_final_or_note_changes(self):
        dashboard = self.vault / "🎯 100-Command-Center/Dashboard.md"
        dashboard.parent.mkdir()
        original = "# Dashboard\n<!-- RESPECTED-BRIEFING:BEGIN -->\nKullanıcı"
        dashboard.write_text(original, encoding="utf-8")
        with patch.object(service, "compile_memory", return_value=0):
            self.assertEqual(service.run_if_due(self.ctx, model=FakeModel(), now=datetime(2026, 10, 4, 9)), 1)
        self.assertEqual(dashboard.read_text(encoding="utf-8"), original)
        self.assertFalse((dashboard.parent / "Briefings/2026-10-04.md").exists())
