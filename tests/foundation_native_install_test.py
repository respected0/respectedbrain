"""Actual Windows processes, unique Inno registry key and executable activation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from uuid import uuid4

from tests.foundation_support import snapshot, note_hashes
from respectedbrain.installation.payload import validate_package

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Native Windows executable/Inno/ACL cases run on Windows CI")
class FoundationNativeInstallTest(unittest.TestCase):
    def run_native(self, argv, *, timeout=300, **kwargs):
        process = subprocess.Popen(argv, **kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Terminate only this fixture's known subprocess tree before any
            # recursive temp cleanup, including Inno's extracted service child.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.communicate()
            raise
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="Respected Türkçe 🧠 ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.app, self.data, self.vault = self.root / "Programs/RespectedBrain", self.root / "data", self.root / "Notlar 🧠"
        self.distribution = ROOT / "dist/RespectedBrain"
        self.document = validate_package(self.distribution)
        self.env = {**os.environ, "RESPECTED_APP_DIR": str(self.app), "RESPECTED_DATA_DIR": str(self.data), "PATH": str(Path(os.environ["SystemRoot"]) / "System32"), "BEYIN_INVOKED_BY": "native-verification", "PYTHONPATH": ""}

    def run_cli(self, launcher, *args):
        return self.run_native([str(launcher), *map(str, args)], cwd=self.root, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

    def install(self):
        result = self.run_cli(self.distribution / "respectedbrain.exe", "setup", "--vault", self.vault, "--package", self.distribution)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.vault / "keep.md").write_bytes("# Benim notum 🧠\n".encode())

    def wait_receipt(self, pending):
        self.assertTrue(pending["pending"])
        self.assertFalse(pending["success"])
        receipt = self.data / "backups" / pending["tx_id"] / "result.json"
        deadline = time.monotonic() + 300
        while not receipt.is_file() and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertTrue(receipt.is_file(), "Deferred helper produced no final receipt")
        return json.loads(receipt.read_text(encoding="utf-8"))

    def test_executable_in_use_update_and_health_rollback(self):
        self.install()
        before = snapshot(self.app)
        notes = note_hashes(self.vault)
        bad = self.root / "bad-package"
        shutil.copytree(self.distribution, bad)
        document = json.loads((bad / "distribution.json").read_text(encoding="utf-8"))
        document["version"] = "9.9.9"
        (bad / "distribution.json").write_text(json.dumps(document), encoding="utf-8")
        result = self.run_cli(self.app / "respectedbrain.exe", "update", "--package", bad)
        self.assertEqual(result.returncode, 0, result.stderr)
        final = self.wait_receipt(json.loads(result.stdout))
        self.assertFalse(final["success"], final)
        self.assertEqual(snapshot(self.app), before)
        self.assertEqual(note_hashes(self.vault), notes)
        result = self.run_cli(self.app / "respectedbrain.exe", "update", "--package", self.distribution)
        self.assertEqual(result.returncode, 0, result.stderr)
        final = self.wait_receipt(json.loads(result.stdout))
        self.assertTrue(final["success"], final)
        self.assertEqual(snapshot(self.app), before)

    def test_readonly_app_root_writes_cache_only_to_data(self):
        self.install()
        before = snapshot(self.app)
        import ctypes
        # Native ACL, rather than Python's readonly bit on a directory.
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, check=True).stdout
        import re
        sid = re.search(rb'S-1-[0-9-]+', identity).group().decode("ascii")
        # Generic W includes SYNCHRONIZE, which also prevents CreateProcess.
        result = subprocess.run(["icacls", str(self.app), "/deny", "*" + sid + ":(OI)(CI)(WD,AD,WEA,WA)"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            with self.assertRaises(PermissionError):
                (self.app / "should-not-write.txt").write_bytes(b"no")
            result = self.run_cli(self.app / "respectedbrain.exe", "search", "--json", "notum")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(list((self.data / "vaults").glob("*/cache/search_index.db")))
            self.assertEqual(snapshot(self.app), before)
        finally:
            restore = subprocess.run(["icacls", str(self.app), "/remove:d", "*" + sid, "/T", "/C"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(restore.returncode, 0, restore.stderr)

    def test_actual_inno_install_update_and_owned_uninstall(self):
        configured_compiler = os.environ.get("INNO_COMPILER")
        compiler = Path(configured_compiler) if configured_compiler else Path(os.environ["LOCALAPPDATA"]) / "Programs/Inno Setup 6/ISCC.exe"
        if not configured_compiler and not compiler.is_file():
            compiler = Path(shutil.which("ISCC.exe") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
        self.assertTrue(compiler.is_file(), "Native Inno compiler is required")
        app_id = "{" + str(uuid4()).upper() + "}"
        command = [str(compiler), "/DMyAppId=" + app_id, "/DPayloadDir=" + str(self.distribution), "/DOutputDir=" + str(self.root), str(ROOT / "packaging/windows/respected_setup.iss")]
        compiled = self.run_native(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        installer = self.root / "RespectedBrain-Windows-Setup.exe"
        options = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART", "/DIR=" + str(self.app), "/DATA=" + str(self.data), "/VAULT=" + str(self.vault), "/LOG=" + str(self.root / "inno.log")]
        import winreg
        key = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + app_id + "_is1"
        try:
            for step in ("install", "update"):
                installed = self.run_native([str(installer), *options], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(installed.returncode, 0, (self.root / "inno.log").read_text(encoding="utf-8-sig", errors="replace"))
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as registry:
                    self.assertEqual(winreg.QueryValueEx(registry, "InstallLocation")[0], str(self.app))
                    registered_uninstall = winreg.QueryValueEx(registry, "UninstallString")[0]
                    self.assertIn(str(self.data), registered_uninstall)
                    self.assertIn(str(self.vault), registered_uninstall)
                self.assertTrue((self.app / "uninstall/unins000.exe").is_file())
                self.assertEqual({path.name for path in (self.app / "uninstall").glob("unins*")}, {"unins000.exe", "unins000.dat"})
                if step == "install":
                    (self.vault / "keep.md").write_bytes(b"native note")
                    before = note_hashes(self.vault)
                else:
                    self.assertEqual(note_hashes(self.vault), before)
            sentinel = self.app / "user.py"
            sentinel.write_bytes(b"user")
            from respectedbrain.installation.ownership import read_manifest, prove_ownership
            recorded = read_manifest(self.data / "install-manifest.json")
            for name in ("unins000.exe", "unins000.dat"):
                self.assertTrue(prove_ownership(self.app / "uninstall" / name, recorded), "Inno changed " + name + " after final sealing")
            before_log = (self.app / "uninstall/unins000.dat").read_bytes()
            # Run exactly the registered Apps/Programs command, with no extra
            # DATA/VAULT arguments or environment overrides concealing a bug.
            clean_env = {key: value for key, value in self.env.items() if key not in ("RESPECTED_APP_DIR", "RESPECTED_DATA_DIR")}
            uninstalled = self.run_native(registered_uninstall, env=clean_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            self.assertEqual(uninstalled.returncode, 0, uninstalled.stderr)
            final = self.wait_receipt(json.loads(uninstalled.stdout))
            self.assertTrue(final["success"], final)
            receipt = self.data / "logs/uninstall-result.json"
            diagnostic = receipt.read_text(encoding="utf-8") if receipt.is_file() else "No common-service uninstall receipt"
            if uninstalled.returncode and (self.app / "uninstall/unins000.dat").is_file():
                after_log = (self.app / "uninstall/unins000.dat").read_bytes()
                diagnostic += "\nInno log changes: " + repr([(i, a, b) for i, (a, b) in enumerate(zip(before_log, after_log)) if a != b]) + " lengths=" + repr((len(before_log), len(after_log)))
            self.assertEqual(uninstalled.returncode, 0, diagnostic)
            self.assertFalse((self.app / "respectedbrain.exe").exists())
            self.assertEqual(sentinel.read_bytes(), b"user")
            self.assertTrue((self.data / "config.json").exists())
            self.assertEqual(note_hashes(self.vault), before)
            with self.assertRaises(FileNotFoundError):
                winreg.OpenKey(winreg.HKEY_CURRENT_USER, key)
        finally:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except FileNotFoundError:
                pass
