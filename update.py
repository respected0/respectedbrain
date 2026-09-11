#!/usr/bin/env python3
"""Respected Brain v0.0.1 — Cross-Platform Interactive & Automated Vault Updater."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
UPDATE_SCRIPT = SCRIPTS_DIR / "update_respected.py"


def _configure_console_output() -> None:
    """Keep Windows OEM consoles from aborting on non-ASCII output."""
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


def _detect_default_vault() -> Path | None:
    """Detect default vault path across common locations."""
    home = Path.home()
    candidates = [
        home / "Documents" / "RespectedOS",
        home / "RespectedOS",
        Path("/mnt/c/Users") / home.name / "Documents" / "RespectedOS",
    ]
    for candidate in candidates:
        if candidate.is_dir() and (
            (candidate / ".respectedbrain-version").is_file()
            or (candidate / ".beyin-version").is_file()
            or (candidate / ".beyin-multi-version").is_file()
            or (candidate / "🔮 850-Companion").is_dir()
        ):
            return candidate
    return None


def _prompt_user(prompt: str, default: str = "") -> str:
    default_text = f" [{default}]" if default else ""
    try:
        val = input(f"{Colors.BOLD}{prompt}{Colors.RESET}{default_text}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{Colors.YELLOW}Güncelleme iptal edildi.{Colors.RESET}")
        sys.exit(1)
    return val if val else default


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Respected Brain — Etkileşimli ve Otomatik Vault Güncelleyici"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Güncellenecek vault dizini (boş bırakılırsa taranır veya sorulur)",
    )
    parser.add_argument(
        "--vault-path",
        default=None,
        help="Hedef vault dizini yolu",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Değişiklikleri onay sormadan doğrudan uygula",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Aynı sürümde olsa dahi yönetilen dosyaları yeniden senkronize et",
    )
    parser.add_argument(
        "--platform",
        choices=["auto", "portable", "windows-wsl", "windows-native"],
        default="auto",
        help="Çalışma ortamı platform profili (varsayılan: auto)",
    )
    parser.add_argument(
        "--summary-provider",
        choices=["auto", "claude", "codex", "cursor", "antigravity"],
        default="auto",
        help="Özetleme için tercih edilen varsayılan model sağlayıcısı",
    )

    args = parser.parse_args(argv)

    print(f"{Colors.CYAN}{Colors.BOLD}════════════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}          Respected Brain v0.0.1 — Vault Güncelleyici               {Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}════════════════════════════════════════════════════════════════════{Colors.RESET}\n")

    vault_str = args.target or args.vault_path
    if not vault_str:
        detected = _detect_default_vault()
        default_str = str(detected) if detected else ""
        vault_str = _prompt_user("Hedef Vault Dizinini girin", default_str)

    if not vault_str:
        print(f"{Colors.RED}Hata: Geçerli bir vault dizini belirtilmedi.{Colors.RESET}")
        return 1

    vault_path = Path(vault_str).expanduser().resolve()
    if not vault_path.is_dir():
        print(f"{Colors.RED}Hata: '{vault_path}' dizini mevcut değil.{Colors.RESET}")
        return 1

    if not UPDATE_SCRIPT.is_file():
        print(f"{Colors.RED}Hata: '{UPDATE_SCRIPT}' bulunamadı.{Colors.RESET}")
        return 1

    # 1. Aşama: Önizleme (Preview)
    print(f"{Colors.CYAN}• Kasa analiz ediliyor ve güncelleme önizlemesi hazırlanıyor...{Colors.RESET}")
    preview_cmd = [
        sys.executable,
        str(UPDATE_SCRIPT),
        str(vault_path),
        "--platform",
        args.platform,
        "--summary-provider",
        args.summary_provider,
    ]
    if args.force:
        preview_cmd.append("--force")

    preview_res = subprocess.run(preview_cmd)
    if preview_res.returncode != 0:
        print(f"\n{Colors.RED}Önizleme başarısız oldu veya kasa güncellenemez durumda.{Colors.RESET}")
        return preview_res.returncode

    # 2. Aşama: Uygulama (Apply)
    if not args.apply:
        print("")
        confirm = _prompt_user("Yukarıdaki değişiklikler uygulansın mı? [E/h]", "E")
        if confirm.lower() not in ("e", "evet", "y", "yes"):
            print(f"{Colors.YELLOW}Güncelleme uygulanmadı (iptal edildi).{Colors.RESET}")
            return 0

    print(f"\n{Colors.CYAN}• Güncelleme güvenli işlemle (transactional) uygulanıyor...{Colors.RESET}")
    apply_cmd = preview_cmd + ["--apply"]
    apply_res = subprocess.run(apply_cmd)
    if apply_res.returncode == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✔ Tebrikler! Respected Brain başarıyla güncellendi (v0.0.1).{Colors.RESET}")
        print(f"{Colors.DIM}Not: AI asistanınızda 'beyin doktor' çalıştırarak sistem sağlığını teyit edebilirsiniz.{Colors.RESET}\n")
    else:
        print(f"\n{Colors.RED}Güncelleme sırasında hata oluştu (önceki yedekten geri yüklendi).{Colors.RESET}")

    return apply_res.returncode


if __name__ == "__main__":
    sys.exit(main())
