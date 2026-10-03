"""Context-bound maintenance and explicit code-project orchestration contracts."""
from __future__ import annotations

import contextlib
import importlib
import io
import errno
import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from respectedbrain.core.context import AppContext
from respectedbrain.core.paths import AppPaths
from respectedbrain.core.resources import ResourceCatalog
from tests.foundation_support import snapshot


class FoundationMaintenanceOrchestrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.app, self.data = self.root / 'app', self.root / 'data'
        self.vault, self.vault2 = self.root / 'Türkçe 🧠 Vault', self.root / 'İkinci Vault'
        self.project = self.root / 'code project'
        for root in (self.app, self.vault, self.vault2, self.project):
            root.mkdir()
        (self.vault / 'knowledge').mkdir()
        (self.vault / 'daily').mkdir()
        (self.vault2 / 'sentinel.md').write_text('other vault', encoding='utf-8')
        self.ctx = AppContext(AppPaths(self.app, self.data, self.vault,
                             '8c76006b-33bb-4cc0-80ce-52a0c8f38f2a'), {}, ResourceCatalog())

    def test_tools_use_selected_vault_without_app_or_other_vault_writes(self):
        maintenance = importlib.import_module('respectedbrain.maintenance')
        before_app, before_other = snapshot(self.app), snapshot(self.vault2)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = maintenance.run_tool(self.ctx, name='vault_linter', argv=['--json'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['vault_root'], str(self.vault))
        self.assertEqual(snapshot(self.app), before_app)
        self.assertEqual(snapshot(self.vault2), before_other)
        self.assertFalse((self.vault / '.beyin').exists())

    def test_explicit_tool_vault_mismatch_fails_before_mutation(self):
        maintenance = importlib.import_module('respectedbrain.maintenance')
        before = snapshot(self.root)
        with self.assertRaises(ValueError):
            maintenance.run_tool(self.ctx, name='vault_linter', argv=['--vault', str(self.vault2), '--fix-dashes'])
        self.assertEqual(snapshot(self.root), before)

    def test_orchestration_project_is_not_vault_and_logs_are_data(self):
        runner = importlib.import_module('respectedbrain.orchestration.runner')
        before_app, before_vault = snapshot(self.app), snapshot(self.vault)
        def fake_subprocess(command, **kwargs):
            if command[:2] == ['git', 'rev-parse']:
                self.assertEqual(kwargs['cwd'], self.project)
                return subprocess.CompletedProcess(command, 0, 'basecommit\n', '')
            if command[:3] == ['git', 'worktree', 'add']:
                worktree = Path(command[-2])
                self.assertEqual(worktree.parent.parent, self.project)
                worktree.mkdir(parents=True)
                return subprocess.CompletedProcess(command, 0, '', '')
            self.fail(f'unexpected subprocess: {command}')
        with mock.patch.object(runner.subprocess, 'run', side_effect=fake_subprocess), mock.patch.object(runner.shutil, 'which', return_value=None):
            code = runner.run(self.ctx, project_root=self.project, argv=['--task', 'a task', '--worker', 'codex'])
        self.assertEqual(code, 1)
        metadata_files = list((self.ctx.paths.state_dir / 'orchestration').glob('*/metadata.json'))
        self.assertEqual(len(metadata_files), 1)
        metadata = json.loads(metadata_files[0].read_text(encoding='utf-8'))
        self.assertEqual(metadata['repo_root'], str(self.project))
        self.assertEqual(metadata['status'], 'failed')
        self.assertEqual(snapshot(self.app), before_app)
        self.assertEqual(snapshot(self.vault), before_vault)

    def test_orchestration_accepts_dispatcher_argument_separator(self):
        runner = importlib.import_module('respectedbrain.orchestration.runner')
        with mock.patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'not git')), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = runner.run(self.ctx, project_root=self.project, argv=['--', '--task', 'a task'])
        self.assertEqual(code, 1)

    def test_orchestration_rejects_vault_as_code_project(self):
        runner = importlib.import_module('respectedbrain.orchestration.runner')
        before = snapshot(self.root)
        with self.assertRaises(ValueError):
            runner.run(self.ctx, project_root=self.vault, argv=['--task', 'a task'])
        self.assertEqual(snapshot(self.root), before)

    def test_agent_history_idempotency_is_in_state_not_vault(self):
        miner_module = importlib.import_module('respectedbrain.maintenance.ingestion.mine_agent_history')
        miner = miner_module.AgentHistoryMiner(self.vault, state_file=self.ctx.paths.state_dir / 'imported_sessions.json')
        miner.imported_ids.add('session-one')
        miner._save_state()
        another = miner_module.AgentHistoryMiner(self.vault, state_file=self.ctx.paths.state_dir / 'imported_sessions.json')
        self.assertEqual(another.imported_ids, {'session-one'})
        self.assertFalse((self.vault / '.beyin').exists())

    def test_snapshot_receipt_uses_data_and_preserves_interval_guard(self):
        module = importlib.import_module('respectedbrain.maintenance.backup.publish_git_snapshot')
        receipt = self.ctx.paths.state_dir / 'git-snapshot-receipt.json'
        with mock.patch.object(module, '_branch_divergence_status', return_value='clean'), mock.patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')):
            result = module.publish_if_due(self.vault, apply=True, receipt_file=receipt)
            second = module.publish_if_due(self.vault, apply=True, receipt_file=receipt)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(second['status'], 'skipped:not_due')
        self.assertTrue(receipt.is_file())
        self.assertFalse((self.vault / '.beyin').exists())

    def test_restic_restore_verification_temp_is_data_cache(self):
        module = importlib.import_module('respectedbrain.maintenance.backup.backup_restic')
        restore_targets = []
        def fake_restic(command, **kwargs):
            if command[1] == 'backup':
                return subprocess.CompletedProcess(command, 0, '{"message_type":"summary","snapshot_id":"snapshot-one"}', '')
            target = Path(command[-1])
            self.assertTrue(target.is_relative_to(self.ctx.paths.cache_dir))
            self.assertTrue(target.is_dir())
            restore_targets.append(target)
            return subprocess.CompletedProcess(command, 0, '', '')
        with mock.patch.object(module, 'check_prerequisites', return_value=(True, 'restic')), mock.patch.object(module.subprocess, 'run', side_effect=fake_restic):
            result = module.run_backup(self.vault, str(self.root / 'backup-target'), apply=True, temp_dir=self.ctx.paths.cache_dir)
        self.assertEqual(result, {'status': 'ok', 'snapshot_id': 'snapshot-one'})
        self.assertEqual(len(restore_targets), 1)
        self.assertFalse(restore_targets[0].exists())

    def test_guarded_antigravity_records_failure_in_selected_data(self):
        module = importlib.import_module('respectedbrain.orchestration.antigravity_orchestrator')
        for argv in (['init'], ['config', 'user.name', 'Test'], ['config', 'user.email', 'test@example.invalid']):
            subprocess.run(['git', *argv], cwd=self.project, check=True, capture_output=True)
        (self.project / 'owned.txt').write_text('baseline', encoding='utf-8')
        subprocess.run(['git', 'add', 'owned.txt'], cwd=self.project, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'baseline'], cwd=self.project, check=True, capture_output=True)
        policy = self.project / 'policy.json'
        policy.write_text(json.dumps({'schema_version': 1, 'worker_executable_candidates': [str(self.root / 'missing-agy')], 'workspace_root': '.worktrees', 'max_active_write_workers': 1, 'read_timeout_seconds': 10, 'write_timeout_seconds': 10, 'dangerously_skip_permissions': False}), encoding='utf-8')
        before_vault, before_app = snapshot(self.vault), snapshot(self.app)
        with contextlib.redirect_stdout(io.StringIO()):
            code = module.main(['run-read', '--slug', 'read-task', '--objective', 'inspect', '--owner', 'owned.txt', '--policy', str(policy), '--run-id', 'read-one'], ctx=self.ctx, project_root=self.project)
        self.assertEqual(code, 20)
        result = json.loads((self.ctx.paths.state_dir / 'orchestration' / 'read-one' / 'verification.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'WORKER_FAILED')
        self.assertFalse((self.project / '.worktrees' / '.orchestration-state').exists())
        self.assertEqual(snapshot(self.vault), before_vault)
        self.assertEqual(snapshot(self.app), before_app)

    def test_gateway_run_services_use_recorded_project_and_bound_rejection(self):
        runner = importlib.import_module('respectedbrain.orchestration.runner')
        run_root = self.ctx.paths.state_dir / 'orchestration' / 'run-owned'
        run_root.mkdir(parents=True)
        (run_root / 'metadata.json').write_text(json.dumps({'run_id': 'run-owned', 'vault_id': self.ctx.paths.vault_id, 'repo_root': str(self.project), 'status': 'completed'}), encoding='utf-8')
        (run_root / 'worker.patch').write_text('diff --git a/owned.txt b/owned.txt\n--- a/owned.txt\n+++ b/owned.txt\n@@ -1 +1 @@\n-before\n+after\n', encoding='utf-8')
        (self.project / 'owned.txt').write_text('before\n', encoding='utf-8')
        subprocess.run(['git', 'init'], cwd=self.project, check=True, capture_output=True)
        before_vault = snapshot(self.vault)
        listing = runner.list_runs(self.ctx)
        self.assertEqual(listing['runs'][0]['run_id'], 'run-owned')
        self.assertTrue(listing['runs'][0]['has_patch'])
        result = runner.apply_run(self.ctx, 'run-owned')
        self.assertTrue(result['success'])
        self.assertEqual((self.project / 'owned.txt').read_text(encoding='utf-8'), 'after\n')
        with self.assertRaises(ValueError):
            runner.reject_run(self.ctx, '../outside')
        self.assertTrue(run_root.is_dir())
        result = runner.reject_run(self.ctx, 'run-owned')
        self.assertTrue(result['success'])
        self.assertFalse(run_root.exists())
        self.assertEqual(snapshot(self.vault), before_vault)

    def test_smart_merge_commits_safely_when_vault_is_on_another_volume(self):
        module = importlib.import_module('respectedbrain.maintenance.smart_merge')
        maintenance = importlib.import_module('respectedbrain.maintenance')
        source, target = self.vault / 'Source.md', self.vault / 'Target.md'
        source.write_text('---\ntags: source\n---\n# Source\nNew fact\n', encoding='utf-8')
        target.write_text('---\ntags: target\n---\n# Target\nExisting fact\n', encoding='utf-8')
        real_replace = os.replace
        cross_volume_attempts, commit_temps = [], []
        def replace(staging, destination):
            staging, destination = Path(staging), Path(destination)
            if staging.is_relative_to(self.ctx.paths.cache_dir):
                cross_volume_attempts.append(staging)
                raise OSError(errno.EXDEV, 'different volume')
            self.assertEqual(staging.parent, destination.parent)
            commit_temps.append(staging)
            return real_replace(staging, destination)
        with mock.patch.object(module.os, 'replace', side_effect=replace), contextlib.redirect_stdout(io.StringIO()):
            code = maintenance.run_tool(self.ctx, name='smart_merge', argv=['--source', str(source), '--target', str(target)])
        self.assertEqual(code, 0)
        merged = target.read_text(encoding='utf-8')
        self.assertIn('New fact', merged)
        self.assertIn('Existing fact', merged)
        self.assertIn('[[Target]]', source.read_text(encoding='utf-8'))
        self.assertEqual(len(cross_volume_attempts), 2)
        self.assertEqual(len(commit_temps), 2)
        self.assertEqual(set(path.name for path in self.vault.glob('*.md')), {'Source.md', 'Target.md'})
        self.assertFalse(any(path.is_file() for path in self.ctx.paths.cache_dir.rglob('*')))

    def test_backup_cannot_write_an_explicit_repository_under_app_root(self):
        maintenance = importlib.import_module('respectedbrain.maintenance')
        module = importlib.import_module('respectedbrain.maintenance.backup.backup_restic')
        before = snapshot(self.app)
        with mock.patch.object(module, 'check_prerequisites', return_value=(True, 'restic')), mock.patch.object(module.subprocess, 'run', side_effect=AssertionError('backup must reject before subprocess')):
            with self.assertRaises(ValueError):
                maintenance.run_tool(self.ctx, name='backup_restic', argv=['--repo', str(self.app / 'backup-repository'), '--apply'])
        self.assertEqual(snapshot(self.app), before)

    def test_local_html_ingestion_keeps_existing_conversion(self):
        maintenance = importlib.import_module('respectedbrain.maintenance')
        source = self.root / 'page.html'
        target = self.root / 'clean.md'
        source.write_text('<html><body><h1>Useful</h1><script>noise()</script><p>A fact</p></body></html>', encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            code = maintenance.run_tool(self.ctx, name='defuddle', argv=['--file', str(source), '--output', str(target)])
        self.assertEqual(code, 0)
        self.assertIn('# Useful', target.read_text(encoding='utf-8'))
        self.assertNotIn('noise()', target.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
