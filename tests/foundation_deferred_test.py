"""Running executables queue verified temporary helpers rather than overwrite themselves."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from tests.foundation_support import make_context, snapshot
from tests.foundation_install_support import seed_package


class FoundationDeferredTest(unittest.TestCase):
    def test_active_executable_uses_os_temp_and_reports_pending(self):
        from respectedbrain.installation.deferred import defer_operation
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            ctx = make_context(root)
            seed_package(ctx.paths.app_root)
            new = seed_package(root / "new", content=b"MZ-new")
            before = snapshot(ctx.paths.app_root)
            with patch("respectedbrain.installation.deferred.sys.platform", "win32"), patch("respectedbrain.installation.deferred.sys.frozen", True, create=True), patch("respectedbrain.installation.deferred.sys.executable", str(ctx.paths.app_root / "respectedbrain.exe")), patch("respectedbrain.installation.deferred.subprocess.Popen") as process:
                result = defer_operation(ctx, mode="update", package=new)
            self.assertTrue(result.pending)
            self.assertFalse(result.success)
            helper = Path(process.call_args.args[0][0])
            self.assertTrue(helper.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            self.assertFalse(helper.is_relative_to(ctx.paths.data_root))
            self.assertEqual(snapshot(ctx.paths.app_root), before)
            self.assertEqual(helper.read_bytes(), b"MZ-fixture")
            import shutil
            shutil.rmtree(helper.parent)

    def test_helper_canonicalizes_its_owned_os_temp_allocation(self):
        from respectedbrain.installation import deferred
        from tests.package_contract_test import owned_temp_alias
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            ctx = make_context(root)
            seed_package(ctx.paths.app_root)
            package = seed_package(root / 'new', content=b'MZ-new')
            before = snapshot(ctx.paths.app_root)
            with owned_temp_alias(self, root) as (alias, allocated):
                (allocated / 'activation').mkdir()
                with patch.object(deferred.sys, 'platform', 'win32'), patch.object(deferred.sys, 'frozen', True, create=True), patch.object(deferred.sys, 'executable', str(ctx.paths.app_root / 'respectedbrain.exe')), patch.object(deferred.tempfile, 'mkdtemp', return_value=str(alias / 'activation')), patch.object(deferred.subprocess, 'Popen') as process:
                    result = deferred.defer_operation(ctx, mode='update', package=package)
                self.assertTrue(result.pending)
                helper = Path(process.call_args.args[0][0])
                self.assertEqual(helper, allocated / 'activation/respectedbrain.exe')
                self.assertEqual(helper.read_bytes(), b'MZ-fixture')
                self.assertEqual(snapshot(ctx.paths.app_root), before)

    def test_tampered_request_stops_before_any_activation(self):
        from respectedbrain.installation.deferred import resume_operation
        from respectedbrain.core.errors import OwnershipConflict
        with tempfile.TemporaryDirectory() as temporary:
            request = Path(temporary).resolve() / "request.json"
            request.write_text('{}', encoding="utf-8")
            with self.assertRaises(OwnershipConflict):
                resume_operation(request, expected_hash="0" * 64)
