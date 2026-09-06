#!/usr/bin/env python3
"""Smart Note Merge - Akıllı Not Birleştirme ve Güvenli Yönlendirme.

İki notu birleştirirken:
  1. Frontmatter'ları (etiketler, taksonomi, timeline) akıllıca birleştirir (union).
  2. Eski notun başlığını/adını hedef notun `aliases:` listesine ekler.
  3. İçeriği hedef nota ekler.
  4. Kaynak notu ASLA silmez; yerine `redirect: [[HedefNot]]` koyar.
  5. Kasadaki tüm `[[KaynakNot]]` bağlantılarını `[[HedefNot]]` olarak günceller.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Set, Tuple

WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")


def parse_frontmatter_and_body(content: str) -> Tuple[Dict[str, Any], str, str]:
    """YAML frontmatter ve gövdeyi ayrıştırır."""
    if not content.startswith("---"):
        return {}, content, ""

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content, ""

    raw_yaml = parts[1]
    body = parts[2].strip()

    # Basit YAML parser
    fm: Dict[str, Any] = {}
    for line in raw_yaml.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().lower()
            v = v.strip().strip('"').strip("'")
            if v.startswith("[") and v.endswith("]"):
                fm[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
            else:
                fm[k] = v
    return fm, body, raw_yaml


def dump_frontmatter(fm: Dict[str, Any]) -> str:
    """Frontmatter sözlüğünü YAML formatına döker."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            items_str = ", ".join(f'"{x}"' if " " in str(x) else str(x) for x in v)
            lines.append(f"{k}: [{items_str}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def smart_merge(
    source_path: Path,
    target_path: Path,
    vault_root: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """İki notu birleştirir ve yönlendirmeleri uygular."""
    if not source_path.exists():
        raise FileNotFoundError(f"Kaynak not bulunamadı: {source_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Hedef not bulunamadı: {target_path}")
    if source_path.resolve() == target_path.resolve():
        raise ValueError("Kaynak ve hedef not aynı dosya olamaz; bir not kendisiyle birleştirilemez.")

    source_content = source_path.read_text(encoding="utf-8", errors="replace")
    target_content = target_path.read_text(encoding="utf-8", errors="replace")

    source_fm, source_body, _ = parse_frontmatter_and_body(source_content)
    target_fm, target_body, _ = parse_frontmatter_and_body(target_content)

    source_stem = source_path.stem
    target_stem = target_path.stem
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Frontmatter Birleştirme
    merged_fm = dict(target_fm)

    # Etiketler (Tags)
    source_tags = set(source_fm.get("tags", [])) if isinstance(source_fm.get("tags"), list) else set()
    target_tags = set(target_fm.get("tags", [])) if isinstance(target_fm.get("tags"), list) else set()
    merged_fm["tags"] = sorted(list(source_tags | target_tags))

    # Aliases
    target_aliases = set(target_fm.get("aliases", [])) if isinstance(target_fm.get("aliases"), list) else set()
    target_aliases.add(source_stem)
    if "title" in source_fm and source_fm["title"]:
        target_aliases.add(str(source_fm["title"]))
    merged_fm["aliases"] = sorted(list(target_aliases))
    merged_fm["updated"] = today

    # 2. Gövde Birleştirme
    merged_body = (
        f"{target_body}\n\n"
        f"---\n\n"
        f"## 📎 Birleştirilen Not: [[{source_stem}]]\n"
        f"> *Bu içerik {today} tarihinde [[{source_stem}]] sayfasından taşındı.*\n\n"
        f"{source_body}\n"
    )

    new_target_content = f"{dump_frontmatter(merged_fm)}\n\n{merged_body}"

    # 3. Kaynak Notu Yönlendirmeye Çevirme (Silme Yok!)
    redirect_fm = {
        "redirect": f"[[{target_stem}]]",
        "type": "redirect",
        "retired_at": today,
        "tags": ["redirect"],
    }
    redirect_content = (
        f"{dump_frontmatter(redirect_fm)}\n\n"
        f"# {source_stem}\n\n"
        f"> [!NOTE] Bu not [[{target_stem}]] ile birleştirildi\n"
        f"> Güncel içerik ve detaylar için: [[{target_stem}]]\n"
    )

    # 4. Vault Genelinde Link Güncelleme
    updated_files: List[str] = []
    link_pattern = re.compile(rf"\[\[{re.escape(source_stem)}(\|[^\]]+)?\]\]", re.IGNORECASE)

    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", ".git", "cache"}]
        for f in files:
            if f.endswith(".md"):
                file_p = Path(root) / f
                if file_p.resolve() in (source_path.resolve(), target_path.resolve()):
                    continue
                try:
                    txt = file_p.read_text(encoding="utf-8", errors="replace")
                    if link_pattern.search(txt):
                        # Linki hedefle değiştir
                        def _repl(match):
                            alias_part = match.group(1) or ""
                            return f"[[{target_stem}{alias_part}]]"

                        new_txt = link_pattern.sub(_repl, txt)
                        if not dry_run:
                            file_p.write_text(new_txt, encoding="utf-8")
                        updated_files.append(file_p.relative_to(vault_root).as_posix())
                except Exception:
                    pass

    if not dry_run:
        target_path.write_text(new_target_content, encoding="utf-8")
        source_path.write_text(redirect_content, encoding="utf-8")

    return {
        "source": str(source_path),
        "target": str(target_path),
        "redirect_created": True,
        "links_updated_count": len(updated_files),
        "links_updated_files": updated_files,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smart Note Merge - Güvenli Not Birleştirme")
    parser.add_argument("--source", required=True, help="Birleştirilip emekli edilecek kaynak not")
    parser.add_argument("--target", required=True, help="İçeriği devralacak hedef not")
    parser.add_argument("--vault", default=".", help="Vault kök dizini")
    parser.add_argument("--dry-run", action="store_true", help="Yazmadan yapılacak değişiklikleri listele")
    args = parser.parse_args()

    vault_root = Path(args.vault).resolve()
    source_p = Path(args.source).resolve()
    target_p = Path(args.target).resolve()

    res = smart_merge(source_p, target_p, vault_root, dry_run=args.dry_run)

    mode_label = "[DRY-RUN] " if res["dry_run"] else ""
    print(f"{mode_label}Not başarıyla birleştirildi:")
    print(f"  Kaynak (Redirect): {res['source']}")
    print(f"  Hedef (Birleşen): {res['target']}")
    print(f"  Güncellenen Wikilink Sayısı: {res['links_updated_count']}")
    if res["links_updated_files"]:
        for f in res["links_updated_files"][:10]:
            print(f"    - {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
