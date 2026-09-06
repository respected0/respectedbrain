#!/usr/bin/env python3
"""Tiling Check - Semantik Tekrar ve Benzer Not Dedektörü.

Respected Brain içindeki notları tarayarak birbirine aşırı benzeyen,
aynı konuyu mükerrer anlatan veya birleştirilmesi (merge) gereken sayfaları
Jaccard ve token overlap benzerliği ile tespit eder.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

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
    "📋 Templates",
    "📦 900-Archive",
}

STOP_WORDS = {
    "ve", "veya", "ile", "bir", "bu", "şu", "o", "de", "da", "ki", "için", "olan",
    "olarak", "gibi", "kadar", "daha", "en", "çok", "her", "şey", "the", "and", "or",
    "is", "in", "at", "of", "to", "a", "an", "it", "that", "this", "for", "with", "on"
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


def tokenize(text: str) -> set[str]:
    """Metni küçük harfli kelime token setine dönüştürür (camelCase ve snake_case destekler)."""
    split_camel = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    words = re.findall(r"\b[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{2,}\b", split_camel.lower())
    return {w for w in words if w not in STOP_WORDS and not w.isdigit()}


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """İki token kümesi arasındaki Jaccard benzerlik katsayısı."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def check_tiling(vault_root: Path, threshold: float = 0.55) -> dict[str, Any]:
    """Kasadaki tüm notları tarayarak benzerlik eşiğini aşan çiftleri bulur."""
    notes: list[tuple[str, str, set[str]]] = []  # (rel_path, stem, tokens)

    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for file in files:
            if file.endswith(".md"):
                full_p = Path(root) / file
                rel_p = full_p.relative_to(vault_root).as_posix()
                if any(rel_p.startswith(ex) for ex in ["📋 Templates", "📦 900-Archive", "📥 000-Inbox/Dump"]):
                    continue
                try:
                    content = full_p.read_text(encoding="utf-8", errors="replace")
                    tokens = tokenize(content)
                    if len(tokens) >= 15:  # Çok kısa notları hariç tut
                        notes.append((rel_p, full_p.stem, tokens))
                except Exception:
                    pass

    similar_pairs: list[dict[str, Any]] = []

    # İkili karşılaştırma
    n = len(notes)
    for i in range(n):
        path_a, stem_a, tokens_a = notes[i]
        for j in range(i + 1, n):
            path_b, stem_b, tokens_b = notes[j]

            # Başlık benzerliği
            title_tokens_a = tokenize(stem_a)
            title_tokens_b = tokenize(stem_b)
            title_sim = jaccard_similarity(title_tokens_a, title_tokens_b)

            # İçerik benzerliği
            content_sim = jaccard_similarity(tokens_a, tokens_b)

            # Bileşik skor (başlık benzerliği ağırlıklı)
            composite_score = (content_sim * 0.7) + (title_sim * 0.3)

            if composite_score >= threshold or content_sim >= threshold or (title_sim >= 0.7 and content_sim >= 0.35):
                similar_pairs.append({
                    "note_a": path_a,
                    "note_b": path_b,
                    "similarity_pct": round(composite_score * 100, 1),
                    "content_similarity_pct": round(content_sim * 100, 1),
                    "title_similarity_pct": round(title_sim * 100, 1),
                    "common_terms": sorted(list(tokens_a & tokens_b))[:8],
                    "recommendation": "Birleştir (Merge) veya karşılıklı link ekle"
                })

    similar_pairs.sort(key=lambda x: x["similarity_pct"], reverse=True)

    return {
        "vault_root": str(vault_root),
        "analyzed_notes_count": len(notes),
        "threshold_pct": round(threshold * 100, 1),
        "duplicate_pairs_count": len(similar_pairs),
        "pairs": similar_pairs[:50],  # Bounded
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Tiling Check - Kasa İçi Benzer Not Taraması")
    parser.add_argument("--vault", help="Denetlenecek vault kök dizini")
    parser.add_argument("--threshold", type=float, default=0.55, help="Benzerlik eşik değeri (0.0 - 1.0, varsayılan: 0.55)")
    parser.add_argument("--json", action="store_true", help="JSON formatında çıktı")
    args = parser.parse_args()

    v_root = resolve_vault_root(Path(args.vault) if args.vault else None)
    results = check_tiling(v_root, threshold=args.threshold)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"=== Tiling Check: {results['vault_root']} ===")
        print(f"Taranan Not Sayısı: {results['analyzed_notes_count']}")
        print(f"Eşik Değeri: %{results['threshold_pct']}")
        print(f"Benzer/Mükerrer Çift Sayısı: {results['duplicate_pairs_count']}")

        if results["pairs"]:
            print("\nÖne Çıkan Benzer Not Çiftleri:")
            for pair in results["pairs"][:15]:
                print(f"  [%{pair['similarity_pct']}] {pair['note_a']}  <--->  {pair['note_b']}")
                print(f"    Ortak Kavramlar: {', '.join(pair['common_terms'])}")
                print(f"    Öneri: {pair['recommendation']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
