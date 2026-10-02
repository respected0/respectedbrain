#!/usr/bin/env python3
"""Tests for Respected Brain installation wizard and multi-channel setup."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PY = REPO_ROOT / "installer" / "install.py"
SET_PROVIDER_PY = (REPO_ROOT / "runtime" / "scripts" / "set_summary_provider.py") if (REPO_ROOT / "runtime" / "scripts" / "set_summary_provider.py").is_file() else (REPO_ROOT / "scripts" / "set_summary_provider.py")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class WizardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temporary.name).resolve()
        self.home_patch = mock.patch.dict(
            os.environ,
            {
                "HOME": str(self.temp_root / "home"),
                "USERPROFILE": str(self.temp_root / "home"),
            },
        )
        self.home_patch.start()
        self.installer = load_module("install_test_module", INSTALL_PY)

    def tearDown(self) -> None:
        self.home_patch.stop()
        self.temporary.cleanup()

    def test_automated_install_creates_complete_vault_and_resolves_placeholders(self) -> None:
        target_vault = self.temp_root / "AdaOS"
        code = self.installer.install_vault(
            vault_path=target_vault,
            user_name="Ada Lovelace",
            user_bio="Algoritma Mimarı",
            companion="Babbage",
            os_name="AdaOS",
            summary_provider="antigravity",
            provider_priority=["antigravity", "codex"],
            install_global=False,
            quiet=True,
        )
        self.assertEqual(code, 0)
        self.assertTrue(target_vault.is_dir())
        self.assertTrue((target_vault / "knowledge" / "concepts").is_dir())
        self.assertTrue((target_vault / "knowledge" / "connections").is_dir())
        self.assertFalse((target_vault / "knowledge" / "concepts" / "core").exists())
        self.assertFalse((target_vault / "knowledge" / "concepts" / "finance").exists())

        # Check config.json
        config_path = target_vault / ".beyin" / "config.json"
        self.assertTrue(config_path.is_file())
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config_data.get("summary_provider"), "antigravity")
        self.assertEqual(config_data.get("provider_priority"), ["antigravity", "codex"])
        self.assertEqual(config_data.get("platform"), "windows-native" if os.name == "nt" else "portable")

        # Check placeholders resolved in Companion / Core.md
        core_file = target_vault / "🔮 850-Companion" / "Core.md"
        if core_file.is_file():
            content = core_file.read_text(encoding="utf-8")
            self.assertIn("Ada Lovelace", content)
            self.assertNotIn("{{USER_NAME}}", content)
            self.assertNotIn("{{COMPANION}}", content)

    @unittest.skipUnless(os.name == "nt", "native Windows hook paths")
    def test_fresh_native_install_renders_hooks_for_promoted_vault_path(self) -> None:
        target_vault = self.temp_root / "Final Türkçe 🚀 Vault"

        code = self.installer.install_vault(
            vault_path=target_vault,
            user_name="Ada",
            user_bio="Engineer",
            companion="Babbage",
            os_name="FinalOS",
            summary_provider="codex",
            python_command=[sys.executable],
            environment="native",
            quiet=True,
        )

        self.assertEqual(code, 0)
        hooks = json.loads((target_vault / ".codex/hooks.json").read_text(encoding="utf-8"))
        commands = [
            hook["commandWindows"]
            for groups in hooks["hooks"].values()
            for group in groups
            for hook in group["hooks"]
        ]
        self.assertEqual(len(commands), 5)
        for command in commands:
            self.assertTrue(
                str(target_vault) in command or str(target_vault.resolve()) in command,
                f"{target_vault} not in {command}",
            )
            self.assertNotIn(".respected-stage-", command)

    def test_install_refuses_non_empty_directory(self) -> None:
        target_vault = self.temp_root / "BusyVault"
        target_vault.mkdir(parents=True)
        (target_vault / "existing.txt").write_text("not empty", encoding="utf-8")

        code = self.installer.install_vault(
            vault_path=target_vault,
            user_name="Test",
            user_bio="Bio",
            companion="Comp",
            os_name="TestOS",
            summary_provider="auto",
            quiet=True,
        )
        self.assertEqual(code, 1)

    def test_reinstall_updates_managed_files_and_preserves_user_file_bytes(self) -> None:
        target_vault = self.temp_root / "RepeatableVault"
        arguments = {
            "vault_path": target_vault,
            "user_name": "Ada",
            "user_bio": "Engineer",
            "companion": "Babbage",
            "os_name": "RepeatableOS",
            "summary_provider": "codex",
            "provider_priority": ["codex", "gemini"],
            "python_command": [sys.executable] if os.name == "nt" else ["python3"],
            "environment": "native",
            "quiet": True,
        }

        first = self.installer.install_vault(**arguments)
        human_note = target_vault / "knowledge" / "human-note.md"
        expected = "İnsan notu byte-for-byte korunmalı.\n".encode("utf-8")
        human_note.write_bytes(expected)
        second = self.installer.install_vault(**arguments)

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(human_note.read_bytes(), expected)
        config = json.loads((target_vault / ".beyin/config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["summary_provider"], "codex")
        self.assertEqual(config["provider_priority"], ["codex", "gemini"])

    def test_reinstall_reapplies_requested_shortcut(self) -> None:
        target_vault = self.temp_root / "RepairableVault"
        desktop = self.temp_root / "Desktop"
        desktop.mkdir()
        arguments = {
            "vault_path": target_vault,
            "user_name": "Ada",
            "user_bio": "Engineer",
            "companion": "Babbage",
            "os_name": "RepairableOS",
            "summary_provider": "auto",
            "environment": "native",
            "quiet": True,
        }

        first = self.installer.install_vault(**arguments)
        second = self.installer.install_vault(
            **arguments,
            desktop_shortcut=True,
            desktop_dir_override=desktop,
        )

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        extension = ".webloc" if sys.platform == "darwin" else ".url" if os.name == "nt" else ".desktop"
        self.assertTrue((desktop / f"RepairableVault{extension}").is_file())

    def test_reinstall_returns_requested_global_integration_failure(self) -> None:
        target_vault = self.temp_root / "FailedRepairVault"
        arguments = {
            "vault_path": target_vault,
            "user_name": "Ada",
            "user_bio": "Engineer",
            "companion": "Babbage",
            "os_name": "FailedRepairOS",
            "summary_provider": "auto",
            "environment": "native",
            "quiet": True,
        }
        self.assertEqual(self.installer.install_vault(**arguments), 0)

        def integration_failure(command, **_kwargs):
            script = Path(command[1]).name if len(command) > 1 else ""
            if script == "install_global.py":
                return SimpleNamespace(returncode=9, stdout="", stderr="global repair failed")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(self.installer.subprocess, "run", side_effect=integration_failure):
            code = self.installer.install_vault(**arguments, install_global=True)

        self.assertEqual(code, 9)

    @unittest.skipUnless(os.name == "nt", "native Windows interpreter propagation")
    def test_native_install_persists_discovered_python_executable_in_hooks(self) -> None:
        target_vault = self.temp_root / "RuntimeVault"
        runtime = r"C:\Users\Ada\Custom Python\python.exe"
        code = self.installer.install_vault(
            vault_path=target_vault,
            user_name="Ada",
            user_bio="Engineer",
            companion="Babbage",
            os_name="AdaOS",
            summary_provider="auto",
            python_command=[runtime],
            environment="native",
            quiet=True,
        )

        self.assertEqual(code, 0)
        config = json.loads((target_vault / ".beyin/config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["python_command"], [runtime])
        rendered = (target_vault / ".claude/settings.json").read_text(encoding="utf-8")
        self.assertIn("Custom Python", rendered)
        self.assertNotIn("py.exe", rendered)

    def test_render_failure_rolls_back_partial_fresh_install(self) -> None:
        target_vault = self.temp_root / "BrokenVault"
        with mock.patch.object(
            self.installer.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=7, stdout="", stderr="render failed"),
        ):
            code = self.installer.install_vault(
                vault_path=target_vault,
                user_name="Test",
                user_bio="Bio",
                companion="Comp",
                os_name="TestOS",
                summary_provider="auto",
                quiet=True,
            )

        self.assertEqual(code, 7)
        self.assertFalse(target_vault.exists(), "Başarısız temiz kurulum yarım vault bırakmamalı")

    def test_interactive_wizard_antigravity_priority_selection(self) -> None:
        target_vault = self.temp_root / "InteractiveVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Yazılım Mühendisi",   # 3. Bio
            "Companion",           # 4. Companion
            "TestOS",              # 5. OS Name
            "2",                   # 6. Seçim: [2] Google Antigravity Öncelikli
            "1",                   # 7. Ortam: [1] Native
            "h",                   # 8. Global AI: Hayır
            "h",                   # 9. Masaüstü Kısayolu: Hayır
            "h",                   # 10. Sabah Brifingi: Hayır
            "h",                   # 11. MCP Sunucusu: Hayır
        ]

        with mock.patch("builtins.input", side_effect=mock_inputs):
            code = self.installer._interactive_wizard()

        self.assertEqual(code, 0)
        config_data = json.loads((target_vault / ".beyin" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config_data.get("summary_provider"), "auto")
        self.assertEqual(
            config_data.get("provider_priority"),
            ["antigravity", "gemini", "codex", "claude", "cursor"],
        )
        self.assertEqual(config_data.get("environment"), "native")

    def test_interactive_wizard_custom_priority_selection(self) -> None:
        target_vault = self.temp_root / "CustomVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Yazılım Mühendisi",   # 3. Bio
            "Companion",           # 4. Companion
            "TestOS",              # 5. OS Name
            "6",                   # 6. Seçim: [6] Özel Sıralama Belirle
            "antigravity, codex",  # Özel sıra
            "3",                   # 7. Ortam: [3] Hibrit
            "h",                   # 8. Global AI: Hayır
            "h",                   # 9. Masaüstü Kısayolu: Hayır
            "h",                   # 10. Sabah Brifingi: Hayır
            "h",                   # 11. MCP Sunucusu: Hayır
        ]

        with mock.patch("builtins.input", side_effect=mock_inputs):
            code = self.installer._interactive_wizard()

        self.assertEqual(code, 0)
        config_data = json.loads((target_vault / ".beyin" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config_data.get("summary_provider"), "auto")
        self.assertEqual(config_data.get("provider_priority"), ["antigravity", "codex"])
        self.assertEqual(config_data.get("environment"), "hybrid")
        self.assertEqual(config_data.get("platform"), "windows-wsl" if os.name == "nt" else "portable")
        if os.name == "nt":
            rendered = (target_vault / ".claude/settings.json").read_text(encoding="utf-8")
            self.assertIn("wsl.exe", rendered)

    def test_interactive_wizard_lock_single_provider_fail_fast(self) -> None:
        target_vault = self.temp_root / "LockedVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Yazılım Mühendisi",   # 3. Bio
            "Companion",           # 4. Companion
            "TestOS",              # 5. OS Name
            "5",                   # 6. Seçim: [5] Tek Model Kitle
            "codex",               # Kilitlenecek model
            "1",                   # 7. Ortam: [1] Native
            "h",                   # 8. Global AI: Hayır
            "h",                   # 9. Masaüstü Kısayolu: Hayır
            "h",                   # 10. Sabah Brifingi: Hayır
            "h",                   # 11. MCP Sunucusu: Hayır
        ]

        with mock.patch("builtins.input", side_effect=mock_inputs):
            code = self.installer._interactive_wizard()

        self.assertEqual(code, 0)
        config_data = json.loads((target_vault / ".beyin" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config_data.get("summary_provider"), "codex")
        self.assertEqual(config_data.get("provider_priority"), ["codex"])
        self.assertIs(config_data.get("provider_fallback"), False)

    def test_create_desktop_shortcut_generates_obsidian_uri(self) -> None:
        desktop_dir = self.temp_root / "Desktop"
        desktop_dir.mkdir()
        target_vault = self.temp_root / "ShortcutVault"
        target_vault.mkdir()

        shortcut_file = self.installer.create_desktop_shortcut(
            os_name="TestOS",
            vault_path=target_vault,
            desktop_dir_override=desktop_dir,
        )

        self.assertIsNotNone(shortcut_file)
        self.assertTrue(shortcut_file.is_file())
        if sys.platform == "darwin":
            expected_name = "ShortcutVault.webloc"
        elif os.name == "nt" or str(desktop_dir).startswith("/mnt/c/"):
            expected_name = "ShortcutVault.url"
        else:
            expected_name = "ShortcutVault.desktop"
        self.assertEqual(shortcut_file.name, expected_name)
        content = shortcut_file.read_text(encoding="utf-8")
        self.assertIn("obsidian://open?vault=ShortcutVault", content)

    def test_macos_shortcut_is_native_webloc(self) -> None:
        desktop_dir = self.temp_root / "MacDesktop"
        desktop_dir.mkdir()
        vault = self.temp_root / "Furkan Brain"
        vault.mkdir()
        with mock.patch.object(self.installer.sys, "platform", "darwin"):
            shortcut = self.installer.create_desktop_shortcut(
                "BrainOS", vault, desktop_dir_override=desktop_dir
            )

        self.assertEqual(shortcut.suffix, ".webloc")
        document = plistlib.loads(shortcut.read_bytes())
        self.assertEqual(document["URL"], "obsidian://open?vault=Furkan%20Brain")

    def test_interactive_wizard_with_mcp_registration(self) -> None:
        target_vault = self.temp_root / "McpVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Mühendis",            # 3. Bio
            "Companion",           # 4. Companion
            "TestOS",              # 5. OS Name
            "1",                   # 6. Seçim: [1] Auto
            "1",                   # 7. Ortam: [1] Native
            "h",                   # 8. Global AI: Hayır
            "h",                   # 9. Masaüstü Kısayolu: Hayır
            "h",                   # 10. Sabah Brifingi: Hayır
            "e",                   # 11. MCP Sunucusu: EVET
        ]

        # Gerçek kullanıcı home dizinini korumak için subprocess'ı izole et
        with mock.patch("builtins.input", side_effect=mock_inputs), \
             mock.patch("subprocess.run") as mock_sub:
            mock_sub.return_value = mock.Mock(returncode=0, stdout="✓ Mocked MCP kaydı başarılı", stderr="")
            code = self.installer._interactive_wizard()

        self.assertEqual(code, 0)
        self.assertTrue((target_vault / "scripts" / "vault_mcp_server.py").is_file())
        # subprocess.run'ın vault_mcp_server.py --register ile çağrıldığını doğrula
        called_args = [call[0][0] for call in mock_sub.call_args_list if call[0]]
        self.assertTrue(any("vault_mcp_server.py" in str(arg) and "--register" in arg for arg in called_args))


if __name__ == "__main__":
    unittest.main()
