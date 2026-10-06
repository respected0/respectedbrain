"""HTTP control plane uses config and selected UUID services."""
import json
import http.client
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.parse import quote

from tests.foundation_support import make_context, snapshot
from respectedbrain.gateway.server import create_server
from respectedbrain.core.config import ConfigStore
from unittest import mock


class GatewayBoundaryTest(unittest.TestCase):
    def test_reindex_reports_numeric_counts(self):
        with mock.patch('respectedbrain.gateway.server.SearchEngine') as engine:
            engine.return_value.index_vault.return_value = {'indexed': 2, 'skipped': 3, 'deleted': 1}
            reply = self.request('/api/actions/reindex', b'{}')[2]
        self.assertEqual(reply['indexed'], 2)
        self.assertEqual(reply['skipped'], 3)
        self.assertIn('5 not tarandı', reply['message'])

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows junction boundary')
    def test_gateway_cannot_read_junction_notes_memory_or_state(self):
        import os
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory() as outside_name:
            outside = Path(outside_name)
            (outside / 'Secret.md').write_text('outside-secret', encoding='utf-8')
            (outside / 'Last-Session.md').write_text('outside-secret', encoding='utf-8')
            (outside / 'health.json').write_text('{"error":"outside-secret"}', encoding='utf-8')
            links = [self.ctx.paths.vault_root / 'escape', self.ctx.paths.vault_root / '🔮 850-Companion', self.ctx.paths.state_dir]
            self.ctx.paths.state_dir.parent.mkdir(parents=True, exist_ok=True)
            if self.ctx.paths.state_dir.exists():
                shutil.rmtree(self.ctx.paths.state_dir)
            try:
                for link in links:
                    subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], check=True, capture_output=True)
                self.assertEqual(self.request('/api/note?path=escape/Secret.md')[0], 403)
                self.assertNotIn('outside-secret', json.dumps(self.request('/api/memory')[2]))
                self.assertEqual(self.request('/api/health')[2]['engine_health'], {})
            finally:
                for link in links:
                    if link.exists():
                        os.rmdir(link)

    def test_missing_health_is_unknown_and_wrong_json_types_are_ignored(self):
        health = self.ctx.paths.state_dir / 'health.json'
        health.parent.mkdir(parents=True, exist_ok=True)
        health.write_text('[]', encoding='utf-8')
        self.assertEqual(self.request('/api/actions/doctor', b'{}')[2]['report']['status'], 'unknown')

    def test_busy_writer_returns_service_unavailable(self):
        from respectedbrain.core.errors import BusyError
        with mock.patch('respectedbrain.gateway.server.DashboardHandler._handle_quick_capture', side_effect=BusyError('busy')):
            self.assertEqual(self.request('/api/actions/capture', b'{}')[0], 503)

    def test_update_ui_handles_unavailable_response(self):
        import shutil
        import subprocess
        executable = shutil.which('node')
        if not executable:
            self.skipTest('Node unavailable for dashboard JavaScript verification')
        source = (Path(__file__).resolve().parents[1] / 'src/respectedbrain/resources/gateway/web/index.html').read_text(encoding='utf-8')
        function = source.split('    async function checkUpdates() {', 1)[1].split('    function escapeHtml', 1)[0]
        script = "const messages=[]; const logTerminal=()=>{}; const showToast=(message)=>messages.push(message); const fetch=async()=>({json:async()=>({current_version:'1',status:'unavailable',update_available:null})}); async function checkUpdates(){" + function + "checkUpdates().then(()=>{if(!messages[0].includes('Güncelleme bilgisi alınamadı'))process.exit(1);});"
        result = subprocess.run([executable, '-e', script], capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = make_context(Path(self.temp.name))
        self.server = create_server(self.ctx, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(5)

    def request(self, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('POST' if body is not None else 'GET', path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            connection.close()

    def test_foreign_origin_and_rebinding_host_are_rejected_without_write(self):
        before = ConfigStore(self.ctx.paths.data_root).read()
        status, headers, _ = self.request('/api/status', headers={'Origin': 'https://example.org'})
        self.assertEqual(status, 403)
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        status, _, _ = self.request('/api/models/priority', b'{"summary_provider":"claude"}', {'Host': 'attacker.example'})
        self.assertEqual(status, 403)
        self.assertEqual(ConfigStore(self.ctx.paths.data_root).read(), before)
        local = f'http://127.0.0.1:{self.server.server_port}'
        self.assertEqual(self.request('/api/status', headers={'Origin': local})[0], 200)

    def test_malformed_requests_return_errors_and_server_survives(self):
        for body, headers, expected in [(b'[]', {}, 400), (b'\xff', {}, 400),
                                        (b'{}', {'Content-Length': '-1'}, 400),
                                        (b'{}', {'Content-Length': 'invalid'}, 400),
                                        (b'{}', {'Content-Length': '999999999'}, 413)]:
            with self.subTest(body=body, headers=headers):
                self.assertEqual(self.request('/api/actions/capture', body, headers)[0], expected)
        self.assertEqual(self.request('/api/search?limit=broken')[0], 400)
        self.assertEqual(self.request('/api/actions/capture', b'{"title":[],"content":"test"}')[0], 400)
        self.assertEqual(self.request('/api/status')[0], 200)

    def test_note_paths_are_rejected_instead_of_rewritten(self):
        (self.ctx.paths.vault_root / 'secret.md').write_text('secret', encoding='utf-8')
        for path in ('../secret.md', '/secret.md', 'C:secret.md'):
            self.assertEqual(self.request('/api/note?path=' + quote(path))[0], 403)

    def test_capture_does_not_overwrite_and_reports_index_failure(self):
        body = json.dumps({'title': 'quoted "title"', 'content': 'first', 'tags': ['a\nb']}).encode()
        with mock.patch('respectedbrain.gateway.server.SearchEngine') as engine:
            engine.return_value.index_vault.side_effect = OSError('index failed')
            _, _, first = self.request('/api/actions/capture', body)
            _, _, second = self.request('/api/actions/capture', body)
        self.assertTrue(first['success'])
        self.assertFalse(first['indexed'])
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(len(list((self.ctx.paths.vault_root / '📥 000-Inbox/Dump').glob('*.md'))), 2)

    def test_updater_placeholder_cannot_claim_verified_freshness(self):
        reply = self.request('/api/updater/check')[2]
        self.assertEqual(reply['status'], 'unavailable')
        self.assertIsNone(reply['latest_version'])


class FoundationServicesTest(unittest.TestCase):
    def test_gateway_config_is_user_config_even_without_legacy_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ctx = make_context(root)
            ConfigStore(ctx.paths.data_root).update(lambda value: value.update(custom=7, preferences={"summary_provider": "codex"}))
            before_app = snapshot(ctx.paths.app_root)
            server = create_server(ctx, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/status", timeout=5) as reply:
                    self.assertEqual(json.load(reply)["summary_provider"], "codex")
                request = Request(base + "/api/models/priority", data=json.dumps({"summary_provider": "claude"}).encode(), headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=5) as reply:
                    self.assertTrue(json.load(reply)["success"])
                with urlopen(base + "/", timeout=5) as reply:
                    self.assertIn(b"<html", reply.read().lower())
                config = ConfigStore(ctx.paths.data_root).read()
                self.assertEqual(config["preferences"]["summary_provider"], "claude")
                self.assertEqual(config["custom"], 7)
                self.assertFalse(config["integrations"]["schedule"])
                self.assertFalse((ctx.paths.vault_root / ".beyin").exists())
                self.assertEqual(snapshot(ctx.paths.app_root), before_app)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(5)
