#!/usr/bin/env python3
"""Yerel Full-Text Search (FTS5) arama motoru - İkinci Beyin.

Harici bağımlılık veya API ücreti olmadan SQLite FTS5 ve BM25 kullanarak
vault içindeki tüm notlarda yüksek hızlı, anlamsal ve kök tabanlı arama yapar.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

from respectedbrain.core.context import AppContext
from respectedbrain.core.coordination import guarded_writer
from respectedbrain.core.platform import path_within_vault

_FRONTMATTER = re.compile(r"\A\ufeff?---\r?\n(.*?)^---[ \t]*(?:\r?\n|$)", re.MULTILINE | re.DOTALL)


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
    metadata, _ = parse_markdown_meta(head)
    return metadata, _FRONTMATTER.match(head) is not None


def parse_markdown_meta(content: str) -> tuple[dict[str, Any], str]:
    """Basit frontmatter ayrıştırıcı ve metin gövdesi."""
    frontmatter: dict[str, Any] = {}
    body = content

    match = _FRONTMATTER.match(content)
    if match:
        raw_fm = match[1]
        body = content[match.end():].strip()
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

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.vault_root = ctx.paths.vault_root
        self.db_path = ctx.paths.cache_dir / "search_index.db"
        self._validate_db_path()
        from respectedbrain.core.coordination import writer_lease
        with writer_lease(ctx):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    @contextmanager
    def _get_connection(self):
        self._validate_db_path()
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    def _validate_db_path(self) -> None:
        for path in (self.db_path, *(self.db_path.with_name(self.db_path.name + suffix) for suffix in ('-journal', '-wal', '-shm'))):
            if not path_within_vault(path, self.ctx.paths.data_root):
                raise ValueError("unsafe-search-database")

    def _excluded(self, relative: str) -> bool:
        parts = Path(relative).parts
        return any(excluded in parts if '/' not in excluded else relative == excluded or relative.startswith(excluded+'/') for excluded in self.EXCLUDED_DIRS)

    def _visible_path(self, relative: str) -> bool:
        return not self._excluded(relative) and path_within_vault(self.vault_root / relative, self.vault_root)

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

    @guarded_writer(busy_result=None)
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
                if self._excluded(rel_root) or not path_within_vault(Path(root), self.vault_root):
                    dirs.clear()
                    continue
                dirs[:] = [directory for directory in dirs if self._visible_path((Path(rel_root)/directory).as_posix())]

                for f in files:
                    if not f.endswith(".md"):
                        continue

                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(self.vault_root).as_posix()
                    if not self._visible_path(rel_path):
                        continue
                    current_files.add(rel_path)

                    try:
                        stat = full_path.stat()
                        mtime = stat.st_mtime
                    except OSError:
                        continue

                    try:
                        payload = full_path.read_bytes()
                        text = payload.decode("utf-8", errors="replace")
                    except OSError:
                        continue

                    sha256 = hashlib.sha256(payload).hexdigest()
                    if not force and rel_path in existing_records:
                        _, prev_sha = existing_records[rel_path]
                        if prev_sha == sha256:
                            con.execute("UPDATE files_meta SET mtime = ? WHERE rel_path = ?", (mtime, rel_path))
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
        if not clean_query or limit <= 0:
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
                    if not self._visible_path(row['rel_path']):
                        continue
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
                    WHERE (title LIKE ? OR rel_path LIKE ?)
                """
                like_expr = f"%{terms[0]}%"
                fallback_params = [like_expr, like_expr]
                if category:
                    fallback_sql += " AND category = ?"
                    fallback_params.append(category)
                fallback_sql += " LIMIT ?"
                fallback_params.append(limit)
                cursor = con.execute(fallback_sql, fallback_params)
                for row in cursor.fetchall():
                    if not self._visible_path(row['rel_path']):
                        continue
                    results.append({
                        "path": row["rel_path"],
                        "title": row["title"],
                        "category": row["category"],
                        "tags": "",
                        "snippet": "",
                        "score": 1.0,
                    })

        return results

    def get_backlinks(self, target_name: str, limit: int = 100) -> list[str]:
        """Not adına verilen referansları (backlinks) SQLite FTS5 üzerinden disk taraması yapmadan getirir."""
        clean = target_name.strip().replace('\\', '/')
        if clean.endswith('.md'):
            clean = clean[:-3]
        terms = re.findall(r'\w+', clean)
        if not terms or limit <= 0:
            return []
        pattern = re.compile(rf"\[\[{re.escape(clean)}(?:\.md)?(?:[|#][^\]]*)?\]\]", re.IGNORECASE)
        backlinks: list[str] = []
        with self._get_connection() as con:
            try:
                cursor = con.execute(
                    "SELECT rel_path, content FROM vault_fts WHERE vault_fts MATCH ? LIMIT ?",
                    (' AND '.join(f'"{term}"' for term in terms), limit),
                )
                for row in cursor.fetchall():
                    if self._visible_path(row['rel_path']) and pattern.search(row["content"]):
                        backlinks.append(row["rel_path"])
            except sqlite3.OperationalError:
                pass
        return backlinks
