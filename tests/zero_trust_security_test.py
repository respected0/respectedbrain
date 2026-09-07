#!/usr/bin/env python3
"""Zero-Trust Red Team Security & Boundary Tests for Respected Brain."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import sys
ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SYS_PATH = list(sys.path)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def tearDownModule():
    sys.path[:] = ORIGINAL_SYS_PATH

from scripts.url_safety import validate_safe_url, is_safe_url
from scripts.publish_git_snapshot import publish_if_due
from scripts.vault_mcp_server import RespectedMcpServer
from scripts.mine_agent_history import AgentHistoryMiner
from scripts.smart_merge import smart_merge, dump_frontmatter
from scripts.tiling_check import check_tiling
from scripts.defuddle import clean_html, MAX_HTML_STRING_LEN


class ZeroTrustSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_root = Path(self.temp_dir.name)
        (self.vault_root / ".beyin").mkdir(parents=True, exist_ok=True)
        (self.vault_root / ".beyin" / "instructions.md").write_text("Test Instructions", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- 1. url_safety Tests ---
    def test_url_safety_nul_byte(self):
        safe, reason = validate_safe_url("http://example.com/\x00evil")
        self.assertFalse(safe)
        self.assertIn("NUL", reason)

    def test_url_safety_malformed_bracket(self):
        safe, reason = validate_safe_url("http://[::1/test")
        self.assertFalse(safe)

    def test_url_safety_fail_closed_unresolvable_when_required(self):
        # require_resolvable=True olduğunda var olmayan domain fail-closed reddedilmeli
        safe, reason = validate_safe_url("https://this-domain-definitely-does-not-exist-xyz12345.org", require_resolvable=True)
        self.assertFalse(safe)
        self.assertTrue(is_safe_url("https://github.com"))
        self.assertFalse(is_safe_url("https://this-domain-definitely-does-not-exist-xyz12345.org", require_resolvable=True))

    def test_url_safety_rejects_malicious_schemes_and_excessive_length(self):
        # Desteklenmeyen veya zararlı şemalar fail-closed reddedilmeli
        for bad_scheme in ("javascript:alert(1)", "data:text/html,<script>alert(1)</script>", "file:///etc/passwd"):
            safe, reason = validate_safe_url(bad_scheme)
            self.assertFalse(safe)
            self.assertTrue(len(reason) > 0)

        # Kullanıcı kimlik bilgisi içeren URL reddedilmeli
        safe, reason = validate_safe_url("http://user:pass@127.0.0.1/")
        self.assertFalse(safe)
        self.assertIn("kimlik", reason.lower())

        # Aşırı uzun URL
        huge_url = "https://example.com/" + ("a" * 5000)
        safe, reason = validate_safe_url(huge_url)
        self.assertFalse(safe)

    # --- 2. publish_git_snapshot Tests ---
    def test_publish_git_snapshot_unmocked_non_git_vault_halts_fail_closed(self):
        """Without any mocks, running publish_if_due on a non-git directory must halt fail-closed."""
        result = publish_if_due(self.vault_root, "origin", "main", apply=True)
        self.assertTrue(result["status"].startswith("halted:"))
        self.assertIn("fail-closed", result["detail"].lower())

    @patch("scripts.publish_git_snapshot._branch_divergence_status")
    @patch("scripts.publish_git_snapshot.check_secret_guard")
    def test_publish_git_snapshot_fail_closed_on_divergence_error(self, mock_guard, mock_div):
        mock_guard.return_value = (True, [])
        mock_div.return_value = "error"

        result = publish_if_due(self.vault_root, "origin", "main", apply=True)
        self.assertEqual(result["status"], "halted:error")
        self.assertIn("fail-closed", result["detail"])

    @patch("scripts.publish_git_snapshot._branch_divergence_status")
    @patch("scripts.publish_git_snapshot.check_secret_guard")
    def test_publish_git_snapshot_fail_closed_on_divergence_unknown(self, mock_guard, mock_div):
        mock_guard.return_value = (True, [])
        mock_div.return_value = "unknown"

        result = publish_if_due(self.vault_root, "origin", "main", apply=True)
        self.assertEqual(result["status"], "halted:unknown")
        self.assertIn("fail-closed", result["detail"])

    # --- 3. vault_mcp_server Tests ---
    def test_vault_mcp_server_safe_resolve_traversal_and_device(self):
        server = RespectedMcpServer(self.vault_root)

        # NUL byte
        self.assertIsNone(server._safe_resolve("notes/\x00secret.md"))
        # ADS (Alternate Data Stream)
        self.assertIsNone(server._safe_resolve("notes.md:stream"))
        # Windows DOS device
        self.assertIsNone(server._safe_resolve("CON.md"))
        self.assertIsNone(server._safe_resolve("sub/NUL.txt"))
        # Path traversal
        self.assertIsNone(server._safe_resolve("../../outside.txt"))

    def test_vault_mcp_server_note_size_ceiling(self):
        server = RespectedMcpServer(self.vault_root)
        huge_file = self.vault_root / "huge_note.md"
        # Test için sunucunun MAX_NOTE_BYTES tavanını geçici olarak küçültelim
        original_max = server.MAX_NOTE_BYTES
        server.MAX_NOTE_BYTES = 100
        try:
            huge_file.write_text("X" * 200, encoding="utf-8")
            res = server.call_tool("respected_get_note", {"path": "huge_note.md"})
            self.assertIn("çok büyük", res)
            self.assertIn("Güvenlik sınırı", res)
        finally:
            server.MAX_NOTE_BYTES = original_max

    # --- 4. mine_agent_history Tests ---
    def test_mine_agent_history_yaml_escaping(self):
        miner = AgentHistoryMiner(self.vault_root)
        import datetime as dt
        session_data = {
            "id": "sess-123",
            "agent": 'agent"with"quotes',
            "title": 'Test "Special" Title with : Colon and \\ Backslash',
            "mtime": dt.datetime.now(),
            "user_inputs": ['Test "Special" Title with : Colon and \\ Backslash'],
            "summaries": ["Karar 1"],
        }
        imported_path = miner.import_session(session_data, target_folder="daily")
        self.assertTrue(imported_path.is_file())
        text = imported_path.read_text(encoding="utf-8")
        self.assertIn('title: "Test \\"Special\\" Title with : Colon and \\\\ Backslash"', text)

    # --- 5. smart_merge Tests ---
    def test_smart_merge_heading_anchors_and_yaml(self):
        source = self.vault_root / "EskiNot.md"
        target = self.vault_root / "YeniNot.md"
        referring = self.vault_root / "Referans.md"

        source.write_text("---\ntitle: \"Eski: Not\"\ntags: [a]\n---\nEski gövde", encoding="utf-8")
        target.write_text("---\ntitle: Yeni Not\ntags: [b]\n---\nYeni gövde", encoding="utf-8")
        referring.write_text(
            "Bkz: [[EskiNot#Giris]] ve [[EskiNot#Detay|Detay Linki]] ayrıca [[EskiNot|Salt Alias]].",
            encoding="utf-8",
        )

        res = smart_merge(source, target, self.vault_root, dry_run=False)
        self.assertEqual(res["links_updated_count"], 1)

        ref_updated = referring.read_text(encoding="utf-8")
        self.assertIn("[[YeniNot#Giris]]", ref_updated)
        self.assertIn("[[YeniNot#Detay|Detay Linki]]", ref_updated)
        self.assertIn("[[YeniNot|Salt Alias]]", ref_updated)

    def test_dump_frontmatter_handles_colons_and_brackets(self):
        fm = {
            "title": "Proje: İkinci Beyin",
            "tags": ["etiket:1", "ikinci etiket"],
            "redirect": "[[HedefNot]]",
        }
        dumped = dump_frontmatter(fm)
        self.assertIn('title: "Proje: İkinci Beyin"', dumped)
        self.assertIn("redirect: [[HedefNot]]", dumped)

    # --- 6. tiling_check Tests ---
    def test_tiling_check_threshold_validation(self):
        with self.assertRaises(ValueError):
            check_tiling(self.vault_root, threshold=-0.1)
        with self.assertRaises(ValueError):
            check_tiling(self.vault_root, threshold=1.5)
        with self.assertRaises(ValueError):
            check_tiling(self.vault_root, threshold="not-a-number")  # type: ignore

    # --- 7. defuddle Tests ---
    def test_defuddle_html_length_cap(self):
        huge_html = "<html><body>" + "<p>Gövde</p>" * 1000 + "</body></html>"
        md = clean_html(huge_html)
        self.assertIn("Gövde", md)


if __name__ == "__main__":
    unittest.main()
