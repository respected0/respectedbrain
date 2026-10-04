"""Verified-package update uses only the public CLI."""
from pathlib import Path
import unittest
from unittest import mock
from respectedbrain import cli


class AutoUpdaterTest(unittest.TestCase):
    def test_explicit_verified_package_update_preserves_exit_status(self):
        identity = "93e9e921-3334-4a6a-a381-1d4c42a9d405"
        with mock.patch.object(cli, "_dispatch", return_value=6) as dispatch:
            self.assertEqual(cli.main(["update", "--vault-id", identity, "--package", "/explicit/package"]), 6)
        args = dispatch.call_args.args[0]
        self.assertEqual((args.command, args.vault_id, args.package), ("update", identity, Path("/explicit/package")))

    def test_old_force_check_options_are_not_silently_applied(self):
        with mock.patch.object(cli, "_dispatch", side_effect=AssertionError("write")):
            self.assertEqual(cli.main(["update", "--force", "--check"]), 2)


if __name__ == "__main__":
    unittest.main()
