#!/usr/bin/env python3
"""Respected Brain — Entegre Otomatik Güncelleyici (Auto-Updater).

GitHub Releases veya yerel kanaldan güncellemeleri denetler, kasanın
bütünlüğünü doğrular ve hasarsız artımlı güncelleme uygular.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_VAULT = Path.home() / "Documents" / "RespectedOS"
GITHUB_REPO = "respected0/respectedbrain"


def check_remote_version() -> tuple[str, str]:
    """Check latest release on GitHub (or return fallback if offline)."""
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": "RespectedBrain-Updater", "Accept": "application/vnd.github.v3+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            tag = data.get("tag_name", "v0.0.1").lstrip("v")
            body = data.get("body", "")
            return tag, body
    except Exception:
        # Fallback to local git commit check if git repo
        try:
            res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
            if res.returncode == 0:
                return f"git-{res.stdout.strip()}", "Yerel Git Deposu"
        except Exception:
            pass
        return "0.0.1", "Offline / Yerel Sürüm"


def get_installed_version(vault_path: Path) -> str:
    ver_file = vault_path / ".respectedbrain-version"
    if ver_file.is_file():
        return ver_file.read_text(encoding="utf-8").strip()
    return "0.0.1"


def verify_vault_integrity(vault_path: Path) -> tuple[bool, str]:
    """Ensure vault structure is intact before updating."""
    if not vault_path.is_dir():
        return False, f"Vault dizini bulunamadı: {vault_path}"
    
    companion = vault_path / "🔮 850-Companion"
    if not companion.is_dir():
        return False, "Kritik dizin eksik: 🔮 850-Companion"

    return True, "Vault bütünlüğü doğrulandı."


def apply_update(vault_path: Path, force: bool = False) -> tuple[bool, str]:
    """Perform transactional update."""
    valid, msg = verify_vault_integrity(vault_path)
    if not valid:
        return False, msg

    state_dir = vault_path / ".beyin" / "engine" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # Run update.py
    cmd = [
        sys.executable,
        str(REPO_ROOT / "update.py"),
        str(vault_path),
        "--apply",
        "--platform", "windows-native",
    ]
    if force:
        cmd.append("--force")

    print(f"[*] Güncelleme uygulanıyor: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)

    history_file = state_dir / "update-history.json"
    history = []
    if history_file.is_file():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception:
            history = []

    record = {
        "timestamp": dt.datetime.now().isoformat(),
        "exit_code": proc.returncode,
        "success": proc.returncode == 0,
        "stdout": proc.stdout[-1000:] if proc.stdout else "",
        "stderr": proc.stderr[-1000:] if proc.stderr else "",
    }
    history.append(record)
    history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    if proc.returncode == 0:
        return True, "Güncelleme başarıyla uygulandı."
    else:
        return False, f"Güncelleme başarısız: {proc.stderr or proc.stdout}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respected Brain Otomatik Güncelleyici")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT, help="Hedef vault yolu")
    parser.add_argument("--check", action="store_true", help="Yalnızca yeni sürümü kontrol et")
    parser.add_argument("--apply", action="store_true", help="Güncellemeyi doğrudan uygula")
    parser.add_argument("--force", action="store_true", help="Zorla üzerine yaz")

    args = parser.parse_args(argv)
    vault = args.vault.resolve()

    current_ver = get_installed_version(vault)
    print(f"[*] Kurulu Sürüm: v{current_ver} ({vault})")

    remote_ver, release_notes = check_remote_version()
    print(f"[*] En Son Sürüm: v{remote_ver}")

    if args.check:
        if remote_ver > current_ver:
            print(f"[!] Yeni sürüm mevcut: v{remote_ver}")
            print(f"Notlar:\n{release_notes}")
            return 10
        else:
            print("[✓] Sistem güncel.")
            return 0

    if args.apply:
        success, msg = apply_update(vault, force=args.force)
        print(f"[{'✓' if success else '!'}] {msg}")
        return 0 if success else 1

    # Default interactive
    if remote_ver > current_ver or args.force:
        ans = input(f"v{remote_ver} sürümüne güncellemek istiyor musunuz? [E/h]: ").strip().lower()
        if ans in ("", "e", "evet", "y", "yes"):
            success, msg = apply_update(vault, force=args.force)
            print(f"[{'✓' if success else '!'}] {msg}")
            return 0 if success else 1
    else:
        print("[✓] Sistem zaten en son sürümde.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
