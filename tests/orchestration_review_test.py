"""Worker policy, scope and patch fidelity in temporary Git repositories."""
from pathlib import Path
from types import SimpleNamespace
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from respectedbrain.orchestration import runner, antigravity_orchestrator as agy
from tests import any_to_any_orchestrator_test as runner_support
from tests import antigravity_orchestrator_test as agy_support


class OrchestrationReviewTest(unittest.TestCase):
    def setUp(self):
        runner_support.AnyToAnyOrchestratorTest.setUp(self)
        # Compare exact fixture bytes independently of host Git newline policy.
        self.git(self.repo, 'config', 'core.autocrlf', 'false')
        (self.repo / 'README.md').write_bytes(self.git(self.repo, 'show', 'HEAD:README.md').stdout)
    tearDown = runner_support.AnyToAnyOrchestratorTest.tearDown

    @unittest.skipUnless(os.name == 'nt', 'Windows junction fixture')
    def test_run_rejection_refuses_junction_in_state_ancestors(self):
        root = Path(self.temp_dir.name).resolve()
        ctx = agy_support.context_for(root)
        outside = root / 'outside'
        directory = outside / 'run-owned'
        directory.mkdir(parents=True)
        sentinel = directory / 'human.txt'
        sentinel.write_bytes(b'human')
        (directory / 'metadata.json').write_text(json.dumps(dict(run_id='run-owned', vault_id=ctx.paths.vault_id)), encoding='utf-8')
        link = ctx.paths.state_dir / 'orchestration'
        link.parent.mkdir(parents=True)
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], check=True, capture_output=True)
        try:
            with self.assertRaises(ValueError):
                runner.reject_run(ctx, 'run-owned')
            self.assertEqual(sentinel.read_bytes(), b'human')
        finally:
            os.rmdir(link)

    def test_failed_acceptance_returns_nonzero_cli_result(self):
        run = runner.OrchestrationRun('fixture', 'user', 'codex', self.repo, Path(self.temp_dir.name)/'state', test_command='fixture-test')
        run.run_dir.mkdir(parents=True)
        run.worktree_dir.mkdir(parents=True)
        def process(command, **options):
            return subprocess.CompletedProcess(command, 1 if isinstance(command, str) else 0, stdout='', stderr='')
        with patch.object(runner, 'get_cli_command', return_value=['fixture-cli']), patch.object(runner.subprocess, 'run', side_effect=process), patch.object(run, 'collect_patch'), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = run.execute_worker()
        self.assertNotEqual(code, 0)

    def run_fixture(self):
        run = runner.OrchestrationRun('fixture task', 'user', 'user', self.repo, Path(self.temp_dir.name) / 'state')
        self.assertTrue(run.setup_worktree())
        return run

    def git(self, root, *args):
        return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)

    def test_run_identity_does_not_collide_for_same_task_in_same_second(self):
        with patch.object(runner.dt, 'datetime') as clock:
            clock.now.return_value.strftime.return_value = '20261006-120000'
            first = runner.OrchestrationRun('same', 'user', 'user', self.repo, self.repo / 'state')
            second = runner.OrchestrationRun('same', 'user', 'user', self.repo, self.repo / 'state')
        self.assertNotEqual(first.run_id, second.run_id)

    def test_patch_contains_committed_unstaged_and_new_binary_files(self):
        run = self.run_fixture()
        readme = run.worktree_dir / 'README.md'
        readme.write_bytes(b'committed edit\n')
        self.git(run.worktree_dir, 'add', 'README.md')
        self.git(run.worktree_dir, 'commit', '-m', 'fixture worker edit')
        readme.write_bytes(b'committed edit\nunstaged edit\n')
        (run.worktree_dir / 'new.bin').write_bytes(bytes(range(256)))
        with contextlib.redirect_stdout(io.StringIO()):
            run.collect_patch(exit_code=0, test_passed=True, duration=0)
        patch_file = run.run_dir / 'worker.patch'
        self.git(self.repo, 'apply', '--check', '--binary', str(patch_file))
        self.git(self.repo, 'apply', '--binary', str(patch_file))
        self.assertEqual((self.repo / 'README.md').read_bytes(), readme.read_bytes())
        self.assertEqual((self.repo / 'new.bin').read_bytes(), bytes(range(256)))

    def test_worker_task_spec_does_not_destroy_repository_owned_note(self):
        original = b'human task documentation\n'
        (self.repo / 'TASK_SPEC.md').write_bytes(original)
        self.git(self.repo, 'add', 'TASK_SPEC.md')
        self.git(self.repo, 'commit', '-m', 'fixture documentation')
        run = self.run_fixture()
        self.assertEqual((run.worktree_dir / 'TASK_SPEC.md').read_bytes(), original)
        with contextlib.redirect_stdout(io.StringIO()):
            run.collect_patch(exit_code=0, test_passed=True, duration=0)
        self.assertEqual((run.worktree_dir / 'TASK_SPEC.md').read_bytes(), original)

    def test_permission_policy_false_omits_skip_flag(self):
        root = Path(self.temp_dir.name).resolve()
        request, lane = agy_support.WorkerInvocationTest().make_worker(agy, root)
        process = SimpleNamespace(pid=123, returncode=0, communicate=lambda **options: ('{"status":"ok"}', ''))
        with patch.object(agy.subprocess, 'Popen', return_value=process) as spawn:
            result = agy.run_worker(request, lane, root / 'fake-agy', dangerously_skip_permissions=False)
        self.assertEqual(result.status, agy.RunStatus.COMPLETE)
        self.assertNotIn('--dangerously-skip-permissions', spawn.call_args.args[0])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction fixture')
    def test_change_scope_rejects_junction_ancestor_of_tracked_file(self):
        root = Path(self.temp_dir.name).resolve()
        owned = self.repo / 'owned'
        owned.mkdir()
        (owned / 'file.txt').write_bytes(b'base')
        self.git(self.repo, 'add', 'owned/file.txt')
        self.git(self.repo, 'commit', '-m', 'fixture tracked file')
        baseline = self.git(self.repo, 'rev-parse', 'HEAD').stdout.decode().strip()
        outside = root / 'outside-files'
        outside.mkdir()
        (outside / 'file.txt').write_bytes(b'external')
        os.rename(owned, root / 'saved-owned')
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(owned), str(outside)], check=True, capture_output=True)
        try:
            lane = agy.Lane(self.repo, self.repo, 'fixture', root/'run', baseline)
            changes = agy.collect_worker_changes(lane)
            self.assertIn('owned/file.txt', changes.unsafe_paths)
        finally:
            os.rmdir(owned)

    def test_acceptance_cannot_expand_worker_scope_after_initial_check(self):
        root = Path(self.temp_dir.name).resolve()
        ctx = agy_support.context_for(root)
        (self.repo / 'owned.txt').write_bytes(b'base')
        self.git(self.repo, 'add', 'owned.txt')
        self.git(self.repo, 'commit', '-m', 'fixture owned')
        policy = self.repo / 'policy.json'
        policy.write_text(json.dumps(dict(schema_version=1, worker_executable_candidates=['fake'], workspace_root='.worktrees', max_active_write_workers=1, read_timeout_seconds=10, write_timeout_seconds=10, dangerously_skip_permissions=False)), encoding='utf-8')
        args = agy._build_parser().parse_args(['run-write', '--repo-root', str(self.repo), '--policy', str(policy), '--run-id', 'fixture-scope', '--slug', 'scope', '--objective', 'fixture', '--owner', 'owned.txt'])
        args.ctx, args.state_root = ctx, ctx.paths.state_dir / 'orchestration'
        def worker(*items, **options):
            lane = items[1]
            (lane.worktree / 'owned.txt').write_bytes(b'worker')
            return SimpleNamespace(status=agy.RunStatus.COMPLETE)
        def acceptance(lane, *items, **options):
            (lane.worktree / 'outside.txt').write_bytes(b'acceptance side effect')
            return ()
        with patch.object(agy, 'resolve_agy', return_value=root / 'fake-agy'), patch.object(agy, 'run_worker', side_effect=worker), patch.object(agy, 'run_acceptance', side_effect=acceptance), contextlib.redirect_stdout(io.StringIO()):
            code = agy._run_cli(args)
        self.assertEqual(code, 21)
        evidence = json.loads((args.state_root / args.run_id / 'verification.json').read_text())
        self.assertEqual(evidence['status'], 'SCOPE_VIOLATION')
