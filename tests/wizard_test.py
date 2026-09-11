#!/usr/bin/env python3
"""Tests for Respected Brain installation wizard and multi-channel setup."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import ModuleType
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PY = REPO_ROOT / "install.py"
SET_PROVIDER_PY = REPO_ROOT / "scripts" / "set_summary_provider.py"


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
        self.installer = load_module("install_test_module", INSTALL_PY)
        self.temporary = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temporary.name)

    def tearDown(self) -> None:
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
        self.assertTrue((target_vault / "knowledge" / "index.md").is_file())
        self.assertTrue((target_vault / "knowledge" / "concepts" / "core").is_dir())
        self.assertTrue((target_vault / "knowledge" / "concepts" / "finance").is_dir())

        # Check config.json
        config_path = target_vault / ".beyin" / "config.json"
        self.assertTrue(config_path.is_file())
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config_data.get("summary_provider"), "antigravity")
        self.assertEqual(config_data.get("provider_priority"), ["antigravity", "codex"])

        # Check placeholders resolved in Companion / Core.md
        core_file = target_vault / "🔮 850-Companion" / "Core.md"
        if core_file.is_file():
            content = core_file.read_text(encoding="utf-8")
            self.assertIn("Ada Lovelace", content)
            self.assertNotIn("{{USER_NAME}}", content)
            self.assertNotIn("{{COMPANION}}", content)

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

    def test_interactive_wizard_antigravity_priority_selection(self) -> None:
        target_vault = self.temp_root / "InteractiveVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Yazılım Mühendisi",   # 3. Bio
            "Jarvis",              # 4. Companion
            "RespectedOS",         # 5. OS Name
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
            ["antigravity", "codex", "claude", "cursor"],
        )
        self.assertEqual(config_data.get("environment"), "native")

    def test_interactive_wizard_custom_priority_selection(self) -> None:
        target_vault = self.temp_root / "CustomVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Yazılım Mühendisi",   # 3. Bio
            "Jarvis",              # 4. Companion
            "RespectedOS",         # 5. OS Name
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

    def test_interactive_wizard_lock_single_provider_fail_fast(self) -> None:
        target_vault = self.temp_root / "LockedVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Yazılım Mühendisi",   # 3. Bio
            "Jarvis",              # 4. Companion
            "RespectedOS",         # 5. OS Name
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

    def test_create_desktop_shortcut_generates_obsidian_uri(self) -> None:
        desktop_dir = self.temp_root / "Desktop"
        desktop_dir.mkdir()
        target_vault = self.temp_root / "ShortcutVault"
        target_vault.mkdir()

        shortcut_file = self.installer.create_desktop_shortcut(
            os_name="RespectedOS",
            vault_path=target_vault,
            desktop_dir_override=desktop_dir,
        )

        self.assertIsNotNone(shortcut_file)
        self.assertTrue(shortcut_file.is_file())
        self.assertEqual(shortcut_file.name, "ShortcutVault.url")
        content = shortcut_file.read_text(encoding="utf-8")
        self.assertIn("obsidian://open?vault=ShortcutVault", content)

    def test_interactive_wizard_with_mcp_registration(self) -> None:
        target_vault = self.temp_root / "McpVault"
        mock_inputs = [
            str(target_vault),     # 1. Kasa yolu
            "Furkan",              # 2. Ad
            "Mühendis",            # 3. Bio
            "Jarvis",              # 4. Companion
            "RespectedOS",         # 5. OS Name
            "1",                   # 6. Seçim: [1] Auto
            "1",                   # 7. Ortam: [1] Native
            "h",                   # 8. Global AI: Hayır
            "h",                   # 9. Masaüstü Kısayolu: Hayır
            "h",                   # 10. Sabah Brifingi: Hayır
            "e",                   # 11. MCP Sunucusu: EVET
        ]

        with mock.patch("builtins.input", side_effect=mock_inputs):
            code = self.installer._interactive_wizard()

        self.assertEqual(code, 0)
        self.assertTrue((target_vault / "scripts" / "vault_mcp_server.py").is_file())


if __name__ == "__main__":
    unittest.main()
