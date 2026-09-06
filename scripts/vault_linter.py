#!/usr/bin/env python3
"""Vault Linter - Kasa Sağlığı, Bağlantı ve Tazelik Denetleyicisi (wiki-lint).

Respected Brain içindeki:
  1. Kırık wikilink'leri ([[Ölü Link]])
  2. Hiçbir yerden bağlantı almayan yetim (orphan) sayfaları
  3. Geçersiz YAML frontmatter bloklarını
  4. Dosya adlarındaki en-dash/em-dash tuzaklarını (Obsidian link bozucular)
  5. OKM / Freshness Policy ihlallerini (tarihsiz sayaç / hızlı gerçek iddiaları)
tespit ederek deterministik rapor üretir.
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

# Hızlı gerçek (fast-fact / sayaç) olup tarihsiz şimdiki zaman kipiyle yazılmış kalıplar
UNSTAMPED_FAST_FACT_RE = re.compile(
    r"(?i)\b(?:pipeline|bakiye|anlaşma|açık iş|stok|deal|open tickets)\s*(?:has|is at|toplamı|sayısı|var|bulunuyor)\s*[:=]?\s*\d+"
)
DATE_STAMP_RE = re.compile(r"(?i)(?:as of|\bas of\b|\bitibarıyla\b|\btarihinde\b)\s*\d{4}")

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
    env_vault = os.environ.get("RESPECTED_VAULT") or os.environ.get("VAULT_ROOT")
    if env_vault:
        p = Path(env_vault).expanduser().resolve()
        if p.is_dir():
            return p
    docs = Path.home() / "Documents"
    if docs.is_dir():
        try:
            for candidate_dir in docs.iterdir():
                if candidate_dir.is_dir() and ((candidate_dir / "knowledge").is_dir() or (candidate_dir / ".beyin").is_dir()):
                    return candidate_dir
        except OSError:
            pass
    return cur


def lint_vault(vault_root: Path) -> dict[str, Any]:
    """Vault genelinde bağlantı, yapı, dosya adı ve tazelik denetimi yapar."""
    all_md_files: dict[str, Path] = {}  # stem.lower() -> Path
    relative_paths: set[str] = set()
    file_contents: dict[Path, str] = {}
    filename_issues: list[dict[str, str]] = []

    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for file in files:
            if file.endswith(".md"):
                full_p = Path(root) / file
                rel_p = full_p.relative_to(vault_root).as_posix()
                stem = full_p.stem.lower()
                all_md_files[stem] = full_p
                relative_paths.add(rel_p.lower())

                # En-dash / Em-dash kontrolü
                if "—" in file or "–" in file:
                    filename_issues.append({
                        "file": rel_p,
                        "issue": "Dosya adında ASCII dışı uzun tire (— veya –) var. Standart '-' (ASCII 0x2D) kullanın.",
                    })

                try:
                    file_contents[full_p] = full_p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    dead_links: list[dict[str, str]] = []
    incoming_links_count: dict[Path, int] = {p: 0 for p in file_contents.keys()}
    frontmatter_issues: list[dict[str, str]] = []
    freshness_warnings: list[dict[str, str]] = []

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

        # Freshness (Tazelik / OKM) Kontrolü (Sadece tarihli olmayan ana bilgi/proje sayfalarında)
        is_dated_container = any(rel_src.startswith(d) for d in ["daily/", "Logs/", "📦 900-Archive/"])
        if not is_dated_container:
            for line_no, line in enumerate(content.splitlines(), 1):
                if UNSTAMPED_FAST_FACT_RE.search(line):
                    if not DATE_STAMP_RE.search(line):
                        freshness_warnings.append({
                            "file": f"{rel_src}:{line_no}",
                            "line": line.strip()[:80],
                            "warning": "Tarihsiz sayaç/hızlı gerçek iddiası. '(as of YYYY-MM-DD)' ekleyin.",
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

    is_healthy = (
        len(dead_links) == 0
        and len(frontmatter_issues) == 0
        and len(filename_issues) == 0
    )

    return {
        "vault_root": str(vault_root),
        "total_markdown_files": len(file_contents),
        "dead_links_count": len(dead_links),
        "dead_links": dead_links[:100],  # Bounded rapor
        "orphan_pages_count": len(orphan_pages),
        "orphan_pages": orphan_pages[:100],
        "frontmatter_issues_count": len(frontmatter_issues),
        "frontmatter_issues": frontmatter_issues,
        "filename_issues_count": len(filename_issues),
        "filename_issues": filename_issues,
        "freshness_warnings_count": len(freshness_warnings),
        "freshness_warnings": freshness_warnings[:100],
        "is_healthy": is_healthy,
    }


def fix_dashes(vault_root: Path) -> int:
    """Dosya adlarındaki em-dash ve en-dash karakterlerini standart ASCII '-' ile değiştirir."""
    fixed = 0
    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for file in files:
            if file.endswith(".md") and ("—" in file or "–" in file):
                old_p = Path(root) / file
                new_name = file.replace("—", "-").replace("–", "-")
                new_p = Path(root) / new_name
                if not new_p.exists():
                    old_p.rename(new_p)
                    fixed += 1
    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault Linter - Kasa Bağlantı, Sağlık ve Tazelik Kontrolü")
    parser.add_argument("--vault", help="Denetlenecek vault kök dizini")
    parser.add_argument("--json", action="store_true", help="JSON formatında çıktı")
    parser.add_argument("--fix-dashes", action="store_true", help="Dosya adlarındaki uzun tireleri otomatik ASCII '-' yap")
    args = parser.parse_args()

    v_root = resolve_vault_root(Path(args.vault) if args.vault else None)

    if args.fix_dashes:
        count = fix_dashes(v_root)
        print(f"Toplam {count} dosya adındaki tire ASCII '-' olarak düzeltildi.")

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

        if results['filename_issues']:
            print(f"\nDosya Adı Tire Sorunları: {results['filename_issues_count']}")
            for fni in results['filename_issues']:
                print(f"  [TİRE HATASI] {fni['file']}: {fni['issue']}")

        if results['frontmatter_issues']:
            print(f"\nFrontmatter Sorunları: {results['frontmatter_issues_count']}")
            for fi in results['frontmatter_issues']:
                print(f"  [FRONTMATTER] {fi['file']}: {fi['issue']}")

        if results['freshness_warnings']:
            print(f"\nTazelik (OKM / Freshness) Uyarıları: {results['freshness_warnings_count']}")
            for fw in results['freshness_warnings'][:10]:
                print(f"  [TAZELİK] {fw['file']}: {fw['warning']} -> '{fw['line']}'")

        print("\nGenel Durum: " + ("TEMİZ / SAĞLIKLI" if results["is_healthy"] else "DİKKAT GEREKİYOR"))

    return 0 if results["is_healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
