"""Retired updater forwards verified-package update through the public CLI."""
from pathlib import Path
import unittest
from unittest import mock
from tests.runtime_layout_test import load, ROOT

class AutoUpdaterTest(unittest.TestCase):
    def test_explicit_verified_package_update_preserves_exit_status(self):
        updater = load(ROOT / "runtime/scripts/auto_updater.py")
        arguments = ["--vault-id", "93e9e921-3334-4a6a-a381-1d4c42a9d405", "--package", "/explicit/package"]
        with mock.patch("respectedbrain.cli.main", return_value=6) as dispatch:
            self.assertEqual(updater.main(arguments), 6)
        dispatch.assert_called_once_with(["update", *arguments])

    def test_old_force_check_options_are_not_silently_applied(self):
        updater = load(ROOT / "runtime/scripts/auto_updater.py")
        with mock.patch("respectedbrain.cli._dispatch", side_effect=AssertionError("write")):
            self.assertEqual(updater.main(["--force", "--check"]), 2)

if __name__ == "__main__":
    unittest.main()
