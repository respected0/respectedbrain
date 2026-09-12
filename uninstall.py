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


RESPECTED_SKILLS = {
    "ajan-gecmis-tara",
    "beyin-doktor",
    "beyin-meydan-oku",
    "beyin-oruntu",
    "gecmis-import",
    "inbox-duzenle",
    "obsidian-layout",
    "otonom-arastirma",
    "yazilim-kalite",
}


_LEGACY_BRAND = "res" + "pot"
_LEGACY_BRAND_UPPER = "RES" + "POT"


def _clean_rule_file(path: Path, label: str) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        new_text = re.sub(
            rf"<!-- (RESPECTED-GLOBAL|AVENOX-GLOBAL|{_LEGACY_BRAND_UPPER}-GLOBAL):BEGIN -->.*?<!-- \1:END -->\s*",
            "",
            text,
            flags=re.DOTALL,
        )
        if new_text.strip() == "":
            path.unlink(missing_ok=True)
            return f"{label} kural dosyası silindi: {path}"
        elif new_text != text:
            path.write_text(new_text, encoding="utf-8")
            return f"{label} kuralı temizlendi: {path}"
    except Exception:
        pass
    return None


def _clean_skills_from(roots: list[Path], label: str) -> list[str]:
    removed = []
    for root in roots:
        if not root.is_dir():
            continue
        for skill_name in RESPECTED_SKILLS:
            skill_dir = root / skill_name
            if skill_dir.is_dir():
                shutil.rmtree(skill_dir, ignore_errors=True)
                removed.append(f"{label} skill silindi: {skill_dir}")
        try:
            if root.is_dir() and not any(root.iterdir()):
                root.rmdir()
        except OSError:
            pass
    return removed


def _clean_hooks_file(path: Path, label: str) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        changed = False

        keywords = ("respected", "avenox", _LEGACY_BRAND, "beyin", "bridge.py", "lifecycle.py")

        # Format 3: Namespace dict { "respected-brain": { ... } }
        for key in list(data.keys()):
            if any(brand in key.lower() for brand in ("respected", "avenox", _LEGACY_BRAND, "beyin")):
                data.pop(key, None)
                changed = True

        # Format 1: Direct event dict { "SessionStart": [ ... ] }
        for event, handlers in list(data.items()):
            if isinstance(handlers, list):
                filtered = [
                    h for h in handlers
                    if not any(k in str(h).lower() for k in keywords)
                ]
                if len(filtered) != len(handlers):
                    data[event] = filtered
                    changed = True

        # Format 2: Nested under "hooks" { "hooks": { "SessionStart": [ ... ] } }
        if isinstance(data.get("hooks"), dict):
            for event, handlers in list(data["hooks"].items()):
                if isinstance(handlers, list):
                    filtered = [
                        h for h in handlers
                        if not any(k in str(h).lower() for k in keywords)
                    ]
                    if len(filtered) != len(handlers):
                        data["hooks"][event] = filtered
                        changed = True

        # Prune empty lists / dictionaries
        for event in list(data.keys()):
            if isinstance(data[event], list) and not data[event]:
                data.pop(event, None)
        if isinstance(data.get("hooks"), dict):
            for event in list(data["hooks"].keys()):
                if isinstance(data["hooks"][event], list) and not data["hooks"][event]:
                    data["hooks"].pop(event, None)
            if not data["hooks"]:
                data.pop("hooks", None)

        if changed:
            if not data:
                path.unlink(missing_ok=True)
                return f"{label} kancaları tamamen temizlendi (dosya silindi): {path}"
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return f"{label} kancaları temizlendi: {path}"
    except Exception:
        pass
    return None


def _clean_wsl_integrations() -> list[str]:
    """Clean global rules, hooks, and skills inside WSL if WSL is present."""
    if os.name != "nt" or not shutil.which("wsl.exe"):
        return []
    cleaned = []
    try:
        script_path = Path(__file__).resolve()
        drive = script_path.drive[0].lower()
        posix_path = f"/mnt/{drive}/" + script_path.as_posix()[3:]
        res = subprocess.run(
            ["wsl.exe", "-e", "python3", posix_path, "--wsl-worker"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                line = line.strip()
                if line:
                    cleaned.append(f"WSL: {line}")
        elif res.stderr:
            cleaned.append(f"WSL temizleme uyarısı: {res.stderr.strip()}")
    except Exception as e:
        cleaned.append(f"WSL temizleme hatası: {e}")
    return cleaned


def remove_global_integrations(clean_wsl: bool | None = None) -> list[str]:
    """Remove global rules, hooks, and skills across Antigravity, Cursor, Codex, and Claude."""
    cleaned = []
    home = Path.home()

    # 1. Antigravity (~/.gemini)
    rule_msg = _clean_rule_file(home / ".gemini" / "GEMINI.md", "Antigravity global")
    if rule_msg:
        cleaned.append(rule_msg)

    hook_msg = _clean_hooks_file(home / ".gemini" / "config" / "hooks.json", "Antigravity")
    if hook_msg:
        cleaned.append(hook_msg)

    cleaned.extend(_clean_skills_from([home / ".gemini" / "config" / "skills"], "Antigravity"))

    # 2. Cursor (~/.cursor)
    cursor_rule = home / ".cursor" / "rules" / "respected-brain.mdc"
    if cursor_rule.is_file():
        cursor_rule.unlink(missing_ok=True)
        cleaned.append(f"Cursor global kuralı silindi: {cursor_rule}")

    cursor_rule_legacy = home / ".cursor" / "rules" / "avenox-beyin.mdc"
    if cursor_rule_legacy.is_file():
        cursor_rule_legacy.unlink(missing_ok=True)
        cleaned.append(f"Cursor eski global kuralı silindi: {cursor_rule_legacy}")

    hook_msg = _clean_hooks_file(home / ".cursor" / "hooks.json", "Cursor")
    if hook_msg:
        cleaned.append(hook_msg)

    cleaned.extend(_clean_skills_from([home / ".cursor" / "skills"], "Cursor"))

    # 3. Codex (~/.codex & ~/.agents)
    rule_msg = _clean_rule_file(home / ".codex" / "AGENTS.md", "Codex global")
    if rule_msg:
        cleaned.append(rule_msg)

    rule_msg_agents = _clean_rule_file(home / ".agents" / "AGENTS.md", "Agents global")
    if rule_msg_agents:
        cleaned.append(rule_msg_agents)

    hook_msg = _clean_hooks_file(home / ".codex" / "hooks.json", "Codex")
    if hook_msg:
        cleaned.append(hook_msg)

    cleaned.extend(_clean_skills_from([home / ".agents" / "skills", home / ".codex" / "skills"], "Codex"))

    # 4. Claude (~/.claude)
    rule_msg = _clean_rule_file(home / ".claude" / "CLAUDE.md", "Claude global")
    if rule_msg:
        cleaned.append(rule_msg)

    hook_msg = _clean_hooks_file(home / ".claude" / "settings.json", "Claude")
    if hook_msg:
        cleaned.append(hook_msg)

    cleaned.extend(_clean_skills_from([home / ".claude" / "skills"], "Claude"))

    if clean_wsl is None:
        clean_wsl = os.name == "nt" and "respected-uninstall-test" not in str(home) and home.exists()

    if clean_wsl:
        cleaned.extend(_clean_wsl_integrations())

    return cleaned


def remove_scheduled_tasks() -> list[str]:
    """Remove Windows scheduled tasks or cron jobs for morning briefings."""
    cleaned = []
    if os.name == "nt" or shutil.which("schtasks.exe"):
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
    """Remove Respected Vault MCP server registration from all known editors."""
    cleaned = []
    home = Path.home()

    mcp_configs = [
        # Antigravity IDE
        home / ".gemini" / "antigravity-ide" / "mcp_config.json",
        home / ".gemini" / "config" / "mcp_config.json",
        # Claude Desktop
        home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
        home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        home / ".config" / "Claude" / "claude_desktop_config.json",
        # Claude Code
        home / ".claude.json",
        # Cursor IDE
        home / ".cursor" / "mcp.json",
        # Windsurf IDE
        home / ".codeium" / "windsurf" / "mcp_config.json",
    ]

    for cfg in mcp_configs:
        if cfg.is_file():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8", errors="replace"))
                servers = data.get("mcpServers", {})
                changed = False
                for s_name in ("respected-vault", "respected-vault-mcp", "respected_vault"):
                    if s_name in servers:
                        servers.pop(s_name, None)
                        changed = True
                if changed:
                    data["mcpServers"] = servers
                    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    cleaned.append(f"MCP kaydı kaldırıldı: {cfg}")
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
    parser.add_argument(
        "--wsl-worker",
        action="store_true",
        help="WSL içinde sessizce global entegrasyonları temizlemek için arka plan modu",
    )

    args = parser.parse_args(argv)

    if args.wsl_worker:
        items = []
        items.extend(remove_global_integrations(clean_wsl=False))
        items.extend(remove_scheduled_tasks())
        items.extend(remove_mcp_config())
        for item in items:
            print(item)
        return 0

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

    if not args.non_interactive:
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
            if not args.non_interactive:
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
