#!/usr/bin/env python3
"""Safe deduplication and repair of daily log session blocks with timestamped backup."""

from __future__ import annotations

import argparse
from datetime import datetime
import difflib
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Sequence


OTURUM_HEADER = re.compile(
    r"^### Oturum\s*\([^)]+\)(?:,\s*compaction\s*öncesi)?\s*$", re.MULTILINE
)


def _extract_minutes(header: str) -> int:
    match = re.search(r"\((\d{2}):(\d{2})\)", header)
    if not match:
        return 0
    return int(match.group(1)) * 60 + int(match.group(2))


def _extract_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{4,}", text.casefold()))


def _is_duplicate_pair(b1: dict[str, Any], b2: dict[str, Any]) -> bool:
    if b1["fingerprint"] == b2["fingerprint"]:
        return True

    t_diff = abs(b1["minutes"] - b2["minutes"])
    if t_diff > 45:
        return False

    body_ratio = difflib.SequenceMatcher(None, b1["body"], b2["body"]).ratio()
    if body_ratio >= 0.50:
        return True

    if b1["baglam"] and b2["baglam"]:
        baglam_ratio = difflib.SequenceMatcher(None, b1["baglam"], b2["baglam"]).ratio()
        if baglam_ratio >= 0.48:
            return True

    w1 = b1["words"]
    w2 = b2["words"]
    if w1 and w2:
        jaccard = len(w1 & w2) / len(w1 | w2)
        if jaccard >= 0.38:
            return True

    return False


def _cluster_blocks(blocks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    n = len(blocks)
    if n <= 1:
        return [[b] for b in blocks]

    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if _is_duplicate_pair(blocks[i], blocks[j]):
                adj[i].add(j)
                adj[j].add(i)

    visited: set[int] = set()
    clusters: list[list[dict[str, Any]]] = []
    for i in range(n):
        if i not in visited:
            component: list[dict[str, Any]] = []
            queue = [i]
            visited.add(i)
            while queue:
                curr = queue.pop(0)
                component.append(blocks[curr])
                for neighbor in sorted(adj[curr]):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            clusters.append(component)
    return clusters


def repair_daily_file(daily_path: Path, vault_root: Path) -> tuple[bool, Path]:
    """Deduplicate identical and near-duplicate session blocks in a daily log file, creating a backup first.

    Returns (was_modified, backup_path).
    """
    daily_path = Path(daily_path).resolve()
    vault_root = Path(vault_root).resolve()

    if not daily_path.is_file():
        raise FileNotFoundError(f"Daily file not found: {daily_path}")

    content = daily_path.read_text(encoding="utf-8")

    matches = list(OTURUM_HEADER.finditer(content))
    if len(matches) <= 1:
        backup_dir = vault_root / "daily-backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = (
            backup_dir
            / f"{daily_path.stem}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
        )
        shutil.copy2(daily_path, backup_path)
        return False, backup_path

    preamble = content[: matches[0].start()]

    parsed_blocks: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        header = match.group(0).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        baglam_match = re.search(r"## Bağlam\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
        baglam = baglam_match.group(1).strip() if baglam_match else ""

        normalized = re.sub(r"\s+", " ", body).strip().casefold()
        fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        parsed_blocks.append(
            {
                "index": i,
                "header": header,
                "body": body,
                "baglam": baglam,
                "minutes": _extract_minutes(header),
                "words": _extract_tokens(body),
                "fingerprint": fingerprint,
            }
        )

    clusters = _cluster_blocks(parsed_blocks)
    has_duplicates = any(len(c) > 1 for c in clusters)

    timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = vault_root / "daily-backup" / timestamp_str
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / daily_path.name
    shutil.copy2(daily_path, backup_path)

    if not has_duplicates:
        return False, backup_path

    cleaned_blocks: list[tuple[str, str]] = []
    for cluster in clusters:
        cluster.sort(key=lambda x: x["index"])
        earliest_header = cluster[0]["header"]
        best_block = max(cluster, key=lambda x: len(x["body"]))
        cleaned_blocks.append((earliest_header, best_block["body"]))

    output_parts = [preamble.rstrip()]
    output_parts.append("")
    for header, body in cleaned_blocks:
        output_parts.append(f"\n{header}\n\n{body}\n")

    cleaned_text = "\n".join(output_parts).strip() + "\n"

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{daily_path.name}.", dir=daily_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(cleaned_text)
        os.replace(temporary, daily_path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

    return True, backup_path


def repair_all_daily_files(vault_root: Path) -> list[tuple[Path, bool, Path]]:
    daily_dir = vault_root / "daily"
    results = []
    if not daily_dir.is_dir():
        return results

    for candidate in sorted(daily_dir.glob("*.md")):
        if candidate.name.startswith("."):
            continue
        try:
            modified, backup = repair_daily_file(candidate, vault_root)
            results.append((candidate, modified, backup))
        except Exception as exc:
            print(f"Hata onarılırken {candidate.name}: {exc}", file=sys.stderr)
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault-root", type=Path, default=Path.cwd(), help="Vault kök dizini"
    )
    parser.add_argument("--date", type=str, help="Onarılacak tek tarih (YYYY-MM-DD)")
    args = parser.parse_args(argv)

    vault = args.vault_root.resolve()
    if args.date:
        target = vault / "daily" / f"{args.date}.md"
        if not target.exists():
            print(f"Hata: {target} bulunamadı", file=sys.stderr)
            return 1
        modified, backup = repair_daily_file(target, vault)
        status = "temizlendi" if modified else "değişiklik gerekmedi"
        print(f"{target.name}: {status} (Yedek: {backup})")
        return 0

    results = repair_all_daily_files(vault)
    for target, modified, backup in results:
        status = "temizlendi" if modified else "değişiklik gerekmedi"
        print(f"{target.name}: {status} (Yedek: {backup})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
