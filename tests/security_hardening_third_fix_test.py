'''Third-review security regressions.'''
from __future__ import annotations
import base64, hashlib, json, os, socket, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest import mock
from respectedbrain.core.context import AppContext, AppPaths
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.installation.payload import validate_package
from respectedbrain.installation.provenance import TrustedProvenancePolicy, verify_release_provenance
from respectedbrain.maintenance.ingestion.defuddle import _DeadlineReader, safe_fetch_url
from respectedbrain.providers.runner import Invocation, _run_process_tree, run_model
from tests.foundation_install_support import seed_package

def _bundle(name, sha):
    statement = {'_type':'https://in-toto.io/Statement/v1','subject':[{'name':name,'digest':{'sha256':sha}}],
      'predicateType':'https://slsa.dev/provenance/v1','predicate':{'buildDefinition':{'externalParameters':{'workflow':{
      'repository':'https://github.com/respected0/respectedbrain','path':'.github/workflows/release.yml','ref':'refs/tags/v0.0.1'}}}}}
    return {'mediaType':'application/vnd.dev.sigstore.bundle+json;version=0.2','dsseEnvelope':{
      'payload':base64.b64encode(json.dumps(statement).encode()).decode(),'payloadType':'application/vnd.in-toto+json',
      'signatures':[{'sig':'synthetic'}]}}

class ProviderIsolationTest(unittest.TestCase):
    def test_custom_child_is_rejected_before_process_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root/'vault'; vault.mkdir(); nested = vault/'nested'; nested.mkdir()
            outside = root/'outside'; outside.mkdir(); existing = root/'human.md'; existing.write_text('human content')
            ctx = AppContext(AppPaths(root/'app',root/'data',vault,'00000000-0000-0000-0000-000000000001'),{},ResourceCatalog())
            for target in (existing,nested/'inside.md',outside/'outside.md'):
                script = f'from pathlib import Path;Path({str(target)!r}).write_text(\'changed\');print(\'ok\')'
                command = subprocess.list2cmdline([sys.executable,'-c',script])
                with mock.patch.dict(os.environ,{'BEYIN_LLM_COMMAND':command}), mock.patch('respectedbrain.providers.runner._run_process_tree') as call:
                    output, error, provider = run_model('prompt',vault,'text',5,ctx=ctx)
                self.assertIsNone(output); self.assertEqual(error,'custom-isolation-required'); self.assertEqual(provider,'custom'); call.assert_not_called()
            self.assertEqual(existing.read_text(),'human content')
            self.assertFalse((nested/'inside.md').exists()); self.assertFalse((outside/'outside.md').exists())

class ProvenanceTest(unittest.TestCase):
    def test_gh_binds_identity_issuer_and_exact_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); package = root/'distribution.json'; package.write_bytes(b'manifest')
            bundle = root/'distribution.json.attestation.json'
            bundle.write_text(json.dumps(_bundle(package.name,hashlib.sha256(package.read_bytes()).hexdigest())))
            policy = TrustedProvenancePolicy(expected_ref='refs/tags/v0.0.1')
            verifier_results = [mock.Mock(returncode=0,stdout='gh version 2.102.0',stderr=''),mock.Mock(returncode=0,stdout='[{}]',stderr='')]
            with mock.patch('shutil.which',return_value='C:/tools/gh.exe'), mock.patch('subprocess.run',side_effect=verifier_results) as call:
                ok, reason, _ = verify_release_provenance(package,bundle,policy=policy)
            self.assertTrue(ok,reason); argv = call.call_args_list[-1].args[0]
            self.assertIn('--cert-oidc-issuer',argv); self.assertNotIn('--cert-identity-issuer',argv)
            self.assertNotIn('--signer-workflow',argv)
            self.assertEqual(argv[argv.index('--source-ref')+1],'refs/tags/v0.0.1')
            self.assertEqual(argv[argv.index('--cert-identity')+1],'https://github.com/respected0/respectedbrain/.github/workflows/release.yml@refs/tags/v0.0.1')

    def test_jsonl_bundle_and_unsigned_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); package = root/'distribution.json'; package.write_bytes(b'manifest'); bundle = root/'a.jsonl'
            bundle.write_text(json.dumps(_bundle(package.name,hashlib.sha256(package.read_bytes()).hexdigest()))+'\n')
            policy = TrustedProvenancePolicy(expected_ref='refs/tags/v0.0.1',verifier_callable=lambda *_:(True,'fixture'))
            self.assertTrue(verify_release_provenance(package,bundle,policy=policy)[0])
            with mock.patch.dict(os.environ,{'RESPECTED_ALLOW_UNSIGNED':'1'}):
                with self.assertRaisesRegex(Exception,'provenance'): validate_package(seed_package(root/'unsigned'))

class HttpDeadlineTest(unittest.TestCase):
    def test_status_and_chunk_lines_stop_near_deadline(self):
        for prefix in (
            b'HTTP/1.1 2',
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1',
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nA\r\n0\r\nX',
        ):
            with self.subTest(prefix=prefix):
                server, client = socket.socketpair(); stop = threading.Event()
                def serve():
                    try:
                        server.sendall(prefix)
                        while not stop.wait(.01): server.sendall(b' ')
                    except OSError: pass
                    finally: server.close()
                threading.Thread(target=serve,daemon=True).start(); started = time.monotonic()
                addresses = [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',80))]
                outcomes = []
                def fetch():
                    with mock.patch('socket.create_connection',return_value=client), mock.patch('socket.getaddrinfo',return_value=addresses):
                        outcomes.append(safe_fetch_url('http://example.test/x',timeout=.05))
                worker = threading.Thread(target=fetch,daemon=True); worker.start(); worker.join(.25)
                completed = not worker.is_alive(); stop.set(); client.close(); worker.join(.25)
                self.assertTrue(completed,'transport exceeded watchdog after stale socket timeout renewal')
                ok, result, _ = outcomes[0]; elapsed = time.monotonic()-started
                self.assertFalse(ok); self.assertLessEqual(elapsed,.12,result)

    def test_underlying_completion_after_deadline_is_rejected(self):
        class SlowStream:
            def readinto(self, buffer):
                time.sleep(0.04)
                buffer[0] = 1
                return 1
        reader = _DeadlineReader(SlowStream(), time.monotonic() + 0.01)
        with self.assertRaises(TimeoutError):
            reader.readinto(bytearray(1))

class ResolverCapacityTest(unittest.TestCase):
    def test_bounded_daemon_workers(self):
        release = threading.Event()
        def block(*args,**kwargs):
            release.wait(2); return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',80))]
        with mock.patch('socket.getaddrinfo',side_effect=block):
            threads = [threading.Thread(target=lambda i=i:safe_fetch_url(f'http://h{i}.example.test/',timeout=.12),daemon=True) for i in range(5)]
            for thread in threads: thread.start()
            time.sleep(.08); workers = [item for item in threading.enumerate() if item.name.startswith('respectedbrain-resolver')]
            self.assertEqual(len(workers),2); release.set()
            for thread in threads: thread.join(1)

    def test_slow_resolver_does_not_block_process_shutdown(self):
        code = (
            "import socket,sys,threading,time\n"
            "entered=threading.Event()\n"
            "def blocked(*args,**kwargs):\n"
            "    entered.set();time.sleep(5);return []\n"
            "socket.getaddrinfo=blocked\n"
            "from respectedbrain.maintenance.ingestion.defuddle import safe_fetch_url\n"
            "threading.Thread(target=lambda:safe_fetch_url('http://slow.example.test/',timeout=.05),daemon=True).start()\n"
            "assert entered.wait(5),'resolver did not start'\n"
            "print('resolver-blocked',flush=True)\n"
            "sys.stdin.readline()\n"
            "sys.exit(0)\n"
        )
        process = subprocess.Popen([sys.executable, "-c", code], cwd=Path.cwd(),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready = []
            reader = threading.Thread(target=lambda: ready.append(process.stdout.readline()), daemon=True)
            reader.start()
            reader.join(10)
            self.assertFalse(reader.is_alive(), 'resolver readiness timed out')
            self.assertEqual(ready, ['resolver-blocked\n'])
            # Measure exit with DNS blocked; interpreter/import startup is outside this contract.
            started = time.monotonic()
            output, errors = process.communicate(input='\n', timeout=2)
            self.assertEqual(process.returncode, 0, errors)
            self.assertLess(time.monotonic() - started, 1.5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def test_nonzero_exit_is_returned_without_hiding_output(self):
        invocation = Invocation(
            [sys.executable, "-c", "import sys;print('partial');sys.stderr.write('failed');raise SystemExit(7)"],
            None,
        )
        result = _run_process_tree(invocation, cwd=Path.cwd(), env=os.environ.copy(), timeout=1)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout.strip(), "partial")
        self.assertEqual(result.stderr.strip(), "failed")

    def test_timeout_contains_detached_descendant_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child_pid_file = root / "child.pid"
            parent_script = root / "spawn_detached.py"
            parent_script.write_text(
                "import subprocess,sys,time\n"
                "from pathlib import Path\n"
                "flags=(subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS) if hasattr(subprocess,'DETACHED_PROCESS') else 0\n"
                "kwargs={'creationflags':flags} if flags else {'start_new_session':True}\n"
                "child=subprocess.Popen([sys.executable,'-c','import time\\nwhile True: time.sleep(.05)'],**kwargs)\n"
                "Path(sys.argv[1]).write_text(str(child.pid),encoding='ascii')\n"
                "time.sleep(5)\n",
                encoding="utf-8",
            )
            invocation = Invocation(
                [sys.executable, str(parent_script), str(child_pid_file)],
                None,
                windows_executable=os.name == "nt",
            )
            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                _run_process_tree(invocation, cwd=root, env=os.environ.copy(), timeout=1.0)
            self.assertLess(time.monotonic() - started, 2.0)
            self.assertTrue(child_pid_file.is_file())
            child_pid = int(child_pid_file.read_text(encoding="ascii"))
            deadline = time.monotonic() + 0.8
            while time.monotonic() < deadline and self._process_alive(child_pid):
                time.sleep(0.02)
            self.assertFalse(self._process_alive(child_pid), f"detached child survived: {child_pid}")

    @staticmethod
    def _process_alive(pid: int) -> bool:
        if os.name == "nt":
            import ctypes
            process = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
            if not process:
                return False
            try:
                return ctypes.windll.kernel32.WaitForSingleObject(process, 0) == 258
            finally:
                ctypes.windll.kernel32.CloseHandle(process)
        try:
            status = Path("/proc") / str(pid) / "stat"
            if status.is_file():
                fields = status.read_text(encoding="utf-8", errors="replace").rsplit(")", 1)[-1].split()
                return bool(fields) and fields[0] != "Z"
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

if __name__ == '__main__': unittest.main()
