"""Update source wrapper preserves the canonical package CLI contract."""
from pathlib import Path
import unittest
from unittest import mock
from respectedbrain.installation.transaction import OperationResult
from tests.runtime_layout_test import load, ROOT
from tests.foundation_integrations_test import IntegrationFixture

class TestUpdateCli(IntegrationFixture,unittest.TestCase):
    def test_update_requires_explicit_verified_package_without_vault_discovery(self):
        with mock.patch("respectedbrain.cli._dispatch",side_effect=AssertionError("mutation")):
            self.assertEqual(load(ROOT / "installer/update.py").main(["--vault-id",self.ctx.paths.vault_id]),2)

    def test_update_main_dispatches_selected_uuid_and_package_once(self):
        from respectedbrain import cli
        backend=mock.Mock()
        with mock.patch.object(cli,"bootstrap",return_value=self.ctx),mock.patch("respectedbrain.integrations.backend.NativeBackend",return_value=backend),mock.patch("respectedbrain.installation.deferred.defer_operation",return_value=None),mock.patch("respectedbrain.installation.update.update",return_value=OperationResult(True,"test",())) as update:
            code=load(ROOT / "installer/update.py").main(["--vault-id",self.ctx.paths.vault_id,"--package",str(self.root / "package")])
        self.assertEqual(code,0)
        update.assert_called_once_with(self.ctx,package=(self.root / "package").resolve(),backend=backend)

    def test_update_failure_exit_status_is_not_rewritten_to_success(self):
        from respectedbrain import cli
        with mock.patch.object(cli,"bootstrap",return_value=self.ctx),mock.patch("respectedbrain.integrations.backend.NativeBackend"),mock.patch("respectedbrain.installation.deferred.defer_operation",return_value=None),mock.patch("respectedbrain.installation.update.update",return_value=OperationResult(False,"test",("failure",))):
            code=load(ROOT / "installer/update.py").main(["--vault-id",self.ctx.paths.vault_id,"--package",str(self.root / "package")])
        self.assertEqual(code,1)

if __name__=="__main__":
    unittest.main()
