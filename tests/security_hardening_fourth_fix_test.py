'''Fourth-review security and packaging regressions.'''
from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from respectedbrain.maintenance.backup.publish_git_snapshot import publish_if_due
import respectedbrain.maintenance.backup.publish_git_snapshot as snapshot_module
from respectedbrain.maintenance.ingestion.defuddle import safe_fetch_url
from tools.build_installer import build


class ImmutableSnapshotChainTest(unittest.TestCase):
    def setUp(self) -> None:
        if subprocess.run(['git', '--version'], capture_output=True).returncode != 0:
            self.skipTest('git is not available')

    def _git(self, repository: Path, *arguments: str) -> str:
        result = subprocess.run(
            ['git', *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _fixture(self, root: Path) -> tuple[Path, Path]:
        remote = root / 'remote.git'
        repository = root / 'vault'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
        subprocess.run(['git', 'init', '-b', 'main', str(repository)], check=True, capture_output=True)
        self._git(repository, 'config', 'user.name', 'Fixture')
        self._git(repository, 'config', 'user.email', 'fixture@example.invalid')
        self._git(repository, 'remote', 'add', 'origin', str(remote))
        (repository / 'note.md').write_text('first\n', encoding='utf-8')
        self._git(repository, 'add', 'note.md')
        self._git(repository, 'commit', '-m', 'baseline')
        self._git(repository, 'push', '-u', 'origin', 'main')
        return remote, repository

    def test_three_snapshots_form_fast_forward_chain_without_user_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, repository = self._fixture(root)
            receipt = root / 'receipt.json'
            commits: list[str] = []
            note = repository / 'note.md'

            for expected in ('first\n', 'second\n', 'third\n'):
                note.write_text(expected, encoding='utf-8')
                result = publish_if_due(
                    repository,
                    remote='origin',
                    branch='main',
                    apply=True,
                    min_interval_seconds=0,
                    receipt_file=receipt,
                )
                self.assertEqual('ok', result['status'], result)
                commits.append(result['commit'])
                self.assertEqual(expected.strip(), self._git(remote, 'show', f'main:{note.name}'))

            self.assertEqual(3, len(set(commits)))
            self.assertEqual(commits[0], self._git(remote, 'rev-parse', f'{commits[1]}^'))
            self.assertEqual(commits[1], self._git(remote, 'rev-parse', f'{commits[2]}^'))

    def test_user_head_progression_still_extends_snapshot_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, repository = self._fixture(root)
            receipt = root / 'receipt.json'
            first = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('ok', first['status'], first)

            (repository / 'user-commit.md').write_text('safe\n', encoding='utf-8')
            self._git(repository, 'add', 'user-commit.md')
            self._git(repository, 'commit', '-m', 'user work')
            second = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('ok', second['status'], second)
            self.assertEqual(first['commit'], self._git(remote, 'rev-parse', f'{second["commit"]}^'))
            self.assertEqual('safe', self._git(remote, 'show', f'main:user-commit.md'))

    def test_external_remote_change_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, repository = self._fixture(root)
            receipt = root / 'receipt.json'
            first = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('ok', first['status'], first)

            external = root / 'external'
            subprocess.run(['git', 'clone', str(remote), str(external)], check=True, capture_output=True)
            self._git(external, 'config', 'user.name', 'External')
            self._git(external, 'config', 'user.email', 'external@example.invalid')
            (external / 'external.md').write_text('external\n', encoding='utf-8')
            self._git(external, 'add', 'external.md')
            self._git(external, 'commit', '-m', 'external')
            external_commit = self._git(external, 'rev-parse', 'HEAD')
            self._git(external, 'push', 'origin', 'main')

            changed = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('halted:remote_changed', changed['status'], changed)
            self.assertEqual(external_commit, self._git(remote, 'rev-parse', 'main'))

    def test_process_restart_preserves_snapshot_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, repository = self._fixture(root)
            receipt = root / 'receipt.json'
            script = (
                'import json, sys\n'
                'from pathlib import Path\n'
                'from respectedbrain.maintenance.backup.publish_git_snapshot import publish_if_due\n'
                'result = publish_if_due(Path(sys.argv[1]), remote="origin", branch="main", apply=True, min_interval_seconds=0, receipt_file=Path(sys.argv[2]))\n'
                'print(json.dumps(result))\n'
            )
            commits = []
            note = repository / 'note.md'
            for content in ('first\n', 'second\n', 'third\n'):
                note.write_text(content, encoding='utf-8')
                process = subprocess.run(
                    [sys.executable, '-c', script, str(repository), str(receipt)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result = json.loads(process.stdout)
                self.assertEqual('ok', result['status'], result)
                commits.append(result['commit'])
            self.assertEqual(commits[0], self._git(remote, 'rev-parse', f'{commits[1]}^'))
            self.assertEqual(commits[1], self._git(remote, 'rev-parse', f'{commits[2]}^'))

    def test_unchanged_note_still_creates_fast_forward_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, repository = self._fixture(root)
            receipt = root / 'receipt.json'
            first = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('ok', first['status'], first)
            second = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('ok', second['status'], second)
            self.assertNotEqual(first['commit'], second['commit'])
            self.assertEqual(first['commit'], self._git(remote, 'rev-parse', f'{second["commit"]}^'))
            self.assertEqual('first', self._git(remote, 'show', 'main:note.md'))

    def test_push_failure_retry_extends_same_verified_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, repository = self._fixture(root)
            receipt = root / 'receipt.json'
            first = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('ok', first['status'], first)
            original_run = snapshot_module.subprocess.run
            failed_once = False

            def fail_push_once(command, **options):
                nonlocal failed_once
                if not failed_once and command[:2] == ['git', 'push']:
                    failed_once = True
                    return subprocess.CompletedProcess(command, 1, stdout='', stderr='simulated push failure')
                return original_run(command, **options)

            with mock.patch.object(snapshot_module.subprocess, 'run', side_effect=fail_push_once):
                failed = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('push-failed', failed['status'], failed)
            self.assertEqual(first['commit'], json.loads(receipt.read_text(encoding='utf-8'))['commit'])
            self.assertEqual(first['commit'], self._git(remote, 'rev-parse', 'main'))

            retried = publish_if_due(repository, remote='origin', branch='main', apply=True, min_interval_seconds=0, receipt_file=receipt)
            self.assertEqual('ok', retried['status'], retried)
            self.assertEqual(first['commit'], self._git(remote, 'rev-parse', f'{retried["commit"]}^'))


class LateByteHttpDeadlineTest(unittest.TestCase):
    def test_late_byte_then_idle_does_not_wait_for_stale_socket_timeout(self) -> None:
        prefixes = (
            b'HTTP/1.1 2',
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1',
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nA\r\n0\r\nX',
        )
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                server, client = socket.socketpair()
                stop = threading.Event()

                def serve() -> None:
                    try:
                        server.sendall(prefix)
                        if not stop.wait(0.06):
                            server.sendall(b' ')
                        stop.wait(0.25)
                    except OSError:
                        pass
                    finally:
                        server.close()

                thread = threading.Thread(target=serve, daemon=True)
                thread.start()
                started = time.monotonic()
                addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))]
                outcome: list[tuple[bool, object, dict]] = []

                def fetch() -> None:
                    with mock.patch('socket.create_connection', return_value=client), \
                         mock.patch('socket.getaddrinfo', return_value=addresses):
                        outcome.append(safe_fetch_url('http://example.test/x', timeout=0.1))

                worker = threading.Thread(target=fetch, daemon=True)
                worker.start()
                worker.join(0.25)
                completed = not worker.is_alive()
                elapsed = time.monotonic() - started
                stop.set()
                client.close()
                server.close()
                thread.join(0.25)
                self.assertTrue(completed, 'request exceeded its watchdog')
                self.assertFalse(outcome[0][0])
                self.assertLessEqual(elapsed, 0.15, outcome[0])


class FrozenGuiPackagingTest(unittest.TestCase):
    def test_pyinstaller_collects_tkinter_runtime(self) -> None:
        class BuildStopped(Exception):
            pass

        with mock.patch('subprocess.run', side_effect=BuildStopped()) as run:
            with self.assertRaises(BuildStopped):
                build(platform='windows' if sys.platform == 'win32' else 'linux', output=Path('unused'), installer=False)

        command = run.call_args.args[0]
        self.assertIn('--collect-all', command)
        self.assertEqual('tkinter', command[command.index('--collect-all') + 1])


if __name__ == '__main__':
    unittest.main()
