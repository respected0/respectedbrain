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
