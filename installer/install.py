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
import tempfile
import time
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "template"
SCRIPTS_DIR = (REPO_ROOT / "runtime" / "scripts") if (REPO_ROOT / "runtime" / "scripts").is_dir() else (REPO_ROOT / "scripts")

SUPPORTED_PROVIDERS = ("antigravity", "gemini", "codex", "claude", "cursor")
PROVIDER_COMMANDS = {
    "antigravity": "agy",
    "gemini": "gemini",
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
        is_macos_target = sys.platform == "darwin"
        is_windows_target = not is_macos_target and (
            os.name == "nt" or str(desktop_dir).startswith("/mnt/c/")
        )
        if is_macos_target:
            import plistlib

            shortcut_file = desktop_dir / f"{vault_name}.webloc"
            shortcut_file.write_bytes(
                plistlib.dumps({"URL": uri}, fmt=plistlib.FMT_XML, sort_keys=True)
            )
            return shortcut_file
        if is_windows_target:
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


def _apply_optional_integrations(
    *,
    vault_path: Path,
    platform_name: str,
    os_name: str,
    install_global: bool,
    install_schedule: bool,
    schedule_time: str,
    desktop_shortcut: bool,
    desktop_dir_override: Path | None,
    install_mcp: bool,
    log,
) -> tuple[int, Path | None]:
    """Apply requested external integrations and preserve their failure code."""
    target_scripts = vault_path / "scripts"

    if install_global:
        log(f"{Colors.DIM}• Global AI kural bağlantıları kuruluyor...{Colors.RESET}")
        global_installer = target_scripts / "install_global.py"
        if not global_installer.is_file():
            print(f"{Colors.RED}HATA: Global entegrasyon betiği bulunamadı.{Colors.RESET}", file=sys.stderr)
            return 1, None
        result = subprocess.run(
            [sys.executable, str(global_installer), str(vault_path), "--home", str(Path.home()), "--platform", platform_name, "--apply"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"{Colors.RED}HATA: Global bağlantı tamamlanamadı: {result.stderr.strip()}{Colors.RESET}", file=sys.stderr)
            return result.returncode or 1, None
        log(f"  {Colors.GREEN}✔ Global AI kural ve kanca bağlantıları başarıyla kuruldu.{Colors.RESET}")

    created_shortcut = None
    if desktop_shortcut:
        log(f"{Colors.DIM}• Masaüstü Obsidian kısayolu oluşturuluyor...{Colors.RESET}")
        created_shortcut = create_desktop_shortcut(os_name, vault_path, desktop_dir_override)
        if created_shortcut is None:
            print(f"{Colors.RED}HATA: İstenen masaüstü kısayolu oluşturulamadı.{Colors.RESET}", file=sys.stderr)
            return 1, None

    if install_schedule:
        log(f"{Colors.DIM}• Sabah brifingi ve bilgi derlemesi zamanlayıcısı kuruluyor ({schedule_time})...{Colors.RESET}")
        schedule_script = target_scripts / "install_briefing_schedule.py"
        if not schedule_script.is_file():
            print(f"{Colors.RED}HATA: Zamanlayıcı kurulum betiği bulunamadı.{Colors.RESET}", file=sys.stderr)
            return 1, created_shortcut
        result = subprocess.run(
            [sys.executable, str(schedule_script), str(vault_path), "--home", str(Path.home()), "--platform", platform_name, "--time", schedule_time, "--apply"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"{Colors.RED}HATA: Zamanlayıcı kurulamadı: {result.stderr.strip()}{Colors.RESET}", file=sys.stderr)
            return result.returncode or 1, created_shortcut

    if install_mcp:
        log(f"{Colors.DIM}• Editörlere (Claude Desktop, Cursor, Antigravity, Windsurf vb.) MCP sunucusu kaydediliyor...{Colors.RESET}")
        mcp_script = target_scripts / "vault_mcp_server.py"
        if not mcp_script.is_file():
            print(f"{Colors.RED}HATA: MCP kayıt betiği bulunamadı.{Colors.RESET}", file=sys.stderr)
            return 1, created_shortcut
        result = subprocess.run(
            [sys.executable, str(mcp_script), "--vault", str(vault_path), "--register"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            print(f"{Colors.RED}HATA: MCP kaydı tamamlanamadı: {result.stderr.strip()}{Colors.RESET}", file=sys.stderr)
            return result.returncode or 1, created_shortcut
        for line in result.stdout.splitlines():
            clean_line = line.strip()
            if clean_line.startswith("✓") or "kaydedildi" in clean_line.lower():
                log(f"  {Colors.GREEN}{clean_line}{Colors.RESET}")

    return 0, created_shortcut


def install_vault(
    vault_path: Path,
    user_name: str,
    user_bio: str,
    companion: str,
    os_name: str,
    summary_provider: str,
    provider_priority: list[str] | None = None,
    python_command: list[str] | None = None,
    install_global: bool = False,
    install_schedule: bool = False,
    schedule_time: str = "08:00",
    desktop_shortcut: bool = False,
    desktop_dir_override: Path | None = None,
    install_mcp: bool = False,
    environment: str | None = None,
    quiet: bool = False,
) -> int:
    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    vault_path = vault_path.expanduser().resolve()
    log(f"\n{Colors.CYAN}>> Kurulum Başlatılıyor:{Colors.RESET} {vault_path}")

    # Preflight target
    target_existed = vault_path.exists()
    if target_existed:
        if not vault_path.is_dir():
            print(f"{Colors.RED}HATA: Hedef yol bir klasör değil: {vault_path}{Colors.RESET}", file=sys.stderr)
            return 1
        if any(vault_path.iterdir()):
            version_files = (
                vault_path / ".respectedbrain-version",
                vault_path / ".respected.json",
                vault_path / ".beyin-version",
                vault_path / ".beyin-multi-version",
            )
            recognized = (
                any(path.is_file() for path in version_files)
                and (
                    (vault_path / ".beyin/instructions.md").is_file()
                    or (vault_path / "🔮 850-Companion").is_dir()
                    or (vault_path / ".respected.json").is_file()
                )
            )
            if not recognized:
                print(f"{Colors.RED}HATA: Hedef klasör boş değil: {vault_path}{Colors.RESET}", file=sys.stderr)
                return 1

            platform_name = (
                "windows-wsl"
                if os.name == "nt" and environment in {"wsl", "hybrid"}
                else "windows-native"
                if os.name == "nt"
                else "portable"
            )
            log(f"{Colors.DIM}• Mevcut Respected Brain kasası güvenli güncelleme yoluyla yenileniyor...{Colors.RESET}")
            update_cmd = [
                sys.executable,
                str(SCRIPTS_DIR / "update_respected.py"),
                str(vault_path),
                "--platform",
                platform_name,
                "--summary-provider",
                summary_provider,
                "--force",
                "--apply",
            ]
            updated = subprocess.run(update_cmd, capture_output=True, text=True, check=False)
            if updated.returncode != 0:
                print(
                    f"{Colors.RED}HATA: Mevcut kasa güncellenemedi: {updated.stderr.strip()}{Colors.RESET}",
                    file=sys.stderr,
                )
                return updated.returncode

            if python_command:
                render_cmd = [
                    sys.executable,
                    str(vault_path / "scripts/render_integrations.py"),
                    "--root",
                    str(vault_path),
                    "--platform",
                    platform_name,
                    "--python-command",
                    *python_command,
                ]
                rendered = subprocess.run(render_cmd, capture_output=True, text=True, check=False)
                if rendered.returncode != 0:
                    print(
                        f"{Colors.RED}HATA: Güncellenen entegrasyonlar render edilemedi: {rendered.stderr.strip()}{Colors.RESET}",
                        file=sys.stderr,
                    )
                    return rendered.returncode
            integration_code, _created_shortcut = _apply_optional_integrations(
                vault_path=vault_path,
                platform_name=platform_name,
                os_name=os_name,
                install_global=install_global,
                install_schedule=install_schedule,
                schedule_time=schedule_time,
                desktop_shortcut=desktop_shortcut,
                desktop_dir_override=desktop_dir_override,
                install_mcp=install_mcp,
                log=log,
            )
            if integration_code != 0:
                return integration_code
            log(f"{Colors.GREEN}✔ Mevcut kasa güncellendi; kullanıcı dosyaları korundu.{Colors.RESET}")
            return 0
    else:
        vault_path.parent.mkdir(parents=True, exist_ok=True)

    stage_container = Path(
        tempfile.mkdtemp(prefix=f".{vault_path.name}.respected-stage-", dir=vault_path.parent)
    )
    working_path = stage_container / "vault"
    working_path.mkdir()

    try:
        # 1. Copy template
        log(f"{Colors.DIM}• Şablon dosyaları aktarılıyor...{Colors.RESET}")
        for item in TEMPLATE_DIR.iterdir():
            target_item = working_path / item.name
            if item.is_dir():
                shutil.copytree(item, target_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target_item)

        # 2. Copy scripts
        log(f"{Colors.DIM}• Yardımcı motor betikleri kopyalanıyor...{Colors.RESET}")
        target_scripts = working_path / "scripts"
        target_scripts.mkdir(parents=True, exist_ok=True)
        excluded_scripts = {"install-windows.ps1", "upstream_sync.sh", "install.py"}
        for script_file in SCRIPTS_DIR.glob("*.py"):
            if script_file.name not in excluded_scripts:
                shutil.copy2(script_file, target_scripts / script_file.name)

        # 3. Create required runtime dirs
        (working_path / "daily").mkdir(exist_ok=True)
        (working_path / "knowledge" / "concepts").mkdir(parents=True, exist_ok=True)
        (working_path / "knowledge" / "connections").mkdir(parents=True, exist_ok=True)

        # 4. Write .beyin/config.json
        if os.name == "nt":
            platform_name = "windows-wsl" if environment in {"wsl", "hybrid"} else "windows-native"
        else:
            platform_name = "portable"
        default_python_command = [sys.executable] if platform_name == "windows-native" else ["python3"]
        config_data = {
            "summary_provider": summary_provider,
            "provider_fallback": summary_provider == "auto",
            "platform": platform_name,
            "python_command": list(python_command or default_python_command),
        }
        if environment:
            config_data["environment"] = environment
        if provider_priority:
            config_data["provider_priority"] = provider_priority

        config_path = working_path / ".beyin" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 5. Render integrations
        log(f"{Colors.DIM}• Multi-AI entegrasyonları derleniyor...{Colors.RESET}")
        source_dir = REPO_ROOT / "runtime"
        if not (source_dir / "instructions.md").is_file():
            source_dir = REPO_ROOT / "template/.beyin"
        render_cmd = [
            sys.executable,
            str(target_scripts / "render_integrations.py"),
            "--root",
            str(working_path),
            "--platform",
            platform_name,
        ]
        if (source_dir / "instructions.md").is_file():
            render_cmd += ["--source", str(source_dir)]
        if python_command:
            render_cmd += ["--python-command", *python_command]
        result = subprocess.run(render_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"{Colors.RED}HATA: Entegrasyon render başarısız:{Colors.RESET}\n{result.stderr}", file=sys.stderr)
            shutil.rmtree(stage_container, ignore_errors=True)
            return result.returncode

        # 6. Resolve placeholders (after template and rendered integrations)
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

        text_extensions = {".md", ".mdc", ".json", ".txt", ".yml", ".yaml"}
        for root, dirs, files in os.walk(working_path):
            if "scripts" in dirs:
                dirs.remove("scripts")
            if Path(root).name == "scripts":
                continue
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

        # Promote only after the complete staged vault has passed its render gate.
        # Each top-level move is atomic on the same volume; rollback moves only
        # our own entries and never sweeps an unrelated concurrent file.
        if vault_path.exists():
            if any(vault_path.iterdir()):
                shutil.rmtree(stage_container, ignore_errors=True)
                print(
                    f"{Colors.RED}HATA: Hedef klasör kurulum sırasında değişti: {vault_path}{Colors.RESET}",
                    file=sys.stderr,
                )
                return 1
        else:
            vault_path.mkdir()
        promoted: list[Path] = []
        try:
            for item in working_path.iterdir():
                destination = vault_path / item.name
                os.replace(item, destination)
                promoted.append(destination)
        except OSError:
            for destination in reversed(promoted):
                try:
                    os.replace(destination, working_path / destination.name)
                except OSError:
                    pass
            if not target_existed:
                try:
                    vault_path.rmdir()
                except OSError:
                    pass
            raise

        # The staged render proves the generated integrations are valid, but native
        # hook commands contain absolute vault paths. Render once more from the
        # promoted vault so persistent commands never retain the disposable stage.
        final_render_cmd = [
            sys.executable,
            str(vault_path / "scripts" / "render_integrations.py"),
            "--root",
            str(vault_path),
            "--platform",
            platform_name,
        ]
        if (source_dir / "instructions.md").is_file():
            final_render_cmd += ["--source", str(source_dir)]
        if python_command:
            final_render_cmd += ["--python-command", *python_command]
        final_render = subprocess.run(
            final_render_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if final_render.returncode != 0:
            for destination in reversed(promoted):
                try:
                    os.replace(destination, working_path / destination.name)
                except OSError:
                    pass
            if not target_existed:
                try:
                    vault_path.rmdir()
                except OSError:
                    pass
            shutil.rmtree(stage_container, ignore_errors=True)
            print(
                f"{Colors.RED}HATA: Final entegrasyon render başarısız:{Colors.RESET}\n"
                f"{final_render.stderr}",
                file=sys.stderr,
            )
            return final_render.returncode

        # Sweep promoted vault to guarantee all rendered files have placeholders resolved
        for root, dirs, files in os.walk(vault_path):
            if "scripts" in dirs:
                dirs.remove("scripts")
            if Path(root).name == "scripts":
                continue
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

        shutil.rmtree(stage_container, ignore_errors=True)
        integration_code, created_shortcut = _apply_optional_integrations(
            vault_path=vault_path,
            platform_name=platform_name,
            os_name=os_name,
            install_global=install_global,
            install_schedule=install_schedule,
            schedule_time=schedule_time,
            desktop_shortcut=desktop_shortcut,
            desktop_dir_override=desktop_dir_override,
            install_mcp=install_mcp,
            log=log,
        )
        if integration_code != 0:
            return integration_code

        # 11. Git Repository Initialization
        git_bin = shutil.which("git")
        if git_bin and not (vault_path / ".git").is_dir():
            log(f"{Colors.DIM}• Git versiyon kontrolü başlatılıyor...{Colors.RESET}")
            try:
                subprocess.run([git_bin, "init", "-q"], cwd=str(vault_path), check=False, capture_output=True)
                subprocess.run([git_bin, "add", "."], cwd=str(vault_path), check=False, capture_output=True)
                subprocess.run([git_bin, "commit", "-q", "-m", f"feat: genesis {os_name} vault"], cwd=str(vault_path), check=False, capture_output=True)
                log(f"  {Colors.GREEN}✔ Kasa Git deposu olarak başlatıldı ve ilk commit oluşturuldu.{Colors.RESET}")
            except Exception:
                pass

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
        if install_mcp:
            log(f"  {Colors.BOLD}MCP Sunucusu:{Colors.RESET} AI Editörlerine Kaydedildi (respected-vault)")
        log(f"\n{Colors.CYAN}Obsidian ile Başlayın:{Colors.RESET}")
        log(f"  1. Obsidian'ı açın.")
        log(f"  2. 'Open folder as vault' seçeneğine tıklayın.")
        log(f"  3. Şu klasörü seçin: {Colors.BOLD}{vault_path}{Colors.RESET}\n")
        return 0

    except Exception as exc:
        shutil.rmtree(stage_container, ignore_errors=True)
        if not target_existed:
            try:
                vault_path.rmdir()
            except OSError:
                pass
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
    print("  [2] Google Antigravity Öncelikli (Antigravity -> Gemini -> Codex -> Claude -> Cursor)")
    print("  [3] OpenAI Codex Öncelikli (Codex -> Claude -> Gemini -> Antigravity -> Cursor)")
    print("  [4] Anthropic Claude Öncelikli (Claude -> Codex -> Gemini -> Antigravity -> Cursor)")
    print("  [5] Yalnızca Tek Model Kitle (Fail-fast — Yalnızca seçilen model)")
    print("  [6] Özel Sıralama Belirle (Virgülle kendi sıranızı girin)")

    choice = _prompt_user("Seçiminiz (1-6)", "1")

    summary_provider = "auto"
    provider_priority: list[str] | None = None

    if choice == "1":
        summary_provider = "auto"
        provider_priority = ["claude", "codex", "gemini", "antigravity", "cursor"]
    elif choice == "2":
        summary_provider = "auto"
        provider_priority = ["antigravity", "gemini", "codex", "claude", "cursor"]
    elif choice == "3":
        summary_provider = "auto"
        provider_priority = ["codex", "claude", "gemini", "antigravity", "cursor"]
    elif choice == "4":
        summary_provider = "auto"
        provider_priority = ["claude", "codex", "gemini", "antigravity", "cursor"]
    elif choice == "5":
        print("  Hangi modeli kilitlemek istiyorsunuz? (antigravity / gemini / codex / claude / cursor)")
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

    # 11. MCP Server Registration
    mcp_choice = _prompt_user(
        "11. Dış projelerden kasaya erişmek için MCP sunucusu editörlere (Claude Desktop, Cursor, Antigravity vb.) kaydedilsin mi? [E/h]",
        "E",
    ).lower()
    install_mcp = mcp_choice in ("e", "evet", "y", "yes")

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
        install_mcp=install_mcp,
        environment=environment,
        quiet=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respected Brain Installer")
    parser.add_argument("target", nargs="?", default=None, help="Kasa kurulum yolu (opsiyonel)")
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
    parser.add_argument("--python-executable", help="Windows bootstrap tarafından doğrulanan Python executable")
    parser.add_argument("--python-launcher-arg", action="append", default=[], help="Python launcher için ek argv; tekrarlanabilir")
    parser.add_argument("--install-global", action="store_true", help="Global AI kural bağlantısını yap")
    parser.add_argument("--install-schedule", dest="install_schedule", action="store_true", default=False, help="Sabah brifingi zamanlayıcısını kur")
    parser.add_argument("--no-install-schedule", dest="install_schedule", action="store_false", help="Zamanlayıcıyı kurma")
    parser.add_argument("--schedule-time", default="08:00", help="Sabah brifingi çalışma saati (HH:MM)")
    parser.add_argument("--desktop-shortcut", dest="desktop_shortcut", action="store_true", default=False, help="Masaüstüne Obsidian kısayolu oluştur")
    parser.add_argument("--no-desktop-shortcut", dest="desktop_shortcut", action="store_false", help="Masaüstü kısayolu oluşturma")
    parser.add_argument("--install-mcp", dest="install_mcp", action="store_true", default=False, help="Editörlere MCP sunucusunu kaydet")
    parser.add_argument("--no-install-mcp", dest="install_mcp", action="store_false", help="MCP sunucusunu kaydetme")
    parser.add_argument("--quiet", action="store_true", help="Sessiz kurulum")

    args = parser.parse_args(argv)

    if not args.non_interactive and not args.defaults and args.vault_path is None and args.target is None:
        # Launch interactive wizard
        return _interactive_wizard()

    # Scripted / Non-interactive execution
    vault_path = args.vault_path or (Path(args.target) if args.target else None) or _default_vault_path()
    user_name = args.user_name or os.environ.get("USERNAME") or os.environ.get("USER") or "Furkan"
    priority = list(args.priority) if args.priority else None
    python_command = (
        [args.python_executable, *args.python_launcher_arg]
        if args.python_executable
        else None
    )

    return install_vault(
        vault_path=vault_path,
        user_name=user_name,
        user_bio=args.user_bio,
        companion=args.companion,
        os_name=args.os_name,
        summary_provider=args.provider,
        provider_priority=priority,
        python_command=python_command,
        install_global=args.install_global,
        install_schedule=args.install_schedule,
        schedule_time=args.schedule_time,
        desktop_shortcut=args.desktop_shortcut,
        install_mcp=args.install_mcp,
        environment=args.environment,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
