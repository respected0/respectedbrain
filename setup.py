#!/usr/bin/env python3
"""Respected Brain v0.0.1 — Evrensel Çapraz Platform Kurulum, Bakım & Yönetim Motoru.

Windows, macOS ve Linux üzerinde tek merkezden çalışır:
  - Mevcut kasayı otomatik tespit eder
  - Kurulum (Install), Güncelleme (Update), Onarım (Repair), Değiştirme (Modify) ve Kaldırma (Uninstall)
  - Tüm platform başlatıcılarının (setup.exe, setup.command, setup) ortak çekirdeğidir.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = (REPO_ROOT / "runtime" / "scripts") if (REPO_ROOT / "runtime" / "scripts").is_dir() else (REPO_ROOT / "scripts")
INSTALLER_DIR = REPO_ROOT / "installer"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


_configure_console()


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


def _default_vault_path() -> Path:
    home = Path.home()
    documents = home / "Documents"
    if documents.is_dir():
        return documents / "RespectedOS"
    return home / "RespectedOS"


def _detect_existing_vault(custom_path: Path | None = None) -> Path | None:
    candidates = []
    if custom_path:
        candidates.append(custom_path)
    candidates.extend([
        _default_vault_path(),
        Path.home() / "RespectedOS",
    ])
    for cand in candidates:
        if cand.is_dir() and (
            (cand / ".respectedbrain-version").is_file()
            or (cand / ".beyin-version").is_file()
            or (cand / ".beyin").is_dir()
            or (cand / "scripts").is_dir()
        ):
            return cand
    return None


def _print_banner() -> None:
    banner = f"""{Colors.CYAN}{Colors.BOLD}
  ██████╗ ███████╗███████╗██████╗ ███████╗ ██████╗████████╗███████╗██████╗ 
  ██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔════╝██╔══██╗
  ██████╔╝█████╗  ███████╗██████╔╝█████╗  ██║        ██║   █████╗  ██║  ██║
  ██╔══██╗██╔══╝  ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══╝  ██║  ██║
  ██║  ██║███████╗███████║██║     ███████╗╚██████╗   ██║   ███████╗██████╔╝
  ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚══════╝╚═════╝ 
{Colors.RESET}
{Colors.BOLD}Respected Brain v0.0.1 — Evrensel Kurulum & Yönetim Merkezi{Colors.RESET}
{Colors.DIM}Yapay zekalarla konuşan, süreklilik kuran, yerel kişisel ikinci beyin.{Colors.RESET}
"""
    print(banner)


def run_install(extra_args: list[str]) -> int:
    install_script = INSTALLER_DIR / "install.py"
    cmd = [sys.executable, str(install_script), *extra_args]
    return subprocess.run(cmd, cwd=REPO_ROOT).returncode


def run_update(vault_path: Path, extra_args: list[str]) -> int:
    update_script = INSTALLER_DIR / "update.py"
    platform_name = "windows-native" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
    cmd = [sys.executable, str(update_script), str(vault_path), "--platform", platform_name, "--force", "--apply", *extra_args]
    print(f"\n{Colors.CYAN}[*] Respected Brain kasası güncelleniyor: {vault_path}{Colors.RESET}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    if proc.returncode == 0:
        print(f"\n{Colors.GREEN}✔ Güncelleme başarıyla tamamlandı! Notlarınız güvenle korundu.{Colors.RESET}")
        run_dashboard(vault_path)
    return proc.returncode


def run_repair(vault_path: Path) -> int:
    platform_name = "windows-native" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
    print(f"\n{Colors.CYAN}[*] Sistem kancaları ve şablonlar onarılıyor: {vault_path}{Colors.RESET}")
    cmd1 = [sys.executable, str(SCRIPTS_DIR / "update_respected.py"), str(vault_path), "--platform", platform_name, "--force", "--apply"]
    subprocess.run(cmd1, cwd=REPO_ROOT)
    cmd2 = [sys.executable, str(SCRIPTS_DIR / "install_global.py"), str(vault_path), "--home", str(Path.home()), "--platform", platform_name, "--apply"]
    subprocess.run(cmd2, cwd=REPO_ROOT)
    mcp_script = SCRIPTS_DIR / "vault_mcp_server.py"
    if mcp_script.is_file():
        cmd3 = [sys.executable, str(mcp_script), "--vault", str(vault_path), "--register"]
        subprocess.run(cmd3, cwd=REPO_ROOT)
    print(f"\n{Colors.GREEN}✔ Onarım tamamlandı! Kancalar, MCP sunucusu ve arama motoru yenilendi.{Colors.RESET}")
    return 0


def run_uninstall(vault_path: Path, extra_args: list[str]) -> int:
    uninstall_script = INSTALLER_DIR / "uninstall.py"
    cmd = [sys.executable, str(uninstall_script), str(vault_path), *extra_args]
    return subprocess.run(cmd, cwd=REPO_ROOT).returncode


def run_dashboard(vault_path: Path) -> None:
    dashboard_script = SCRIPTS_DIR / "dashboard.py"
    if dashboard_script.is_file():
        print(f"\n{Colors.CYAN}[*] Kontrol Paneli başlatılıyor: http://localhost:8520{Colors.RESET}")
        try:
            subprocess.Popen([sys.executable, str(dashboard_script), "--vault", str(vault_path), "--open"])
        except Exception:
            pass


def _interactive_menu(vault_path: Path) -> int:
    print(f"{Colors.GREEN}[✓] Mevcut Respected Brain kasası tespit edildi:{Colors.RESET} {vault_path}\n")
    print(f"{Colors.BOLD}Lütfen gerçekleştirmek istediğiniz işlemi seçin:{Colors.RESET}")
    print("  [1] 🔄 Güncelle (Update) — Kasayı son sürüme güncelle (Notlarınız korunur)")
    print("  [2] 🛠️ Onar (Repair) — Eksik kancaları, FTS5 indeksini ve şablonları tamir et")
    print("  [3] ⚙️ Değiştir (Modify) — Model önceliğini ve kullanıcı ayarlarını baştan yapılandır")
    print("  [4] 🗑️ Kaldır (Uninstall) — Zamanlanmış görevleri ve kısayolları sistemden kaldır")
    print("  [5] 🚀 Kontrol Panelini Aç (Web Gateway — http://localhost:8520)")
    print("  [0] Çıkış\n")

    try:
        choice = input(f"{Colors.BOLD}Seçiminiz [1-5]: {Colors.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nİşlem iptal edildi.")
        return 0

    if choice == "1":
        return run_update(vault_path, [])
    elif choice == "2":
        return run_repair(vault_path)
    elif choice == "3":
        return run_install(["--vault-path", str(vault_path)])
    elif choice == "4":
        return run_uninstall(vault_path, [])
    elif choice == "5":
        run_dashboard(vault_path)
        return 0
    else:
        print("Çıkış yapıldı.")
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Respected Brain — Evrensel Kurulum, Bakım ve Yönetim Sistemi (v0.0.1)",
        add_help=False,
    )
    parser.add_argument("--help", "-h", action="store_true", help="Yardım mesajını göster")
    parser.add_argument("--install", action="store_true", help="Doğrudan yeni kurulum sihirbazını çalıştır")
    parser.add_argument("--update", action="store_true", help="Doğrudan güncelleme modunda çalış")
    parser.add_argument("--repair", action="store_true", help="Doğrudan onarım modunda çalış")
    parser.add_argument("--modify", action="store_true", help="Doğrudan ayar değiştirme modunda çalış")
    parser.add_argument("--uninstall", action="store_true", help="Doğrudan kaldırma modunda çalış")
    parser.add_argument("--dashboard", action="store_true", help="Kontrol panelini başlat")
    parser.add_argument("--vault-path", type=Path, default=None, help="Hedef kasa dizini")

    known_args, remaining_args = parser.parse_known_args(argv)

    if known_args.vault_path and "--vault-path" not in remaining_args:
        remaining_args = ["--vault-path", str(known_args.vault_path), *remaining_args]

    if known_args.help:
        _print_banner()
        parser.print_help()
        return 0

    vault = _detect_existing_vault(known_args.vault_path)

    # Direct action flags
    if known_args.install:
        return run_install(remaining_args)

    if known_args.update:
        target = vault or known_args.vault_path or _default_vault_path()
        return run_update(target, remaining_args)

    if known_args.repair:
        target = vault or known_args.vault_path or _default_vault_path()
        return run_repair(target)

    if known_args.modify:
        target = vault or known_args.vault_path or _default_vault_path()
        return run_install(["--vault-path", str(target), *remaining_args])

    if known_args.uninstall:
        target = vault or known_args.vault_path or _default_vault_path()
        return run_uninstall(target, remaining_args)

    if known_args.dashboard:
        target = vault or known_args.vault_path or _default_vault_path()
        run_dashboard(target)
        return 0

    # Interactive flow
    _print_banner()

    if vault:
        return _interactive_menu(vault)
    else:
        print(f"{Colors.CYAN}[*] Yeni kurulum sihirbazı başlatılıyor...{Colors.RESET}\n")
        return run_install(remaining_args)


if __name__ == "__main__":
    raise SystemExit(main())
