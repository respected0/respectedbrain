#!/usr/bin/env python3
"""Add or update the Respot Brain multi-AI layer in an existing brain vault safely."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import shutil
import subprocess
import sys
import os

from respot_manifest import GENERATED, MULTI_VERSION, RUNTIME


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "template"


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, help="mevcut vault klasörü")
    parser.add_argument("--apply", action="store_true", help="önizleme yerine değişiklikleri uygula")
    parser.add_argument(
        "--defer-version-stamp",
        action="store_true",
        help="upgrade transaction için adapterları kur ama .beyin-multi-version yazma",
    )
    parser.add_argument(
        "--platform",
        choices=("auto", "portable", "windows-wsl", "windows-native"),
        default="auto",
        help="hook çalışma ortamı; WSL içindeki Windows vault'larında otomatik algılanır",
    )
    args = parser.parse_args()
    vault = args.vault.expanduser().resolve()
    if not vault.is_dir():
        parser.error(f"vault bulunamadı: {vault}")
    if not ((vault / ".beyin-version").is_file() or (vault / "🔮 850-Companion").is_dir()):
        parser.error("hedef bir v1/v2 ikinci beyin vault'u gibi görünmüyor")

    instructions = vault / ".beyin" / "instructions.md"
    source_instructions = instructions if instructions.exists() else vault / "CLAUDE.md"
    if not source_instructions.is_file():
        parser.error("CLAUDE.md veya .beyin/instructions.md bulunamadı")
    print(f"kanonik talimat kaynağı: {source_instructions}")
    print("yönetilen adaptörler:")
    for relative in (*GENERATED, *RUNTIME, ".beyin/config.json", ".agents/skills", ".claude/skills"):
        print(f"  {relative}")
    if not args.apply:
        print("ÖNİZLEME: hiçbir dosya değişmedi. Uygulamak için --apply ekle.")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = vault / ".beyin" / "backups" / stamp
    for relative in (*GENERATED, *RUNTIME):
        existing = vault / relative
        if existing.is_file():
            copy_file(existing, backup / relative)

    canonical_text = source_instructions.read_text(encoding="utf-8")
    header = "<!-- GENERATED: edit .beyin/instructions.md, then run scripts/render_integrations.py -->\n\n"
    if canonical_text.startswith(header):
        canonical_text = canonical_text[len(header):]
    instructions.parent.mkdir(parents=True, exist_ok=True)
    instructions.write_text(canonical_text, encoding="utf-8")

    config = vault / ".beyin/config.json"
    if not config.exists():
        copy_file(TEMPLATE / ".beyin/config.json", config)

    for relative in RUNTIME:
        copy_file(TEMPLATE / relative, vault / relative)
    shutil.copytree(TEMPLATE / ".beyin" / "skills", vault / ".beyin" / "skills", dirs_exist_ok=True)

    platform = args.platform
    if platform == "auto":
        in_wsl = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
        if os.name == "nt":
            platform = "windows-native"
        else:
            platform = "windows-wsl" if in_wsl and str(vault).startswith("/mnt/") else "portable"
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "render_integrations.py"), "--root", str(vault), "--platform", platform],
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"üretim başarısız; yedek: {backup}", file=sys.stderr)
        return result.returncode
    if not args.defer_version_stamp:
        (vault / ".beyin-multi-version").write_text(f"{MULTI_VERSION}\n", encoding="utf-8")
        version_message = f"multi sürüm: {MULTI_VERSION}"
    else:
        version_message = "multi sürüm damgası finalize aşamasına bırakıldı"
    print(
        f"çoklu-AI katmanı kuruldu ({platform}); {version_message}; "
        f"değiştirilen adaptörlerin yedeği: {backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
