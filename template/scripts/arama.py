#!/usr/bin/env python3
"""Yerel Full-Text Search (FTS5) arama motoru - İkinci Beyin.

Harici bağımlılık veya API ücreti olmadan SQLite FTS5 ve BM25 kullanarak
vault içindeki tüm notlarda yüksek hızlı, anlamsal ve kök tabanlı arama yapar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def resolve_vault_root(candidate: Path | None = None) -> Path:
    """Vault kök dizinini belirler."""
    if candidate:
        resolved = candidate.expanduser().resolve()
        if (resolved / "knowledge").is_dir() or (resolved / ".beyin").is_dir():
            return resolved
        return resolved

    # 1. Mevcut dizin ve üst dizinler
    cur = Path.cwd().resolve()
    for p in [cur, *cur.parents]:
        if (p / ".beyin").is_dir() and (p / "knowledge").is_dir():
            return p

    # 2. Ortam değişkeni (RESPECTED_VAULT veya VAULT_ROOT)
    env_vault = os.environ.get("RESPECTED_VAULT") or os.environ.get("VAULT_ROOT")
    if env_vault:
        p = Path(env_vault).expanduser().resolve()
        if p.is_dir():
            return p

    # 3. Kullanıcının Documents dizinindeki vault adayları
    docs = Path.home() / "Documents"
    if docs.is_dir():
        try:
            for candidate_dir in docs.iterdir():
                if candidate_dir.is_dir() and ((candidate_dir / "knowledge").is_dir() or (candidate_dir / ".beyin").is_dir()):
                    return candidate_dir
        except OSError:
            pass

    # 4. Bulunamazsa mevcut çalışma dizini
    return cur


def read_head(path: Path, max_chars: int = 1200) -> str:
    """Dosyanın yalnızca ilk max_chars karakterini okur (frontmatter ve başlık I/O optimizasyonu)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(max_chars)
    except OSError:
        return ""


def parse_frontmatter_head(path: Path, max_chars: int = 1200) -> tuple[dict[str, Any], bool]:
    """Büyük dosyaları tamamen belleğe okumadan, ilk 1200 karakterden frontmatter ayrıştırır."""
    head = read_head(path, max_chars=max_chars)
    if not head.startswith("---"):
        return {}, False
    parts = head.split("---", 2)
    if len(parts) < 3:
        return {}, False
    fm: dict[str, Any] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                fm[key] = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
            else:
                fm[key] = val
    return fm, True


def parse_markdown_meta(content: str) -> tuple[dict[str, Any], str]:
    """Basit frontmatter ayrıştırıcı ve metin gövdesi."""
    frontmatter: dict[str, Any] = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_fm = parts[1]
            body = parts[2].strip()
            for line in raw_fm.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip().lower()
                    val = val.strip().strip('"').strip("'")
                    if val.startswith("[") and val.endswith("]"):
                        frontmatter[key] = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
                    else:
                        frontmatter[key] = val

    return frontmatter, body


from contextlib import contextmanager

class SearchEngine:
    """SQLite FTS5 tabanlı yerel arama motoru."""

    EXCLUDED_DIRS = {
        ".git",
        ".beyin/cache",
        "cache",
        "node_modules",
        ".claude",
        ".gemini",
        "venv",
        ".venv",
        "__pycache__",
    }

    def __init__(self, vault_root: Path, db_path: Path | None = None) -> None:
        self.vault_root = vault_root.resolve()
        if db_path is None:
            cache_dir = self.vault_root / ".beyin" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = cache_dir / "search_index.db"
        else:
            self.db_path = db_path
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def _get_connection(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    def _init_db(self) -> None:
        with self._get_connection() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS files_meta (
                    rel_path TEXT PRIMARY KEY,
                    mtime REAL NOT NULL,
                    sha256 TEXT NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL
                );
            """)
            con.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
                    rel_path UNINDEXED,
                    title,
                    content,
                    tags,
                    category,
                    tokenize = 'unicode61'
                );
            """)
            con.commit()

    def index_vault(self, force: bool = False) -> dict[str, int]:
        """Vault içindeki tüm .md dosyalarını artımlı (incremental) olarak indeksler."""
        indexed = 0
        skipped = 0
        deleted = 0

        with self._get_connection() as con:
            cursor = con.execute("SELECT rel_path, mtime, sha256 FROM files_meta")
            existing_records = {row["rel_path"]: (row["mtime"], row["sha256"]) for row in cursor.fetchall()}

            current_files: set[str] = set()

            for root, dirs, files in os.walk(self.vault_root):
                rel_root = Path(root).relative_to(self.vault_root).as_posix()
                if any(rel_root == exc or rel_root.startswith(f"{exc}/") for exc in self.EXCLUDED_DIRS):
                    dirs.clear()
                    continue

                for f in files:
                    if not f.endswith(".md"):
                        continue

                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(self.vault_root).as_posix()
                    current_files.add(rel_path)

                    try:
                        stat = full_path.stat()
                        mtime = stat.st_mtime
                    except OSError:
                        continue

                    if not force and rel_path in existing_records:
                        prev_mtime, _ = existing_records[rel_path]
                        if abs(prev_mtime - mtime) < 0.001:
                            skipped += 1
                            continue

                    try:
                        text = full_path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue

                    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    if not force and rel_path in existing_records:
                        _, prev_sha = existing_records[rel_path]
                        if prev_sha == sha256:
                            skipped += 1
                            continue

                    fm, body = parse_markdown_meta(text)
                    title = fm.get("title") or full_path.stem
                    raw_tags = fm.get("tags") or ""
                    tags = " ".join(raw_tags) if isinstance(raw_tags, list) else str(raw_tags)
                    category = Path(rel_path).parts[0] if len(Path(rel_path).parts) > 1 else "Root"

                    con.execute("DELETE FROM files_meta WHERE rel_path = ?", (rel_path,))
                    con.execute("DELETE FROM vault_fts WHERE rel_path = ?", (rel_path,))

                    con.execute(
                        "INSERT INTO files_meta (rel_path, mtime, sha256, title, category) VALUES (?, ?, ?, ?, ?)",
                        (rel_path, mtime, sha256, title, category),
                    )
                    con.execute(
                        "INSERT INTO vault_fts (rel_path, title, content, tags, category) VALUES (?, ?, ?, ?, ?)",
                        (rel_path, title, body, tags, category),
                    )
                    indexed += 1

            stale_files = set(existing_records.keys()) - current_files
            for stale in stale_files:
                con.execute("DELETE FROM files_meta WHERE rel_path = ?", (stale,))
                con.execute("DELETE FROM vault_fts WHERE rel_path = ?", (stale,))
                deleted += 1

            con.commit()

        return {"indexed": indexed, "skipped": skipped, "deleted": deleted, "total": len(current_files)}

    def search(self, query: str, limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
        """Sorguyla eşleşen notları BM25 ağırlıklandırmasıyla getirir."""
        clean_query = query.strip()
        if not clean_query:
            return []

        terms = re.findall(r"\w+", clean_query)
        if not terms:
            return []

        fts_expr = " OR ".join(f'"{t}"*' for t in terms)

        sql = """
            SELECT
                rel_path,
                title,
                category,
                tags,
                snippet(vault_fts, 2, '>>>', '<<<', '...', 20) AS snippet,
                bm25(vault_fts, 5.0, 1.0, 3.0, 1.0) AS rank
            FROM vault_fts
            WHERE vault_fts MATCH ?
        """
        params: list[Any] = [fts_expr]

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        results: list[dict[str, Any]] = []
        with self._get_connection() as con:
            try:
                cursor = con.execute(sql, params)
                for row in cursor.fetchall():
                    results.append({
                        "path": row["rel_path"],
                        "title": row["title"],
                        "category": row["category"],
                        "tags": row["tags"],
                        "snippet": row["snippet"].replace("\n", " ").strip(),
                        "score": round(float(row["rank"]), 4),
                    })
            except sqlite3.OperationalError:
                fallback_sql = """
                    SELECT rel_path, title, category, '' AS tags, '' AS snippet, 0.0 AS rank
                    FROM files_meta
                    WHERE title LIKE ? OR rel_path LIKE ?
                    LIMIT ?
                """
                like_expr = f"%{terms[0]}%"
                cursor = con.execute(fallback_sql, (like_expr, like_expr, limit))
                for row in cursor.fetchall():
                    results.append({
                        "path": row["rel_path"],
                        "title": row["title"],
                        "category": row["category"],
                        "tags": "",
                        "snippet": "",
                        "score": 1.0,
                    })

        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="İkinci Beyin Yerel Hibrit Arama")
    parser.add_argument("query", nargs="?", default="", help="Aranacak ifade")
    parser.add_argument("--vault", type=Path, default=None, help="Vault kök dizini")
    parser.add_argument("--reindex", action="store_true", help="Tüm vault'u yeniden indeksle")
    parser.add_argument("--category", type=str, default=None, help="Belirli bir kategoride filtrele")
    parser.add_argument("--limit", type=int, default=10, help="Maksimum sonuç sayısı")
    parser.add_argument("--json", action="store_true", help="JSON formatında çıktı")

    args = parser.parse_args()
    vault = resolve_vault_root(args.vault)
    engine = SearchEngine(vault)

    if args.reindex or not engine.db_path.exists():
        stats = engine.index_vault(force=args.reindex)
        if not args.json:
            print(f"İndeksleme tamamlandı: {stats['indexed']} yeni/güncellenen, {stats['skipped']} değişmeyen, {stats['deleted']} silinen.")

    if not args.query:
        if not args.reindex:
            parser.print_help()
        return 0

    results = engine.search(args.query, limit=args.limit, category=args.category)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    if not results:
        print(f"'{args.query}' için eşleşen not bulunamadı.")
        return 0

    print(f"\n🔍 '{args.query}' için bulunan sonuçlar ({len(results)}):\n" + "=" * 60)
    for idx, r in enumerate(results, 1):
        print(f"[{idx}] {r['title']} ({r['path']}) - Kategori: {r['category']}")
        if r["snippet"]:
            print(f"    Özet: {r['snippet']}")
        print("-" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
