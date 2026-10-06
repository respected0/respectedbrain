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

from respectedbrain.core.context import AppContext
from respectedbrain.maintenance import selected_vault, mutable_target, note_target, safe_walk
from respectedbrain.maintenance._atomic import replace_staged
from respectedbrain.core.config import atomic_write_bytes

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
import tempfile
import json
from typing import Any, Dict, List, Set, Tuple






def _atomic_write_text(path: Path, content: str, *, temp_dir: Path | None = None) -> None:
    """Write text atomically via temporary file and atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=temp_dir or path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        replace_staged(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


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
    """Frontmatter sözlüğünü güvenli YAML formatına döker."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            items_str = ", ".join(json.dumps(str(x), ensure_ascii=False) if any(c in str(x) for c in (":", " ", "#", "[", "]")) else str(x) for x in v)
            lines.append(f"{k}: [{items_str}]")
        else:
            val_str = str(v)
            if val_str.startswith("[[") and val_str.endswith("]]"):
                lines.append(f"{k}: {val_str}")
            elif any(ch in val_str for ch in (":", "#", "[", "]", "{", "}", "\"", "'")) or " " in val_str:
                lines.append(f"{k}: {json.dumps(val_str, ensure_ascii=False)}")
            else:
                lines.append(f"{k}: {val_str}")
    lines.append("---")
    return "\n".join(lines)


def _ensure_string_list(val: Any) -> list[str]:
    """YAML değerini güvenli şekilde temiz string listesine dönüştürür."""
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        cleaned = val.strip()
        return [cleaned] if cleaned else []
    return [str(val).strip()]


def smart_merge(
    source_path: Path,
    target_path: Path,
    vault_root: Path,
    dry_run: bool = False,
    *, temp_dir: Path | None = None,
) -> Dict[str, Any]:
    """İki notu birleştirir ve yönlendirmeleri uygular."""
    source_path = note_target(vault_root, source_path)
    target_path = note_target(vault_root, target_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Kaynak not bulunamadı: {source_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Hedef not bulunamadı: {target_path}")
    if source_path.resolve() == target_path.resolve():
        raise ValueError("Kaynak ve hedef not aynı dosya olamaz; bir not kendisiyle birleştirilemez.")

    if temp_dir is not None:
        temp_dir.mkdir(parents=True, exist_ok=True)
    before_images = {path: path.read_bytes() for path in (source_path, target_path)}
    source_content = before_images[source_path].decode('utf-8')
    target_content = before_images[target_path].decode('utf-8')

    source_fm, source_body, _ = parse_frontmatter_and_body(source_content)
    target_fm, target_body, target_yaml = parse_frontmatter_and_body(target_content)

    source_stem = source_path.stem
    target_stem = target_path.stem
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Frontmatter Birleştirme
    merged_fm = dict(target_fm)

    # Etiketler (Tags)
    source_tags = set(_ensure_string_list(source_fm.get("tags")))
    target_tags = set(_ensure_string_list(target_fm.get("tags")))
    merged_fm["tags"] = sorted(list(source_tags | target_tags))

    # Aliases
    source_aliases = set(_ensure_string_list(source_fm.get("aliases")))
    target_aliases = set(_ensure_string_list(target_fm.get("aliases")))
    all_aliases = source_aliases | target_aliases
    all_aliases.add(source_stem)
    if "title" in source_fm and source_fm["title"]:
        all_aliases.add(str(source_fm["title"]).strip())
    merged_fm["aliases"] = sorted(list(all_aliases))
    merged_fm["updated"] = today

    # 2. Gövde Birleştirme
    merged_body = (
        f"{target_body}\n\n"
        f"---\n\n"
        f"## 📎 Birleştirilen Not: [[{source_stem}]]\n"
        f"> *Bu içerik {today} tarihinde [[{source_stem}]] sayfasından taşındı.*\n\n"
        f"{source_body}\n"
    )

    # Preserve unrecognized and nested YAML verbatim; only update owned fields.
    fields = {key: merged_fm[key] for key in ('tags', 'aliases', 'updated')}
    kept, skip = [], False
    for line in target_yaml.splitlines():
        key = re.match(r'^([A-Za-z0-9_-]+):', line)
        if key:
            skip = key.group(1).lower() in fields
        if not skip:
            kept.append(line)
    additions = dump_frontmatter(fields).splitlines()[1:-1]
    frontmatter = '\n'.join(['---', *kept, *additions, '---'])
    new_target_content = f"{frontmatter}\n\n{merged_body}"

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
    edits = [(target_path, target_content, new_target_content), (source_path, source_content, redirect_content)]
    link_pattern = re.compile(rf"\[\[{re.escape(source_stem)}(#[^\]\|]+)?(\|[^\]]+)?\]\]", re.IGNORECASE)

    for root, dirs, files in safe_walk(vault_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", ".git", "cache"}]
        for f in files:
            if f.endswith(".md"):
                file_p = Path(root) / f
                if file_p.resolve() in (source_path.resolve(), target_path.resolve()):
                    continue
                original = file_p.read_bytes()
                txt = original.decode('utf-8')
                if link_pattern.search(txt):
                    # Linki hedefle değiştir (anchor ve alias korunur)
                    def _repl(match):
                        anchor_part = match.group(1) or ""
                        alias_part = match.group(2) or ""
                        return f"[[{target_stem}{anchor_part}{alias_part}]]"

                    new_txt = link_pattern.sub(_repl, txt)
                    before_images[file_p] = original
                    edits.append((file_p, txt, new_txt))
                    updated_files.append(file_p.relative_to(vault_root).as_posix())

    if not dry_run:
        completed = []
        try:
            for path, before, after in edits:
                note_target(vault_root, path)
                if path.read_bytes() != before_images[path]:
                    raise ValueError(f"Note changed during merge: {path}")
                _atomic_write_text(path, after, temp_dir=temp_dir)
                completed.append((path, before, after))
            for path, before, after in completed:
                note_target(vault_root, path)
                if path.read_bytes() != after.encode('utf-8'):
                    raise ValueError(f'Note changed before merge completed: {path}')
        except Exception:
            for path, before, after in reversed(completed):
                note_target(vault_root, path)
                if path.read_bytes() != after.encode('utf-8'):
                    raise ValueError(f"Merge rollback conflict; preserve merged content: {path}")
                atomic_write_bytes(path, before_images[path])
            raise

    return {
        "source": str(source_path),
        "target": str(target_path),
        "redirect_created": True,
        "links_updated_count": len(updated_files),
        "links_updated_files": updated_files,
        "dry_run": dry_run,
    }


def main(argv=None, *, ctx: AppContext | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smart Note Merge - Güvenli Not Birleştirme")
    parser.add_argument("--source", required=True, help="Birleştirilip emekli edilecek kaynak not")
    parser.add_argument("--target", required=True, help="İçeriği devralacak hedef not")
    parser.add_argument("--vault", default=None, help="Vault kök dizini")
    parser.add_argument("--dry-run", action="store_true", help="Yazmadan yapılacak değişiklikleri listele")
    args = parser.parse_args(argv)

    vault_root = selected_vault(ctx, args.vault)
    source_p = mutable_target(ctx, Path(args.source))
    target_p = mutable_target(ctx, Path(args.target))

    res = smart_merge(source_p, target_p, vault_root, dry_run=args.dry_run, temp_dir=ctx.paths.cache_dir if ctx else None)

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
