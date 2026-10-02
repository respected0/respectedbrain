#!/usr/bin/env python3
"""Build script for Respected Brain Installers across Windows, macOS, and Linux.

Produces single-click native installers:
  - Windows: setup.exe (Inno Setup 6.x / PyInstaller)
  - macOS: setup.command (Finder double-clickable launcher) and native packages
  - Linux: setup (Double-clickable executable launcher) and setup.sh (curl | bash)
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DIST_DIR = REPO_ROOT / "dist"


def make_executable(path: Path) -> None:
    if path.is_file():
        try:
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            pass


def build_windows_inno() -> bool:
    iscc = shutil.which("iscc") or shutil.which("iscc.exe")
    if not iscc:
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        ]
        for c in candidates:
            if c.is_file():
                iscc = str(c)
                break

    if not iscc:
        return False

    iss_file = REPO_ROOT / "installer" / "respected_setup.iss"
    print(f"[*] Inno Setup ile setup.exe derleniyor: {iscc} {iss_file}")
    proc = subprocess.run([iscc, str(iss_file)], cwd=REPO_ROOT)
    return proc.returncode == 0


def build_pyinstaller(target_name: str = "setup") -> bool:
    pyinstaller = shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")
    if not pyinstaller:
        return False

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    wizard_script = SCRIPT_DIR / "setup_wizard.py"

    cmd = [
        pyinstaller,
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", target_name,
        "--distpath", str(DIST_DIR),
        str(wizard_script),
    ]
    print(f"[*] PyInstaller ile derleniyor: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    if proc.returncode == 0:
        exe_ext = ".exe" if sys.platform == "win32" else ""
        out_bin = DIST_DIR / f"{target_name}{exe_ext}"
        if out_bin.is_file():
            dest_bin = REPO_ROOT / f"{target_name}{exe_ext}"
            shutil.copy2(out_bin, dest_bin)
            make_executable(dest_bin)
            print(f"[✓] {dest_bin.name} basariyla olusturuldu: {dest_bin}")
        return True
    return False


def build_unix_launchers() -> None:
    # Ensure macOS setup.command and Linux setup are executable
    mac_launcher = REPO_ROOT / "setup.command"
    linux_launcher = REPO_ROOT / "setup"

    for script in (mac_launcher, linux_launcher):
        if script.is_file():
            make_executable(script)
            print(f"[✓] Unix başlatıcı hazırlandı: {script.name}")


def main() -> int:
    print("[*] Respected Brain Cross-Platform Installer Derleyici")
    build_unix_launchers()

    if sys.platform == "win32":
        if build_windows_inno():
            print("[+] Windows setup.exe basariyla derlendi!")
            return 0
        if build_pyinstaller("setup"):
            print("[+] Windows setup.exe (PyInstaller) basariyla derlendi!")
            return 0
    elif sys.platform == "darwin":
        print("[+] macOS setup.command hazirlandi!")
        if build_pyinstaller("setup"):
            print("[+] macOS setup binary basariyla derlendi!")
        return 0
    else:
        print("[+] Linux setup hazirlandi!")
        if build_pyinstaller("setup"):
            print("[+] Linux setup binary basariyla derlendi!")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
