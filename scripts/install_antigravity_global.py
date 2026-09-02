#!/usr/bin/env python3
"""Connect Windows Antigravity to one Respected Brain vault through WSL."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from install_global import apply_plan, build, windows_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, help="WSL'den görülen, adı serbest vault yolu")
    parser.add_argument(
        "--antigravity-home",
        required=True,
        type=Path,
        help="Windows kullanıcı kökü; ör. /mnt/c/Users/<ad>",
    )
    parser.add_argument("--apply", action="store_true", help="önizleme yerine değişiklikleri uygula")
    args = parser.parse_args()

    vault = args.vault.expanduser().resolve()
    home = args.antigravity_home.expanduser().resolve()
    if not (vault / ".beyin/instructions.md").is_file():
        parser.error("vault içinde .beyin/instructions.md bulunamadı")
    if not (vault / ".beyin/skills").is_dir():
        parser.error("vault içinde .beyin/skills bulunamadı")
    if not home.is_dir():
        parser.error(f"Antigravity kullanıcı kökü bulunamadı: {home}")
    if windows_path(vault) is None:
        parser.error("Windows Antigravity için vault /mnt/<sürücü>/... altında olmalı")

    try:
        writes, _touched = build(vault, home, ("antigravity",), "windows-wsl")
    except (OSError, ValueError) as error:
        print(f"hata: {error}", file=sys.stderr)
        return 2

    for path, _content in writes:
        print(f"yönetilecek: {path}")
    if not args.apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0

    backup = home / ".respected-backups" / dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    try:
        apply_plan(writes, home, backup)
    except (OSError, ValueError) as error:
        print(f"yazma başarısız: {error}; yedek: {backup}", file=sys.stderr)
        return 3
    print(f"Respected global Antigravity bağlantısı kuruldu; yedek: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
