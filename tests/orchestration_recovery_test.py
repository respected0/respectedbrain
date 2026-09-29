"""Regressions for low-cost, durable orchestration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from antigravity_orchestrator_test import load_orchestrator


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
            command = [sys.executable, '-c', 'import time,pathlib; time.sleep(1); pathlib.Path(' + repr(str(done)) + ').write_text("ok")']
            source = ('import sys; sys.path.insert(0, ' + repr(str(Path(m.__file__).parent)) + '); '
                      'import antigravity_orchestrator as m; from pathlib import Path; '
                      'm._spawn_detached(' + repr(command) + ', Path(' + repr(str(root)) + '), Path(' + repr(str(root / 'log')) + '))')
            parent = subprocess.run([sys.executable, '-c', source], capture_output=True, timeout=10)
            self.assertEqual(parent.returncode, 0, parent.stderr.decode('utf-8', errors='replace'))
            import time
            deadline = time.monotonic() + 5
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual(done.read_text(), 'ok')


if __name__ == '__main__':
    unittest.main()
