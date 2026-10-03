"""HTTP control plane uses config and selected UUID services."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from tests.foundation_support import make_context, snapshot
from respectedbrain.gateway.server import create_server
from respectedbrain.core.config import ConfigStore


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
