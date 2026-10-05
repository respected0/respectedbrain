"""Regressions for low-cost, durable orchestration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from tests.antigravity_orchestrator_test import load_orchestrator


def _wait_for_detached_completion(
    path: Path,
    expected: str,
    *,
    child_pid: int | None = None,
    is_alive_fn=None,
    timeout: float = 5.0,
    poll_interval: float = 0.05,
) -> bool:
    """Wait for detached output completion without racing an empty file open window."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        content_matches = False
        try:
            content_matches = path.is_file() and path.read_text(encoding="utf-8") == expected
        except OSError:
            content_matches = False

        pid_finished = True
        if os.name == "nt" and child_pid is not None and is_alive_fn is not None:
            pid_finished = not is_alive_fn(child_pid)

        if content_matches and pid_finished:
            return True
        time.sleep(poll_interval)
    return False


class RecoveryTest(unittest.TestCase):
    def test_success_prose_is_not_a_provider_error(self):
        m = load_orchestrator()
        for prose in ('quota risk', 'authentication required for other providers'):
            output = json.dumps({'status': 'SUCCESS', 'response': prose})
            self.assertEqual(m.classify_worker_exit(0, output, '', False), m.RunStatus.COMPLETE)

    def test_structured_error_is_still_classified(self):
        m = load_orchestrator()
        self.assertEqual(m.classify_worker_exit(0, json.dumps({'status': 'ERROR', 'error': 'quota exhausted'}), '', False), m.RunStatus.LIMIT_EXHAUSTED)

    def test_pid_probe_does_not_kill_process(self):
        m = load_orchestrator()
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
        try:
            self.assertTrue(m._pid_is_alive(process.pid))
            with self.assertRaises(subprocess.TimeoutExpired):
                process.wait(timeout=0.2)
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait()
        self.assertFalse(m._pid_is_alive(process.pid))

    def test_detached_process_finishes_after_parent_exits(self):
        m = load_orchestrator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            done = root / 'done'
            command = [sys.executable, '-c', 'import time,pathlib; time.sleep(1); pathlib.Path(' + repr(str(done)) + ').write_text("ok"); time.sleep(0.5)']
            source = ('from respectedbrain.orchestration import antigravity_orchestrator as m; from pathlib import Path; '
                      'print(m._spawn_detached(' + repr(command) + ', Path(' + repr(str(root)) + '), Path(' + repr(str(root / 'log')) + ')))')
            parent = subprocess.run([sys.executable, '-c', source], capture_output=True, timeout=10)
            self.assertEqual(parent.returncode, 0, parent.stderr.decode('utf-8', errors='replace'))
            child_pid = int(parent.stdout.strip())
            # On POSIX, checking only `done.exists()` unblocks as soon as open('w')
            # creates the 0-byte file before write()/close() completes. Wait until
            # the payload matches. On Windows, also wait for child process exit so
            # the inherited log handle is released before tempdir cleanup.
            completed = _wait_for_detached_completion(
                done, 'ok', child_pid=child_pid, is_alive_fn=m._pid_is_alive, timeout=5.0
            )
            self.assertTrue(completed, 'Detached process completion timed out')
            self.assertEqual(done.read_text(), 'ok')
            if os.name == 'nt':
                self.assertFalse(m._pid_is_alive(child_pid), 'Detached test child did not exit')

    def test_wait_for_detached_completion_survives_empty_file_window(self):
        with tempfile.TemporaryDirectory() as directory:
            done = Path(directory) / 'done'
            ready_event = threading.Event()
            write_event = threading.Event()

            def delayed_writer():
                with done.open('w', encoding='utf-8') as handle:
                    handle.flush()
                    ready_event.set()
                    write_event.wait(timeout=2.0)
                    handle.write('ok')

            thread = threading.Thread(target=delayed_writer)
            thread.start()
            try:
                self.assertTrue(ready_event.wait(timeout=2.0))
                # Confirm the file exists but has empty content during open('w') phase.
                self.assertTrue(done.exists())
                self.assertEqual(done.read_text(encoding='utf-8'), '')

                def release_writer():
                    time.sleep(0.1)
                    write_event.set()

                releaser = threading.Thread(target=release_writer)
                releaser.start()
                try:
                    completed = _wait_for_detached_completion(done, 'ok', timeout=2.0)
                    self.assertTrue(completed)
                    self.assertEqual(done.read_text(encoding='utf-8'), 'ok')
                finally:
                    releaser.join()
            finally:
                write_event.set()
                thread.join()

    def test_wait_for_detached_completion_times_out_on_unwritten_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            done = Path(directory) / 'done'
            done.touch()
            self.assertTrue(done.exists())
            self.assertEqual(done.read_text(encoding='utf-8'), '')
            # An unwritten empty file must not satisfy completion; it must time out.
            completed = _wait_for_detached_completion(done, 'ok', timeout=0.15, poll_interval=0.02)
            self.assertFalse(completed)

    def test_wait_for_detached_completion_times_out_on_partial_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            done = Path(directory) / 'done'
            done.write_text('partial', encoding='utf-8')
            completed = _wait_for_detached_completion(done, 'ok', timeout=0.15, poll_interval=0.02)
            self.assertFalse(completed)

    def test_wait_for_detached_completion_respects_pid_liveness_on_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            done = Path(directory) / 'done'
            done.write_text('ok', encoding='utf-8')
            alive_state = [True]

            def fake_is_alive(pid):
                return alive_state[0]

            if os.name == 'nt':
                self.assertFalse(
                    _wait_for_detached_completion(
                        done, 'ok', child_pid=12345, is_alive_fn=fake_is_alive, timeout=0.1, poll_interval=0.02
                    )
                )
                alive_state[0] = False
                self.assertTrue(
                    _wait_for_detached_completion(
                        done, 'ok', child_pid=12345, is_alive_fn=fake_is_alive, timeout=0.5, poll_interval=0.02
                    )
                )
            else:
                self.assertTrue(
                    _wait_for_detached_completion(
                        done, 'ok', child_pid=12345, is_alive_fn=fake_is_alive, timeout=0.5, poll_interval=0.02
                    )
                )


if __name__ == '__main__':
    unittest.main()
