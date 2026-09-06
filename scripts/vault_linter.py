#!/usr/bin/env python3
"""Vault Linter - Kasa Sağlığı ve Bağlantı Denetleyicisi (wiki-lint).

Respected Brain içindeki kırık wikilink'leri ([[Ölü Link]]), hiçbir yerden
bağlantı almayan yetim (orphan) sayfaları ve geçersiz YAML frontmatter
bloklarını tespit ederek deterministik rapor üretir.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

# Wikilink regex: [[Hedef]] veya [[Hedef|Görünen İsim]] veya [[Hedef#Başlık]]
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")

EXCLUDED_DIRS = {
    ".git",
    ".beyin",
    "cache",
    ".claude",
    ".gemini",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    ".vault-meta",
}

IGNORE_ORPHAN_BASENAMES = {
    "dashboard",
    "vault-map",
    "skills-map",
    "index",
    "overview",
    "readme",
    "core",
    "kurallar",
    "last-session",
    "threads",
    "journal",
}


def resolve_vault_root(candidate: Path | None = None) -> Path:
    """Vault kökünü bulur."""
    if candidate:
        return candidate.resolve()
    cur = Path.cwd().resolve()
    for p in [cur, *cur.parents]:
        if (p / "knowledge").is_dir() or (p / ".beyin").is_dir():
            return p
    default_win = Path(r"C:\Users\Furkan\Documents\RespectedOS")
    if default_win.is_dir():
        return default_win
    return cur


def lint_vault(vault_root: Path) -> dict[str, Any]:
    """Vault genelinde bağlantı ve yapı denetimi yapar."""
    all_md_files: dict[str, Path] = {}  # stem.lower() -> Path
    relative_paths: set[str] = set()
    file_contents: dict[Path, str] = {}

    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for file in files:
            if file.endswith(".md"):
                full_p = Path(root) / file
                rel_p = full_p.relative_to(vault_root).as_posix()
                stem = full_p.stem.lower()
                all_md_files[stem] = full_p
                relative_paths.add(rel_p.lower())
                try:
                    file_contents[full_p] = full_p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    dead_links: list[dict[str, str]] = []
    incoming_links_count: dict[Path, int] = {p: 0 for p in file_contents.keys()}
    frontmatter_issues: list[dict[str, str]] = []

    for file_path, content in file_contents.items():
        rel_src = file_path.relative_to(vault_root).as_posix()

        # Frontmatter kontrolü
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) < 3:
                frontmatter_issues.append({
                    "file": rel_src,
                    "issue": "Kapanmamış YAML frontmatter (eksik ikinci '---')",
                })

        # Wikilink kontrolü
        matches = WIKILINK_RE.findall(content)
        for target in matches:
            target_clean = target.strip()
            if not target_clean:
                continue

            target_stem = Path(target_clean).stem.lower()
            target_rel = target_clean.replace("\\", "/").lower()
            if not target_rel.endswith(".md"):
                target_rel_with_ext = target_rel + ".md"
            else:
                target_rel_with_ext = target_rel

            # Hedef var mı?
            resolved = False
            # 1. Stem bazlı eşleşme
            if target_stem in all_md_files:
                resolved = True
                matched_p = all_md_files[target_stem]
                incoming_links_count[matched_p] = incoming_links_count.get(matched_p, 0) + 1
            # 2. Göreceli yol eşleşmesi
            elif target_rel_with_ext in relative_paths:
                resolved = True
                for p in file_contents.keys():
                    if p.relative_to(vault_root).as_posix().lower() == target_rel_with_ext:
                        incoming_links_count[p] = incoming_links_count.get(p, 0) + 1
                        break

            if not resolved:
                dead_links.append({
                    "source": rel_src,
                    "target": target_clean,
                })

    # Yetim (Orphan) Sayfaları Belirleme
    orphan_pages: list[str] = []
    for p, count in incoming_links_count.items():
        stem = p.stem.lower()
        if count == 0 and stem not in IGNORE_ORPHAN_BASENAMES:
            rel = p.relative_to(vault_root).as_posix()
            # Şablonlar, archive ve dump klasörlerindeki notları orphan sayma
            if not any(rel.startswith(ignore) for ignore in ["📋 Templates", "📦 900-Archive", "📥 000-Inbox/Dump"]):
                orphan_pages.append(rel)

    return {
        "vault_root": str(vault_root),
        "total_markdown_files": len(file_contents),
        "dead_links_count": len(dead_links),
        "dead_links": dead_links[:100],  # Bounded rapor
        "orphan_pages_count": len(orphan_pages),
        "orphan_pages": orphan_pages[:100],
        "frontmatter_issues_count": len(frontmatter_issues),
        "frontmatter_issues": frontmatter_issues,
        "is_healthy": len(dead_links) == 0 and len(frontmatter_issues) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault Linter - Kasa Bağlantı ve Sağlık Kontrolü")
    parser.add_argument("--vault", help="Denetlenecek vault kök dizini")
    parser.add_argument("--json", action="store_true", help="JSON formatında çıktı")
    args = parser.parse_args()

    v_root = resolve_vault_root(Path(args.vault) if args.vault else None)
    results = lint_vault(v_root)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"=== Vault Linter Raporu: {results['vault_root']} ===")
        print(f"Toplam Not Sayısı: {results['total_markdown_files']}")
        print(f"Kırık Link Sayısı: {results['dead_links_count']}")
        if results['dead_links']:
            for dl in results['dead_links'][:15]:
                print(f"  [ÖLÜ LİNK] {dl['source']} -> [[{dl['target']}]]")
            if results['dead_links_count'] > 15:
                print(f"  ... ve {results['dead_links_count'] - 15} adet daha.")

        print(f"\nYetim (Bağlantısız) Sayfa Sayısı: {results['orphan_pages_count']}")
        if results['orphan_pages']:
            for op in results['orphan_pages'][:15]:
                print(f"  [YETİM SAYFA] {op}")
            if results['orphan_pages_count'] > 15:
                print(f"  ... ve {results['orphan_pages_count'] - 15} adet daha.")

        if results['frontmatter_issues']:
            print(f"\nFrontmatter Sorunları: {results['frontmatter_issues_count']}")
            for fi in results['frontmatter_issues']:
                print(f"  [FRONTMATTER] {fi['file']}: {fi['issue']}")

        print("\nGenel Durum: " + ("TEMİZ / SAĞLIKLI" if results["is_healthy"] else "DİKKAT GEREKİYOR"))

    return 0 if results["is_healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
