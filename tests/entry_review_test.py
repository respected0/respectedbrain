"""Entry dispatch and final cross-module boundaries in isolated fixtures."""
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from respectedbrain import cli
from respectedbrain.core.locking import exclusive_lock
from respectedbrain.maintenance.ingestion.mine_agent_history import AgentHistoryMiner
from respectedbrain.orchestration import runner
from tests.foundation_support import make_context, snapshot


class EntryReviewTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.ctx = make_context(self.root)
        self.project = self.root / 'project'
        self.project.mkdir()

    def call(self, args):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(cli, 'bootstrap', return_value=self.ctx), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(args)
        return code, out.getvalue(), err.getvalue()

    def hook_input(self):
        path = self.ctx.paths.state_dir / 'hookin-fixture.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(session_id='fixture', transcript_path=str(self.root / 'missing.jsonl'))), encoding='utf-8')
        return path

    def test_failed_flush_preserves_managed_input_for_retry(self):
        path = self.hook_input()
        before = path.read_bytes()
        code, _, _ = self.call(['flush', '--hook-input', str(path)])
        self.assertEqual(code, 1)
        self.assertTrue(path.exists(), 'failure must retain the retry input')
        self.assertEqual(path.read_bytes(), before)

    def test_successful_flush_does_not_delete_changed_input(self):
        path = self.hook_input()
        edited = b'{"human":"late edit"}'
        def flush(*args, **kwargs):
            path.write_bytes(edited)
            return 0
        with patch('respectedbrain.memory.flush.flush_transcript', side_effect=flush):
            code, _, _ = self.call(['flush', '--hook-input', str(path)])
        self.assertEqual(code, 0)
        self.assertTrue(path.exists(), 'cleanup must preserve a late edit')
        self.assertEqual(path.read_bytes(), edited)

    def test_successful_flush_cleans_only_unchanged_managed_input(self):
        path = self.hook_input()
        transcript = self.root / 'missing.jsonl'
        transcript.write_text('{}\n', encoding='utf-8')
        code, _, err = self.call(['flush', '--hook-input', str(path)])
        self.assertEqual(code, 0, err)
        self.assertFalse(path.exists())

    def test_successful_flush_handles_input_already_removed(self):
        path = self.hook_input()
        def flush(*args, **kwargs):
            path.unlink()
            return 0
        with patch('respectedbrain.memory.flush.flush_transcript', side_effect=flush):
            code, _, err = self.call(['flush', '--hook-input', str(path)])
        self.assertEqual(code, 0, err)

    def test_maintenance_accepts_dispatch_argument_separator(self):
        code, out, err = self.call(['maintenance', 'vault_linter', '--', '--json'])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['vault_root'], str(self.ctx.paths.vault_root))

    def test_architect_output_and_abbreviation_obey_writer_admission(self):
        for option in ('--output', '--output=', '--out'):
            with self.subTest(option=option):
                target = self.ctx.paths.vault_root / 'architecture.md'
                args = [option + str(target)] if option.endswith('=') else [option, str(target)]
                with exclusive_lock(self.ctx.paths.data_root / '.operation.lock', timeout=0):
                    code, _, _ = self.call(['maintenance', 'architect_scan', '--path', str(self.project), *args])
                self.assertEqual(code, 1)
                self.assertFalse(target.exists())

    def test_abbreviated_dash_fix_obeys_writer_admission(self):
        note = self.ctx.paths.vault_root / 'a—b.md'
        note.write_bytes(b'human')
        with exclusive_lock(self.ctx.paths.data_root / '.operation.lock', timeout=0):
            code, _, _ = self.call(['maintenance', 'vault_linter', '--fix-d'])
        self.assertEqual(code, 1)
        self.assertTrue(note.exists())

    def test_architect_read_is_allowed_during_activation_and_output_is_atomic(self):
        (self.project / 'main.py').write_bytes(b'print(1)')
        with exclusive_lock(self.ctx.paths.data_root / '.operation.lock', timeout=0):
            code, out, err = self.call(['maintenance', 'architect_scan', '--path', str(self.project), '--json'])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['entry_points'], ['main.py'])
        target = self.ctx.paths.vault_root / 'architecture.md'
        code, _, err = self.call(['maintenance', 'architect_scan', '--path', str(self.project), '--out', str(target)])
        self.assertEqual(code, 0, err)
        self.assertIn('main.py', target.read_text(encoding='utf-8'))
        self.assertFalse(list(target.parent.glob('.architecture.md-*.tmp')))

    def run_record(self, **extra):
        directory = self.ctx.paths.state_dir / 'orchestration' / 'run-fixture'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'metadata.json').write_text(json.dumps(dict(run_id='run-fixture', vault_id=self.ctx.paths.vault_id, **extra)), encoding='utf-8')
        return directory

    def test_listing_rejects_malformed_result_and_worktree_field(self):
        directory = self.run_record()
        (directory / 'result.json').write_text('[]', encoding='utf-8')
        self.assertEqual(runner.list_runs(self.ctx)['runs'], [])
        (directory / 'result.json').unlink()
        self.run_record(worktree_path=['invalid'])
        self.assertEqual(runner.list_runs(self.ctx)['runs'], [])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction fixture')
    def test_listing_refuses_linked_evidence_even_when_it_is_not_a_file(self):
        directory = self.run_record()
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'human.txt'
        sentinel.write_bytes(b'human')
        for name in ('worker.patch', 'result.json'):
            link = directory / name
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True, check=True)
            try:
                self.assertEqual(runner.list_runs(self.ctx)['runs'], [])
                self.assertEqual(sentinel.read_bytes(), b'human')
            finally:
                os.rmdir(link)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction fixture')
    def test_history_discovery_prunes_provider_junctions(self):
        home = self.root / 'home'
        roots = {
            'claude': home / '.claude',
            'codex': home / '.codex' / 'sessions',
            'antigravity': home / '.gemini' / 'antigravity-ide' / 'brain',
        }
        outside = self.root / 'outside-logs'
        (outside / '.system_generated' / 'logs').mkdir(parents=True)
        (outside / 'session-fixture.jsonl').write_text('{}', encoding='utf-8')
        (outside / '.system_generated' / 'logs' / 'transcript.jsonl').write_text('{}', encoding='utf-8')
        miner = AgentHistoryMiner(self.ctx.paths.vault_root, state_file=self.ctx.paths.state_dir / 'history.json')
        for provider, root in roots.items():
            root.mkdir(parents=True)
            link = root / 'linked'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], check=True, capture_output=True)
            try:
                with patch.object(Path, 'home', return_value=home):
                    sessions = getattr(miner, 'discover_' + provider + '_sessions')()
                self.assertEqual(sessions, [], provider)
            finally:
                os.rmdir(link)

    def test_history_discovery_keeps_real_nested_provider_logs(self):
        home = self.root / 'home'
        paths = {
            'claude': home/'.claude'/'projects'/'fixture'/'session-fixture.jsonl',
            'codex': home/'.codex'/'sessions'/'2026'/'10'/'06'/'rollout-fixture.jsonl',
            'antigravity': home/'.gemini'/'antigravity-ide'/'brain'/'conversation' / '.system_generated'/'logs'/'transcript.jsonl',
        }
        miner = AgentHistoryMiner(self.ctx.paths.vault_root, state_file=self.ctx.paths.state_dir/'history.json')
        for provider, path in paths.items():
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{}')
            with patch.object(Path, 'home', return_value=home):
                sessions = getattr(miner, 'discover_' + provider + '_sessions')()
            self.assertEqual([item['path'] for item in sessions], [path], provider)


class BootstrapReviewTest(unittest.TestCase):
    def test_frozen_launch_uses_executable_root_and_explicit_data(self):
        module = importlib.import_module('respectedbrain.bootstrap')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / 'home'
            home.mkdir()
            cases = [('win32', root/'app'/'respectedbrain.exe', root/'app'),
                     ('darwin', root/'RespectedBrain.app'/'Contents'/'MacOS'/'respectedbrain', root/'RespectedBrain.app'),
                     ('linux', root/'app'/'respectedbrain', root/'app')]
            for platform, executable, expected in cases:
                with self.subTest(platform=platform), patch.object(module.sys, 'frozen', True, create=True), patch.object(module.sys, 'platform', platform), patch.object(module.sys, 'executable', str(executable)), patch.object(Path, 'home', return_value=home), patch.object(module, 'known_folder', return_value=home/'Documents'):
                    roots = module.application_roots(env={'RESPECTED_DATA_DIR': str(root/'data')})
                    self.assertEqual(roots.app_root, expected)
                    self.assertEqual(roots.data_root, root/'data')
                    self.assertEqual(module.launcher_argv(), (str(executable),))
            self.assertEqual(snapshot(root), {'home': 'directory'})

