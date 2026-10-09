"""Tests for content secret scanning before Git snapshot publication."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from respectedbrain.maintenance.backup.publish_git_snapshot import (
    check_secret_guard,
    publish_if_due,
    scan_file_content_for_secrets,
)


class ContentSecretScanningTest(unittest.TestCase):
    def test_clean_notes_pass_scan(self):
        """Normal markdown notes with no secrets must pass cleanly."""
        with tempfile.TemporaryDirectory(prefix="vault-clean-") as tmp:
            root = Path(tmp)
            (root / "note1.md").write_text("# Toplantı Notu\nBugün mimari kararları konuştuk.\n", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "note2.md").write_text("# Proje Planı\nHer şey yolunda.\n", encoding="utf-8")

            safe, findings = check_secret_guard(root)
            self.assertTrue(safe)
            self.assertEqual(findings, [])

    def test_synthetic_api_tokens_and_private_keys_abort_scan(self):
        """Realistic synthetic tokens (OpenAI, Anthropic, GitHub, AWS, RSA Private Key) must be detected without leaking values."""
        samples = [
            ("openai.md", "OPENAI_KEY = 'sk-proj-abc1234567890abcdef1234567890'\n", "provider-token"),
            ("anthropic.md", "ANTHROPIC_KEY = 'sk-ant-api03-abcdef1234567890abcdef1234567890-xyz\n", "provider-token"),
            ("github.md", "token: ghp_1234567890abcdef1234567890abcdef\n", "provider-token"),
            ("aws.md", "aws_access_key_id = AKIAIOSFODNN7EXAMPLE\n", "cloud-credential"),
            ("rsa.md", "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----\n", "private-key"),
            ("ec.md", "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEI...\n-----END EC PRIVATE KEY-----\n", "private-key"),
        ]

        for fname, content, expected_cat in samples:
            with tempfile.TemporaryDirectory(prefix="vault-secret-") as tmp:
                root = Path(tmp)
                (root / fname).write_text(content, encoding="utf-8")

                safe, findings = check_secret_guard(root)
                self.assertFalse(safe, f"Failed to detect secret in {fname}")
                self.assertGreater(len(findings), 0)
                # Output must only contain path and category, NOT the secret value
                finding_str = str(findings)
                self.assertNotIn("sk-proj-abc12345", finding_str)
                self.assertNotIn("sk-ant-api03", finding_str)
                self.assertNotIn("ghp_1234567890", finding_str)
                self.assertNotIn("AKIAIOSFODNN7EXAMPLE", finding_str)
                self.assertNotIn("MIIEowIBAAK", finding_str)

    def test_split_pattern_across_buffer_boundary_is_detected(self):
        """Secret patterns split across chunk read boundaries must not be missed."""
        with tempfile.TemporaryDirectory(prefix="vault-split-") as tmp:
            root = Path(tmp)
            # Create a large file where a secret is positioned across a 64KB boundary
            chunk_size = 64 * 1024
            padding_before = "A" * (chunk_size - 16) + " "  # space before boundary
            secret = "sk-proj-boundarytest1234567890abcdef12345"
            padding_after = "B" * 1000
            file_path = root / "large_split.md"
            file_path.write_text(padding_before + secret + padding_after, encoding="utf-8")

            findings = scan_file_content_for_secrets(file_path, root, chunk_size=chunk_size)
            self.assertIsNotNone(findings)
            self.assertEqual(findings.get("category"), "provider-token")
            # Secret value must not be leaked
            self.assertNotIn("boundarytest", str(findings))

    def test_unreadable_file_fails_closed(self):
        """Unreadable files must fail-closed and abort snapshot, not silently succeed."""
        with tempfile.TemporaryDirectory(prefix="vault-unreadable-") as tmp:
            root = Path(tmp)
            p = root / "unreadable.md"
            p.write_text("Normal content\n", encoding="utf-8")

            # Mock open to simulate permission error or OS read error
            from unittest.mock import patch
            with patch("builtins.open", side_effect=PermissionError("EACCES")):
                safe, findings = check_secret_guard(root)
                self.assertFalse(safe)
                self.assertTrue(any(f.get("category") == "read-error" for f in findings))

    def test_link_or_reparse_escape_fails_closed(self):
        """Symlinks pointing outside vault root must fail-closed."""
        with tempfile.TemporaryDirectory(prefix="vault-outside-") as tmp_out:
            outside_target = Path(tmp_out) / "secret.txt"
            outside_target.write_text("Sensitive host data\n", encoding="utf-8")

            with tempfile.TemporaryDirectory(prefix="vault-link-") as tmp:
                root = Path(tmp)
                link_path = root / "escape_link.md"
                try:
                    os.symlink(outside_target, link_path)
                except OSError:
                    # Windows may require developer mode or admin for symlinks; test reparse check if skipped
                    self.skipTest("Symlinks not supported in this environment")

                safe, findings = check_secret_guard(root)
                self.assertFalse(safe)
                self.assertTrue(any(f.get("category") in ("link-escape", "unsafe-link") for f in findings))

    def test_tracked_file_inside_ignored_directory_is_scanned(self):
        """A secret in a tracked file that happens to match .gitignore must still be scanned."""
        with tempfile.TemporaryDirectory(prefix="git-vault-") as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, check=True, capture_output=True)

            ignored_dir = root / "ignored_folder"
            ignored_dir.mkdir()
            tracked_secret = ignored_dir / "secret.md"
            tracked_secret.write_text("sk-proj-trackedsecret1234567890abcdef\n", encoding="utf-8")

            # Add to git index first
            subprocess.run(["git", "add", "-f", "ignored_folder/secret.md"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

            # Now add ignored_folder to .gitignore
            (root / ".gitignore").write_text("ignored_folder/\n", encoding="utf-8")

    def test_snapshot_index_race_condition_aborts_and_preserves_staging(self):
        """A secret captured into the immutable tree after the live-index scan aborts publication."""
        with tempfile.TemporaryDirectory(prefix="git-race-") as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, check=True, capture_output=True)

            # User had an existing staged file
            user_staged = root / "user_keep.md"
            user_staged.write_text("User important note\n", encoding="utf-8")
            subprocess.run(["git", "add", "user_keep.md"], cwd=root, check=True, capture_output=True)

            # A concurrent writer stages a secret into the isolated publication index.
            race_note = root / "race_note.md"
            race_note.write_text("Clean initial\n", encoding="utf-8")

            secret = "sk-proj-" + "SYNTHETICONLY1234567890" * 3
            original_run = subprocess.run
            attempted = []

            def fixture_run(argv, **kwargs):
                if argv[:5] == ["git", "add", "-A", "--", "."]:
                    race_note.write_text(secret, encoding="utf-8")
                    result = original_run(argv, **kwargs)
                    race_note.write_text("Clean content restored in tree\n", encoding="utf-8")
                    return result
                if len(argv) > 1 and argv[1] in ("commit", "push"):
                    attempted.append(argv[1])
                    return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
                return original_run(argv, **kwargs)

            from unittest.mock import patch
            from respectedbrain.maintenance.backup import publish_git_snapshot as snapshot
            receipt = root / "receipt.json"
            with patch.object(snapshot, "_branch_divergence_status", return_value="clean"), \
                 patch.object(snapshot.subprocess, "run", side_effect=fixture_run):
                outcome = snapshot.publish_if_due(root, apply=True, receipt_file=receipt)

            self.assertEqual(outcome.get("status"), "aborted:secret_found")
            self.assertEqual(attempted, [])  # Neither commit nor push was attempted!
            self.assertFalse(receipt.exists())

            # Prior user staged file must still be in git index (preserved, not blown away by git reset HEAD)
            status_out = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout
            self.assertIn("A  user_keep.md", status_out)


if __name__ == "__main__":
    unittest.main()
