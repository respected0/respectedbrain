#!/usr/bin/env python3
"""Respected Brain v0.0.1 — Cross-Platform Interactive & Automated Installer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = REPO_ROOT / "template"
SCRIPTS_DIR = REPO_ROOT / "scripts"

SUPPORTED_PROVIDERS = ("antigravity", "codex", "claude", "cursor")
PROVIDER_COMMANDS = {
    "antigravity": "agy",
    "codex": "codex",
    "claude": "claude",
    "cursor": "cursor-agent",
}


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


def _detect_installed_providers() -> dict[str, bool]:
    detected = {}
    for provider, cmd in PROVIDER_COMMANDS.items():
        found = shutil.which(cmd) or shutil.which(f"{cmd}.exe") or shutil.which(f"{cmd}.cmd")
        detected[provider] = bool(found)
    return detected


def _default_vault_path() -> Path:
    home = Path.home()
    documents = home / "Documents"
    if documents.is_dir():
        return documents / "RespectedOS"
    return home / "RespectedOS"


def _prompt_user(prompt: str, default: str = "") -> str:
    default_text = f" [{default}]" if default else ""
    try:
        val = input(f"{Colors.BOLD}{prompt}{Colors.RESET}{default_text}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{Colors.YELLOW}Kurulum kullanıcı tarafından iptal edildi.{Colors.RESET}")
        sys.exit(1)
    return val if val else default


def create_desktop_shortcut(
    os_name: str,
    vault_path: Path,
    desktop_dir_override: Path | None = None,
) -> Path | None:
    """Create a desktop shortcut for opening the vault directly in Obsidian."""
    import urllib.parse

    vault_name = vault_path.name
    encoded_vault = urllib.parse.quote(vault_name)
    uri = f"obsidian://open?vault={encoded_vault}"

    desktop_dir = desktop_dir_override
    if desktop_dir is None:
        if os.name == "nt":
            # 1. Check Windows Shell Folders in Registry (handles OneDrive & custom Desktop locations)
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
                )
                val, _ = winreg.QueryValueEx(key, "Desktop")
                winreg.CloseKey(key)
                desktop_cand = Path(os.path.expandvars(val))
                if desktop_cand.is_dir():
                    desktop_dir = desktop_cand
            except Exception:
                pass

            # 2. Fallbacks for Windows
            if desktop_dir is None:
                userprofile = os.environ.get("USERPROFILE")
                if userprofile:
                    onedrive_desktop = Path(userprofile) / "OneDrive" / "Desktop"
                    onedrive_tr = Path(userprofile) / "OneDrive" / "Masaüstü"
                    std_desktop = Path(userprofile) / "Desktop"
                    std_tr = Path(userprofile) / "Masaüstü"
                    for cand in (onedrive_desktop, onedrive_tr, std_desktop, std_tr):
                        if cand.is_dir():
                            desktop_dir = cand
                            break
        else:
            # Check WSL mounting Windows Desktop
            wsl_cand = None
            if Path("/mnt/c/Users").is_dir():
                for user_dir in Path("/mnt/c/Users").iterdir():
                    if user_dir.is_dir() and user_dir.name.lower() not in ("public", "default", "all users"):
                        for sub in ("OneDrive/Desktop", "OneDrive/Masaüstü", "Desktop", "Masaüstü"):
                            cand = user_dir / sub
                            if cand.is_dir():
                                wsl_cand = cand
                                break
                    if wsl_cand:
                        break
            if wsl_cand:
                desktop_dir = wsl_cand
            else:
                home_desktop = Path.home() / "Desktop"
                if home_desktop.is_dir():
                    desktop_dir = home_desktop

    if not desktop_dir or not desktop_dir.is_dir():
        return None

    try:
        is_windows_target = os.name == "nt" or str(desktop_dir).startswith("/mnt/c/")
        if is_windows_target or sys.platform == "darwin":
            shortcut_file = desktop_dir / f"{vault_name}.url"
            content = (
                "[{000214A0-0000-0000-C000-000000000046}]\n"
                "Prop3=19,0\n"
                "[InternetShortcut]\n"
                "IDList=\n"
                f"URL={uri}\n"
            )
            shortcut_file.write_text(content, encoding="utf-8")
            return shortcut_file
        else:
            # Linux .desktop file
            shortcut_file = desktop_dir / f"{vault_name}.desktop"
            content = (
                "[Desktop Entry]\n"
                f"Name={vault_name} (Obsidian)\n"
                f"Comment={vault_name} İkinci Beyin Kasa Kısayolu\n"
                f"Exec=xdg-open \"{uri}\"\n"
                "Icon=obsidian\n"
                "Terminal=false\n"
                "Type=Application\n"
                "Categories=Office;Utility;\n"
            )
            shortcut_file.write_text(content, encoding="utf-8")
            shortcut_file.chmod(0o755)
            return shortcut_file
    except OSError:
        return None


def install_vault(
    vault_path: Path,
    user_name: str,
    user_bio: str,
    companion: str,
    os_name: str,
    summary_provider: str,
    provider_priority: list[str] | None = None,
    install_global: bool = False,
    install_schedule: bool = False,
    schedule_time: str = "08:00",
    desktop_shortcut: bool = False,
    desktop_dir_override: Path | None = None,
    environment: str | None = None,
    quiet: bool = False,
) -> int:
    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    vault_path = vault_path.expanduser().resolve()
    log(f"\n{Colors.CYAN}>> Kurulum Başlatılıyor:{Colors.RESET} {vault_path}")

    # Preflight target
    if vault_path.exists():
        if not vault_path.is_dir():
            print(f"{Colors.RED}HATA: Hedef yol bir klasör değil: {vault_path}{Colors.RESET}", file=sys.stderr)
            return 1
        if any(vault_path.iterdir()):
            print(f"{Colors.RED}HATA: Hedef klasör boş değil: {vault_path}{Colors.RESET}", file=sys.stderr)
            return 1
    else:
        vault_path.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Copy template
        log(f"{Colors.DIM}• Şablon dosyaları aktarılıyor...{Colors.RESET}")
        for item in TEMPLATE_DIR.iterdir():
            target_item = vault_path / item.name
            if item.is_dir():
                shutil.copytree(item, target_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target_item)

        # 2. Copy scripts
        log(f"{Colors.DIM}• Yardımcı motor betikleri kopyalanıyor...{Colors.RESET}")
        target_scripts = vault_path / "scripts"
        target_scripts.mkdir(parents=True, exist_ok=True)
        excluded_scripts = {"install-windows.ps1", "upstream_sync.sh", "install.py"}
        for script_file in SCRIPTS_DIR.glob("*.py"):
            if script_file.name not in excluded_scripts:
                shutil.copy2(script_file, target_scripts / script_file.name)

        # 3. Create required runtime dirs
        (vault_path / "daily").mkdir(exist_ok=True)
        (vault_path / "knowledge" / "concepts" / "core").mkdir(parents=True, exist_ok=True)
        (vault_path / "knowledge" / "concepts" / "finance").mkdir(parents=True, exist_ok=True)
        (vault_path / "knowledge" / "connections").mkdir(parents=True, exist_ok=True)

        # 4. Resolve placeholders
        log(f"{Colors.DIM}• Kimlik ve profil değişkenleri işleniyor...{Colors.RESET}")
        today_str = time.strftime("%Y-%m-%d")
        replacements = {
            "{{OS_NAME}}": os_name,
            "{{USER_NAME}}": user_name,
            "{{USER_BIO}}": user_bio,
            "{{COMPANION}}": companion,
            "{{VAULT_PATH}}": str(vault_path),
            "{{TODAY}}": today_str,
        }

        text_extensions = {".md", ".json", ".py", ".sh", ".ps1", ".txt", ".yml", ".yaml"}
        for root, _dirs, files in os.walk(vault_path):
            for file_name in files:
                file_path = Path(root) / file_name
                if file_path.suffix.lower() in text_extensions or file_name.startswith("."):
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        updated = content
                        for placeholder, val in replacements.items():
                            updated = updated.replace(placeholder, val)
                        if updated != content:
                            file_path.write_text(updated, encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        pass

        # 5. Write .beyin/config.json
        platform_name = "windows-native" if os.name == "nt" else "portable"
        config_data = {
            "summary_provider": summary_provider,
            "platform": platform_name,
            "python_command": ["python"] if os.name == "nt" else ["python3"],
        }
        if environment:
            config_data["environment"] = environment
        if provider_priority:
            config_data["provider_priority"] = provider_priority

        config_path = vault_path / ".beyin" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 6. Render integrations
        log(f"{Colors.DIM}• Multi-AI entegrasyonları derleniyor...{Colors.RESET}")
        render_cmd = [
            sys.executable,
            str(target_scripts / "render_integrations.py"),
            "--root",
            str(vault_path),
            "--platform",
            platform_name,
        ]
        result = subprocess.run(render_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"{Colors.RED}HATA: Entegrasyon render başarısız:{Colors.RESET}\n{result.stderr}", file=sys.stderr)
            return result.returncode

        # 7. Optional global install
        if install_global:
            log(f"{Colors.DIM}• Global AI kural bağlantıları kuruluyor...{Colors.RESET}")
            if shutil.which("agy") or shutil.which("agy.exe"):
                agy_global = target_scripts / "install_antigravity_global.py"
                if agy_global.is_file():
                    subprocess.run([sys.executable, str(agy_global)], check=False, capture_output=True)
            global_installer = target_scripts / "install_global.py"
            if global_installer.is_file():
                subprocess.run([sys.executable, str(global_installer)], check=False, capture_output=True)

        # 8. Optional Desktop shortcut
        created_shortcut = None
        if desktop_shortcut:
            log(f"{Colors.DIM}• Masaüstü Obsidian kısayolu oluşturuluyor...{Colors.RESET}")
            created_shortcut = create_desktop_shortcut(
                os_name=os_name,
                vault_path=vault_path,
                desktop_dir_override=desktop_dir_override,
            )

        # 9. Optional Morning Briefing Schedule
        if install_schedule:
            log(f"{Colors.DIM}• Sabah brifingi ve bilgi derlemesi zamanlayıcısı kuruluyor ({schedule_time})...{Colors.RESET}")
            schedule_script = target_scripts / "install_briefing_schedule.py"
            if schedule_script.is_file():
                schedule_cmd = [
                    sys.executable,
                    str(schedule_script),
                    str(vault_path),
                    "--home",
                    str(Path.home()),
                    "--platform",
                    platform_name,
                    "--time",
                    schedule_time,
                    "--apply",
                ]
                subprocess.run(schedule_cmd, check=False, capture_output=True)

        log(f"\n{Colors.GREEN}{Colors.BOLD}✔ Tebrikler! {os_name} başarıyla kuruldu!{Colors.RESET}")
        log(f"  {Colors.BOLD}Konum:{Colors.RESET} {vault_path}")
        log(f"  {Colors.BOLD}Düşünme Ortağı:{Colors.RESET} {companion}")
        log(f"  {Colors.BOLD}Özetleyici Modeli:{Colors.RESET} {summary_provider}")
        if provider_priority:
            log(f"  {Colors.BOLD}Model Öncelik Sırası:{Colors.RESET} {' -> '.join(provider_priority)}")
        if environment:
            log(f"  {Colors.BOLD}Ortam:{Colors.RESET} {environment}")
        if created_shortcut:
            log(f"  {Colors.BOLD}Masaüstü Kısayolu:{Colors.RESET} {created_shortcut}")
        if install_schedule:
            log(f"  {Colors.BOLD}Sabah Brifingi & Bilgi Derlemesi:{Colors.RESET} Aktif ({schedule_time})")
        log(f"\n{Colors.CYAN}Obsidian ile Başlayın:{Colors.RESET}")
        log(f"  1. Obsidian'ı açın.")
        log(f"  2. 'Open folder as vault' seçeneğine tıklayın.")
        log(f"  3. Şu klasörü seçin: {Colors.BOLD}{vault_path}{Colors.RESET}\n")
        return 0

    except Exception as exc:
        print(f"{Colors.RED}Kurulum sırasında beklenmeyen hata oluştu: {exc}{Colors.RESET}", file=sys.stderr)
        return 1


def _interactive_wizard() -> int:
    detected = _detect_installed_providers()

    banner = f"""
{Colors.CYAN}{Colors.BOLD}
  ██████╗ ███████╗███████╗██████╗ ███████╗ ██████╗████████╗███████╗██████╗ 
  ██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔════╝██╔══██╗
  ██████╔╝█████╗  ███████╗██████╔╝█████╗  ██║        ██║   █████╗  ██║  ██║
  ██╔══██╗██╔══╝  ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══╝  ██║  ██║
  ██║  ██║███████╗███████║██║     ███████╗╚██████╗   ██║   ███████╗██████╔╝
  ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚══════╝╚═════╝ 
{Colors.RESET}
{Colors.BOLD}Respected Brain v0.0.1 — İnteraktif Kurulum Sihirbazı{Colors.RESET}
{Colors.DIM}Yapay zekalarla konuşan, süreklilik kuran, yerel kişisel ikinci beyin.{Colors.RESET}
"""
    print(banner)

    # 1. Vault Path
    default_vault = _default_vault_path()
    raw_path = _prompt_user("1. Kasa nereye kurulsun?", str(default_vault))
    vault_path = Path(raw_path)

    # 2. User info
    default_user = os.environ.get("USERNAME") or os.environ.get("USER") or "Furkan"
    user_name = _prompt_user("2. Adınız / Hitap şekli?", default_user)
    user_bio = _prompt_user("3. Kısa rol / uzmanlık alanı?", "Geliştirici & Mühendis")

    # 3. Companion & OS name
    companion = _prompt_user("4. Düşünme ortağınızın (Companion) adı?", "Jarvis")
    os_name = _prompt_user("5. Kasa işletim sistemi adı?", "RespectedOS")

    # 4. Provider Detection Display
    print(f"\n{Colors.BOLD}Sistemde Algılanan AI CLI Araçları:{Colors.RESET}")
    for p in SUPPORTED_PROVIDERS:
        status = f"{Colors.GREEN}[✓] Kurulu{Colors.RESET}" if detected[p] else f"{Colors.DIM}[ ] Bulunamadı{Colors.RESET}"
        print(f"  • {p:<12}: {status}")

    # 5. Model & Fallback Priority Selection Menu
    print(f"\n{Colors.BOLD}6. Model ve Fallback Sıralama Tercihi:{Colors.RESET}")
    print("  [1] Akıllı Otomatik (Auto) — Kurulu tüm modelleri hız/maliyet sırasıyla tara (Önerilen)")
    print("  [2] Google Antigravity Öncelikli (Antigravity -> Codex -> Claude -> Cursor)")
    print("  [3] OpenAI Codex Öncelikli (Codex -> Claude -> Antigravity -> Cursor)")
    print("  [4] Anthropic Claude Öncelikli (Claude -> Codex -> Antigravity -> Cursor)")
    print("  [5] Yalnızca Tek Model Kitle (Fail-fast — Yalnızca seçilen model)")
    print("  [6] Özel Sıralama Belirle (Virgülle kendi sıranızı girin)")

    choice = _prompt_user("Seçiminiz (1-6)", "1")

    summary_provider = "auto"
    provider_priority: list[str] | None = None

    if choice == "1":
        summary_provider = "auto"
        provider_priority = ["claude", "codex", "antigravity", "cursor"]
    elif choice == "2":
        summary_provider = "auto"
        provider_priority = ["antigravity", "codex", "claude", "cursor"]
    elif choice == "3":
        summary_provider = "auto"
        provider_priority = ["codex", "claude", "antigravity", "cursor"]
    elif choice == "4":
        summary_provider = "auto"
        provider_priority = ["claude", "codex", "antigravity", "cursor"]
    elif choice == "5":
        print("  Hangi modeli kilitlemek istiyorsunuz? (antigravity / codex / claude / cursor)")
        locked = _prompt_user("Model", "antigravity").lower()
        if locked in SUPPORTED_PROVIDERS:
            summary_provider = locked
            provider_priority = [locked]
        else:
            summary_provider = "auto"
    elif choice == "6":
        custom_input = _prompt_user("Sıralamayı virgülle girin (örn: antigravity, codex)", "antigravity, codex")
        items = [p.strip().lower() for p in custom_input.split(",") if p.strip()]
        valid = [p for p in items if p in SUPPORTED_PROVIDERS]
        if valid:
            summary_provider = "auto"
            provider_priority = valid

    # 7. Environment Selection Menu
    print(f"\n{Colors.BOLD}7. Çalışma Ortamı Tercihi:{Colors.RESET}")
    print("  [1] Native (PowerShell / Terminal — Doğrudan mevcut işletim sistemi üzerinde)")
    print("  [2] WSL / Linux Alt Sistemi (WSL2 ortamında geliştirme yapanlar için)")
    print("  [3] Hibrit (Kasa yerel belgelerde, WSL/Linux'tan köprüyle ortak erişim)")
    env_choice = _prompt_user("Seçiminiz (1-3)", "1")
    if env_choice == "2":
        environment = "wsl"
    elif env_choice == "3":
        environment = "hybrid"
    else:
        environment = "native"

    # 8. Global rules
    global_choice = _prompt_user("8. Global AI kurallarına (~/.gemini, ~/.claude vb.) bağlansın mı? [E/h]", "E").lower()
    install_global = global_choice in ("e", "evet", "y", "yes")

    # 9. Desktop Shortcut
    shortcut_choice = _prompt_user("9. Masaüstüne doğrudan Obsidian açılış kısayolu eklensin mi? [E/h]", "E").lower()
    desktop_shortcut = shortcut_choice in ("e", "evet", "y", "yes")

    # 10. Morning Briefing & Knowledge Compilation Schedule
    schedule_choice = _prompt_user("10. Sabah Bilgi Derleme ve Brifing zamanlayıcısı kurulsun mu? [E/h]", "E").lower()
    install_schedule = schedule_choice in ("e", "evet", "y", "yes")
    schedule_time = "08:00"
    if install_schedule:
        schedule_time = _prompt_user(
            "    Çalışma saati ne olsun? (Seçtiğiniz saatte bilgisayar kapalıysa, açtığınızda otomatik çalışır)",
            "08:00",
        )

    return install_vault(
        vault_path=vault_path,
        user_name=user_name,
        user_bio=user_bio,
        companion=companion,
        os_name=os_name,
        summary_provider=summary_provider,
        provider_priority=provider_priority,
        install_global=install_global,
        install_schedule=install_schedule,
        schedule_time=schedule_time,
        desktop_shortcut=desktop_shortcut,
        environment=environment,
        quiet=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respected Brain Installer")
    parser.add_argument("--non-interactive", action="store_true", help="Kullanıcıdan girdi almadan çalış")
    parser.add_argument("--defaults", action="store_true", help="Varsayılan değerlerle otomatik kur")
    parser.add_argument("--vault-path", type=Path, help="Kasa kurulum yolu")
    parser.add_argument("--user-name", default=None, help="Kullanıcı adı")
    parser.add_argument("--user-bio", default="Geliştirici & Mühendis", help="Kullanıcı rol / bio")
    parser.add_argument("--companion", default="Jarvis", help="Companion / hafıza asistanı adı")
    parser.add_argument("--os-name", default="RespectedOS", help="Kasa işletim sistemi adı")
    parser.add_argument("--provider", default="auto", choices=("auto", *SUPPORTED_PROVIDERS), help="Birincil model")
    parser.add_argument("--priority", nargs="+", help="Model fallback öncelik sırası")
    parser.add_argument("--environment", choices=("native", "wsl", "hybrid"), default=None, help="Çalışma ortamı tercihi")
    parser.add_argument("--install-global", action="store_true", help="Global AI kural bağlantısını yap")
    parser.add_argument("--install-schedule", dest="install_schedule", action="store_true", default=False, help="Sabah brifingi zamanlayıcısını kur")
    parser.add_argument("--no-install-schedule", dest="install_schedule", action="store_false", help="Zamanlayıcıyı kurma")
    parser.add_argument("--schedule-time", default="08:00", help="Sabah brifingi çalışma saati (HH:MM)")
    parser.add_argument("--desktop-shortcut", dest="desktop_shortcut", action="store_true", default=False, help="Masaüstüne Obsidian kısayolu oluştur")
    parser.add_argument("--no-desktop-shortcut", dest="desktop_shortcut", action="store_false", help="Masaüstü kısayolu oluşturma")
    parser.add_argument("--quiet", action="store_true", help="Sessiz kurulum")

    args = parser.parse_args(argv)

    if not args.non_interactive and not args.defaults and args.vault_path is None:
        # Launch interactive wizard
        return _interactive_wizard()

    # Scripted / Non-interactive execution
    vault_path = args.vault_path or _default_vault_path()
    user_name = args.user_name or os.environ.get("USERNAME") or os.environ.get("USER") or "Furkan"
    priority = list(args.priority) if args.priority else None

    return install_vault(
        vault_path=vault_path,
        user_name=user_name,
        user_bio=args.user_bio,
        companion=args.companion,
        os_name=args.os_name,
        summary_provider=args.provider,
        provider_priority=priority,
        install_global=args.install_global,
        install_schedule=args.install_schedule,
        schedule_time=args.schedule_time,
        desktop_shortcut=args.desktop_shortcut,
        environment=args.environment,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
