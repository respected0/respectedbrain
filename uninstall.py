#!/usr/bin/env python3
"""Respected Brain v0.0.1 — Cross-Platform Uninstaller.

Safely removes global integrations, hooks, scheduled tasks, MCP registrations,
and desktop shortcuts. By default, user vault notes are strictly preserved.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


_configure_console_output()


def _is_color_supported() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


class Colors:
    COLOR = _is_color_supported()
    CYAN = "\033[96m" if COLOR else ""
    GREEN = "\033[92m" if COLOR else ""
    YELLOW = "\033[93m" if COLOR else ""
    RED = "\033[91m" if COLOR else ""
    BOLD = "\033[1m" if COLOR else ""
    DIM = "\033[2m" if COLOR else ""
    RESET = "\033[0m" if COLOR else ""


def _prompt_user(prompt: str, default: str = "") -> str:
    default_text = f" [{default}]" if default else ""
    try:
        val = input(f"{Colors.BOLD}{prompt}{Colors.RESET}{default_text}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{Colors.YELLOW}İşlem iptal edildi.{Colors.RESET}")
        sys.exit(1)
    return val if val else default


def remove_global_integrations() -> list[str]:
    """Remove global rules, hooks, and skills across Antigravity, Cursor, Codex, and Claude."""
    cleaned = []
    home = Path.home()

    # 1. Antigravity (~/.gemini)
    gemini_dir = home / ".gemini"
    gemini_md = gemini_dir / "GEMINI.md"
    if gemini_md.is_file():
        text = gemini_md.read_text(encoding="utf-8", errors="replace")
        new_text = re.sub(
            r"<!-- (RESPECTED-GLOBAL|AVENOX-GLOBAL):BEGIN -->.*?<!-- \1:END -->\s*",
            "",
            text,
            flags=re.DOTALL,
        )
        if new_text != text:
            gemini_md.write_text(new_text, encoding="utf-8")
            cleaned.append(f"Antigravity global kuralı temizlendi: {gemini_md}")

    gemini_hooks = gemini_dir / "config" / "hooks.json"
    if gemini_hooks.is_file():
        try:
            data = json.loads(gemini_hooks.read_text(encoding="utf-8", errors="replace"))
            changed = False
            for event, handlers in list(data.items()):
                if isinstance(handlers, list):
                    filtered = [h for h in handlers if "respected" not in str(h).lower() and "avenox" not in str(h).lower()]
                    if len(filtered) != len(handlers):
                        data[event] = filtered
                        changed = True
            if changed:
                gemini_hooks.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                cleaned.append(f"Antigravity kancaları temizlendi: {gemini_hooks}")
        except Exception:
            pass

    # 2. Cursor (~/.cursor)
    cursor_rule = home / ".cursor" / "rules" / "respected-brain.mdc"
    if cursor_rule.is_file():
        cursor_rule.unlink(missing_ok=True)
        cleaned.append(f"Cursor global kuralı silindi: {cursor_rule}")

    cursor_rule_legacy = home / ".cursor" / "rules" / "avenox-beyin.mdc"
    if cursor_rule_legacy.is_file():
        cursor_rule_legacy.unlink(missing_ok=True)
        cleaned.append(f"Cursor eski global kuralı silindi: {cursor_rule_legacy}")

    cursor_hooks = home / ".cursor" / "hooks.json"
    if cursor_hooks.is_file():
        try:
            data = json.loads(cursor_hooks.read_text(encoding="utf-8", errors="replace"))
            changed = False
            for event, handlers in list(data.items()):
                if isinstance(handlers, list):
                    filtered = [h for h in handlers if "respected" not in str(h).lower() and "avenox" not in str(h).lower()]
                    if len(filtered) != len(handlers):
                        data[event] = filtered
                        changed = True
            if changed:
                cursor_hooks.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                cleaned.append(f"Cursor kancaları temizlendi: {cursor_hooks}")
        except Exception:
            pass

    # 3. Codex (~/.codex)
    codex_hooks = home / ".codex" / "hooks.json"
    if codex_hooks.is_file():
        try:
            data = json.loads(codex_hooks.read_text(encoding="utf-8", errors="replace"))
            changed = False
            for event, handlers in list(data.items()):
                if isinstance(handlers, list):
                    filtered = [h for h in handlers if "respected" not in str(h).lower() and "avenox" not in str(h).lower()]
                    if len(filtered) != len(handlers):
                        data[event] = filtered
                        changed = True
            if changed:
                codex_hooks.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                cleaned.append(f"Codex kancaları temizlendi: {codex_hooks}")
        except Exception:
            pass

    return cleaned


def remove_scheduled_tasks() -> list[str]:
    """Remove Windows scheduled tasks or cron jobs for morning briefings."""
    cleaned = []
    if os.name == "nt" or shutil.which("schtasks.exe"):
        # Query and delete Respected tasks
        try:
            out = subprocess.run(
                ["schtasks.exe", "/Query", "/FO", "LIST"],
                capture_output=True,
                text=True,
                check=False,
                errors="replace",
            )
            for line in out.stdout.splitlines():
                if "RespectedDailyBriefing" in line or "AvenoxDailyBriefing" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        task_name = parts[1].strip()
                        subprocess.run(
                            ["schtasks.exe", "/Delete", "/TN", task_name, "/F"],
                            capture_output=True,
                            check=False,
                        )
                        cleaned.append(f"Windows Görev Zamanlayıcı görevi silindi: {task_name}")
        except Exception:
            pass
    elif shutil.which("crontab"):
        try:
            out = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
            if out.returncode == 0:
                lines = [
                    l for l in out.stdout.splitlines()
                    if "morning_briefing.py" not in l and "RespectedDailyBriefing" not in l
                ]
                if len(lines) != len(out.stdout.splitlines()):
                    new_cron = "\n".join(lines) + ("\n" if lines else "")
                    subprocess.run(["crontab", "-"], input=new_cron, text=True, check=False)
                    cleaned.append("Linux/macOS crontab sabah brifingi görevi kaldırıldı")
        except Exception:
            pass
    return cleaned


def remove_desktop_shortcuts(vault_name: str = "RespectedOS") -> list[str]:
    """Remove desktop shortcuts created for Obsidian vault."""
    cleaned = []
    home = Path.home()
    desktop_candidates = [
        home / "Desktop",
        home / "Masaüstü",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Masaüstü",
    ]
    shortcut_names = [
        f"{vault_name}.url",
        f"{vault_name}.lnk",
        "RespectedOS.url",
        "RespectedOS.lnk",
        f"{vault_name}.desktop",
        "RespectedOS.desktop",
    ]
    for d in desktop_candidates:
        if d.is_dir():
            for s in shortcut_names:
                p = d / s
                if p.is_file():
                    p.unlink(missing_ok=True)
                    cleaned.append(f"Masaüstü kısayolu silindi: {p}")

    # macOS .app launcher
    app_launcher = Path(f"/Applications/{vault_name}.app")
    if app_launcher.exists():
        shutil.rmtree(app_launcher, ignore_errors=True)
        cleaned.append(f"macOS uygulama başlatıcı silindi: {app_launcher}")

    return cleaned


def remove_mcp_config() -> list[str]:
    """Remove Respected Vault MCP server registration from Claude Desktop and Cursor."""
    cleaned = []
    home = Path.home()

    # Claude Desktop
    claude_configs = [
        home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
        home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    ]
    for cfg in claude_configs:
        if cfg.is_file():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8", errors="replace"))
                servers = data.get("mcpServers", {})
                if "respected-vault" in servers or "respected-vault-mcp" in servers:
                    servers.pop("respected-vault", None)
                    servers.pop("respected-vault-mcp", None)
                    data["mcpServers"] = servers
                    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    cleaned.append(f"Claude Desktop MCP kaydı kaldırıldı: {cfg}")
            except Exception:
                pass

    return cleaned


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Respected Brain — Sistem Entegrasyonlarını Temiz Kaldırıcı (Uninstaller)"
    )
    parser.add_argument(
        "--vault-path",
        default=None,
        help="Hedef vault dizini (opsiyonel)",
    )
    parser.add_argument(
        "--purge-vault",
        action="store_true",
        help="DİKKAT: Kasa dizinini ve içindeki notları da tamamen siler (onay gerektirir)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Soru sormadan onaylanmış adımları doğrudan çalıştır",
    )

    args = parser.parse_args(argv)

    print(f"{Colors.CYAN}{Colors.BOLD}════════════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}          Respected Brain v0.0.1 — Kaldırma Aracı (Uninstall)       {Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}════════════════════════════════════════════════════════════════════{Colors.RESET}\n")

    print(f"{Colors.YELLOW}Bu işlem şu sistem bileşenlerini temizleyecektir:{Colors.RESET}")
    print(" 1. Global AI Kancaları ve Kuralları (Antigravity, Cursor, Codex, Claude)")
    print(" 2. Günlük Sabah Brifingi Görev Zamanlayıcı / Cron Kaydı")
    print(" 3. Masaüstü Başlatıcı Kısayolları")
    print(" 4. MCP Sunucu Kayıtları\n")

    if not args.purge_vault:
        print(f"{Colors.GREEN}{Colors.BOLD}GÜVENCE:{Colors.RESET} İkinci beyin kasanız ve notlarınız {Colors.BOLD}SİLİNMEYECEKTİR{Colors.RESET} (güvenle korunacaktır).\n")
    else:
        print(f"{Colors.RED}{Colors.BOLD}UYARI:{Colors.RESET} --purge-vault seçeneği belirtildi. Kasa dizini de silinecek!\n")

    if not args.non-interactive:
        confirm = _prompt_user("Kaldırma işlemine devam etmek istiyor musunuz? [e/H]", "h")
        if confirm.lower() not in ("e", "evet", "y", "yes"):
            print(f"{Colors.YELLOW}Kaldırma işlemi iptal edildi.{Colors.RESET}")
            return 0

    print(f"\n{Colors.CYAN}• Global entegrasyonlar temizleniyor...{Colors.RESET}")
    items = []
    items.extend(remove_global_integrations())
    items.extend(remove_scheduled_tasks())
    items.extend(remove_desktop_shortcuts())
    items.extend(remove_mcp_config())

    if args.purge_vault:
        vault_path = None
        if args.vault_path:
            vault_path = Path(args.vault_path).expanduser().resolve()
        else:
            default_path = Path.home() / "Documents" / "RespectedOS"
            if default_path.is_dir():
                vault_path = default_path

        if vault_path and vault_path.is_dir():
            if not args.non-interactive:
                confirm_purge = _prompt_user(f"'{vault_path}' kasası ve tüm notlar TAMAMEN SİLİNECEK. Emin misiniz? [evet/HAYIR]", "hayir")
                if confirm_purge.lower() in ("evet", "yes"):
                    shutil.rmtree(vault_path, ignore_errors=True)
                    items.append(f"Kasa dizini tamamen silindi: {vault_path}")
                else:
                    print(f"{Colors.YELLOW}Kasa silinmedi, korundu.{Colors.RESET}")
            else:
                shutil.rmtree(vault_path, ignore_errors=True)
                items.append(f"Kasa dizini tamamen silindi: {vault_path}")

    print("")
    if items:
        for item in items:
            print(f"{Colors.GREEN}✔{Colors.RESET} {item}")
    else:
        print(f"{Colors.DIM}Sistemde temizlenecek aktif bir global kayıt bulunamadı (zaten temiz).{Colors.RESET}")

    print(f"\n{Colors.GREEN}{Colors.BOLD}Respected Brain entegrasyonları sisteminizden başarıyla kaldırıldı.{Colors.RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
