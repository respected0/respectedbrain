#!/usr/bin/env python3
"""Connect explicit Antigravity homes to one Respected Brain vault through WSL."""

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
        action="append",
        type=Path,
        help="Antigravity kullanıcı kökü; birden fazla verilebilir",
    )
    parser.add_argument("--apply", action="store_true", help="önizleme yerine değişiklikleri uygula")
    args = parser.parse_args()

    vault = args.vault.expanduser().resolve()
    homes: list[Path] = []
    seen_homes: set[Path] = set()
    for candidate in args.antigravity_home:
        home = candidate.expanduser().resolve()
        if home not in seen_homes:
            homes.append(home)
            seen_homes.add(home)
    if not (vault / ".beyin/instructions.md").is_file():
        parser.error("vault içinde .beyin/instructions.md bulunamadı")
    if not (vault / ".beyin/skills").is_dir():
        parser.error("vault içinde .beyin/skills bulunamadı")
    for home in homes:
        if not home.is_dir():
            parser.error(f"Antigravity kullanıcı kökü bulunamadı: {home}")
    if windows_path(vault) is None:
        parser.error("Windows Antigravity için vault /mnt/<sürücü>/... altında olmalı")

    plans: list[tuple[Path, list[tuple[Path, str | None]]]] = []
    try:
        for home in homes:
            writes, _touched = build(vault, home, ("antigravity",), "windows-wsl")
            plans.append((home, writes))
    except (OSError, ValueError) as error:
        print(f"hata: {error}", file=sys.stderr)
        return 2

    for home, writes in plans:
        print(f"kullanıcı kökü: {home}")
        for path, _content in writes:
            print(f"yönetilecek: {path}")
    if not args.apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0

    for home, writes in plans:
        backup = home / ".respected-backups" / dt.datetime.now().strftime(
            "%Y%m%d-%H%M%S-%f"
        )
        try:
            changed = apply_plan(writes, home, backup)
        except (OSError, ValueError) as error:
            print(
                f"yazma başarısız ({home}): {error}; yedek: {backup}",
                file=sys.stderr,
            )
            return 3
        if changed:
            print(f"Respected global Antigravity bağlantısı kuruldu ({home}); yedek: {backup}")
        else:
            print(f"Respected global Antigravity bağlantısı zaten güncel ({home}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
