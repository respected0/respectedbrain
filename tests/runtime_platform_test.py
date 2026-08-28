#!/usr/bin/env python3
"""Behavior tests for Respot's host-specific runtime primitives."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "template" / ".beyin" / "runtime_platform.py"


def load_runtime():
    spec = importlib.util.spec_from_file_location("respot_runtime_platform", RUNTIME_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runtime module: {RUNTIME_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNTIME = load_runtime()


class RuntimePlatformTest(unittest.TestCase):
    def test_nonblocking_lock_reports_contention(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "lock"
            with (
                path.open("a+", encoding="utf-8") as first,
                path.open("a+", encoding="utf-8") as second,
            ):
                with RUNTIME.exclusive_lock(first, blocking=True) as held:
                    self.assertTrue(held)
                    with RUNTIME.exclusive_lock(second, blocking=False) as second_held:
                        self.assertFalse(second_held)

    def test_exclusive_claim_has_a_single_winner(self):
        with tempfile.TemporaryDirectory() as temporary:
            claim = Path(temporary) / "claim"
            self.assertTrue(RUNTIME.create_exclusive_claim(claim))
            self.assertFalse(RUNTIME.create_exclusive_claim(claim))
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(claim.stat().st_mode) & 0o077, 0)

    def test_detached_process_options_match_the_host(self):
        options = RUNTIME.detached_process_options()
        if os.name == "nt":
            self.assertIn("creationflags", options)
            self.assertNotIn("start_new_session", options)
        else:
            self.assertEqual(options, {"start_new_session": True})

    def test_path_containment_rejects_parent_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "vault"
            vault.mkdir()
            inside = vault / "notes" / "note.md"
            inside.parent.mkdir()
            inside.write_text("inside", encoding="utf-8")
            outside = base / "outside.md"
            outside.write_text("outside", encoding="utf-8")

            self.assertTrue(RUNTIME.path_within_vault(vault, vault))
            self.assertTrue(RUNTIME.path_within_vault(inside, vault))
            self.assertFalse(RUNTIME.path_within_vault(outside, vault))
            self.assertFalse(RUNTIME.path_within_vault(vault / ".." / "outside.md", vault))

    def test_path_containment_rejects_symlink_components(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "vault"
            vault.mkdir()
            outside = base / "outside"
            outside.mkdir()
            linked = vault / "linked"
            try:
                linked.symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlink creation is unavailable: {error}")

            self.assertFalse(RUNTIME.path_within_vault(linked / "note.md", vault))


if __name__ == "__main__":
    unittest.main()
