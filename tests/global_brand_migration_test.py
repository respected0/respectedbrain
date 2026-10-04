"""Global legacy merge and transaction rollback protections."""
import json
from unittest import TestCase, mock
from tests.foundation_integrations_test import IntegrationFixture
from tests.foundation_support import snapshot
from respectedbrain.core.legacy_names import LEGACY_GLOBAL_BEGIN, LEGACY_GLOBAL_END, LEGACY_CURSOR_RULE, LEGACY_HOOK_NAME, LEGACY_GLOBAL_BACKUP_ROOT
from respectedbrain.integrations.rendering import plan_integrations
from respectedbrain.integrations.backend import ExternalChange
from respectedbrain.installation.transaction import Transaction

class GlobalBrandMigrationTest(IntegrationFixture, TestCase):
    def block(self):
        return LEGACY_GLOBAL_BEGIN + "\nlegacy\n" + LEGACY_GLOBAL_END

    def test_preview_is_read_only_and_apply_migrates_all_legacy_identities_idempotently(self):
        for relative in (".gemini/GEMINI.md", ".codex/AGENTS.md", ".claude/CLAUDE.md"):
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Personal rule\n\n" + self.block() + "\n", encoding="utf-8")
        hooks = self.home / ".gemini/config/hooks.json"
        hooks.parent.mkdir()
        hooks.write_text(json.dumps({"personal-hook": {"enabled": True}, LEGACY_HOOK_NAME: {"legacy": True}}), encoding="utf-8")
        cursor = self.home / ".cursor/rules" / LEGACY_CURSOR_RULE
        cursor.parent.mkdir(parents=True)
        cursor.write_text(self.block(), encoding="utf-8")
        before = snapshot(self.root)
        rows = plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        self.assertEqual(snapshot(self.root), before)
        backend = self.backend()
        with Transaction(self.data, backend, vault_id=self.ctx.paths.vault_id) as tx:
            for row in rows:
                tx.apply_external(row)
            tx.commit()
        for relative in (".gemini/GEMINI.md", ".codex/AGENTS.md", ".claude/CLAUDE.md"):
            text = (self.home / relative).read_text(encoding="utf-8")
            self.assertIn("# Personal rule", text)
            self.assertEqual(text.count("<!-- RESPECTED-GLOBAL:BEGIN -->"), 1)
            self.assertNotIn(LEGACY_GLOBAL_BEGIN, text)
        self.assertIn("personal-hook", json.loads(hooks.read_text(encoding="utf-8")))
        self.assertFalse(cursor.exists())
        self.assertEqual(plan_integrations(self.ctx, self.profile, {"global": True}, backend), ())
        self.assertTrue((self.data / "backups").is_dir())

    def test_current_and_legacy_blocks_collide_without_mutation(self):
        path = self.home / ".codex/AGENTS.md"
        path.parent.mkdir()
        path.write_text(self.block() + "\n<!-- RESPECTED-GLOBAL:BEGIN -->current<!-- RESPECTED-GLOBAL:END -->", encoding="utf-8")
        before = snapshot(self.root)
        with self.assertRaisesRegex(ValueError, "çakış"):
            plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        self.assertEqual(snapshot(self.root), before)

    def test_unverified_legacy_cursor_rule_fails_closed(self):
        path = self.home / ".cursor/rules" / LEGACY_CURSOR_RULE
        path.parent.mkdir(parents=True)
        path.write_text("# User-owned file", encoding="utf-8")
        before = snapshot(self.root)
        with self.assertRaisesRegex(ValueError, "doğrulan"):
            plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        self.assertEqual(snapshot(self.root), before)

    def test_failed_apply_removes_new_files_and_directories_after_rollback(self):
        backend = self.backend()
        writes = [ExternalChange("file", str(self.home / ".codex/hooks.json"), None, b"{}\n"), ExternalChange("file", str(self.home / ".codex/AGENTS.md"), None, b"managed\n")]
        original = backend.apply
        def fail_second(change):
            if change.key.endswith("AGENTS.md"):
                raise OSError("injected-write-failure")
            return original(change)
        with mock.patch.object(backend, "apply", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "injected-write-failure"):
                with Transaction(self.data, backend, vault_id=self.ctx.paths.vault_id) as tx:
                    for row in writes:
                        tx.apply_external(row)
                    tx.commit()
        self.assertFalse((self.home / ".codex").exists())

    def test_legacy_and_current_backup_roots_are_preserved_as_unknown_user_data(self):
        for relative in (LEGACY_GLOBAL_BACKUP_ROOT, ".respected-backups"):
            path = self.home / relative
            path.mkdir()
            (path / "keep.txt").write_text(relative, encoding="utf-8")
        before = snapshot(self.home)
        rows = plan_integrations(self.ctx, self.profile, {"global": True}, self.backend())
        self.assertEqual(snapshot(self.home), before)
        self.assertFalse(any("backups" in row.key for row in rows))
