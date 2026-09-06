#!/usr/bin/env python3
"""Bounded Vault Recall - Prompt öncesi hafif, sessiz hafıza fısıltısı.

Kullanıcı her mesaj gönderdiğinde, arka planda kasadan en alakalı 2-3 nottan
en fazla 900 karakterlik (~250 token) minik bir bağlam özeti çıkarır.

Tasarım İlkeleri:
  1. BOUNDED:   Azami 3 not ve azami 900 karakter. Bir ipucudur, döküm değildir.
  2. ABSTAINS:  Düşük eşleşme skorunda, selamlama veya kısa yanıtlarda tamamen SUSAR ("").
  3. FAIL-CLOSED: Herhangi bir hata durumunda sessizce "" döner; ana süreci asla engellemez.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
from typing import Any, List, Optional, Set

MAX_NOTES = 3
MAX_CHARS = 900
MIN_QUERY_CHARS = 12

CONVERSATIONAL_WORDS = {
    "ok", "tamam", "evet", "hayır", "olur", "peki", "merhaba", "selam",
    "günaydın", "iyi akşamlar", "teşekkürler", "sağol", "devam", "devam et", "et",
    "anladım", "başla", "hazırım", "yes", "no", "thanks", "hello", "hi", "jarvis"
}

_WORD_RE = re.compile(r"[\w\u00C0-\u017F]+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text) if len(w) > 1]


def should_abstain(query: str) -> bool:
    """Sorgunun geri çağırma gerektirip gerektirmediğini denetler."""
    clean = query.strip()
    if len(clean) < MIN_QUERY_CHARS:
        return True
    if clean.startswith("/"):
        return True

    tokens = _tokenize(clean)
    if not tokens:
        return True

    # Tamamı selamlama / onay kelimesiyse sus
    if all(t in CONVERSATIONAL_WORDS for t in tokens):
        return True

    return False


def _get_search_engine(vault_root: Path):
    """Arama motorunu yükler."""
    scripts_dir = vault_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    template_scripts = vault_root.parent / "template" / "scripts"
    if str(template_scripts) not in sys.path:
        sys.path.insert(0, str(template_scripts))

    try:
        from arama import SearchEngine
        return SearchEngine(vault_root)
    except Exception:
        return None


def get_bounded_recall(
    query: str,
    vault_root: Optional[Path] = None,
    max_notes: int = MAX_NOTES,
    max_chars: int = MAX_CHARS,
) -> str:
    """Prompt için en fazla max_chars uzunluğunda hafıza fısıltısı üretir."""
    try:
        if should_abstain(query):
            return ""

        if vault_root is None:
            # Ortam değişkeni veya geçerli dizin
            env_v = os.environ.get("RESPECTED_VAULT") or os.environ.get("VAULT_ROOT")
            if env_v:
                vault_root = Path(env_v).resolve()
            else:
                cur = Path.cwd().resolve()
                vault_root = cur

        engine = _get_search_engine(vault_root)
        if engine is None:
            return ""

        results = engine.search(query, limit=max_notes)
        if not results:
            return ""

        # Sonuçları formatla
        lines: List[str] = ["[Hafıza Fısıltısı]"]
        total_len = len(lines[0])

        for r in results[:max_notes]:
            rel_path = r.get("path", "")
            snippet = r.get("snippet", "").strip().replace("\n", " ")
            if not snippet:
                continue

            entry = f"- [[{rel_path}]]: {snippet}"
            if total_len + len(entry) + 1 > max_chars:
                # Kırparak sığdır
                avail = max_chars - (total_len + len(f"- [[{rel_path}]]: ") + 4)
                if avail > 20:
                    entry = f"- [[{rel_path}]]: {snippet[:avail]}..."
                    lines.append(entry)
                break
            lines.append(entry)
            total_len += len(entry) + 1

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)
    except Exception:
        # Fail-closed
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded Vault Recall CLI")
    parser.add_argument("query", help="Arama sorgusu / prompt")
    parser.add_argument("--vault", help="Vault kök dizini", default=None)
    parser.add_argument("--max-chars", type=int, default=MAX_CHARS, help="Azami karakter sayısı")
    args = parser.parse_args()

    v_root = Path(args.vault).resolve() if args.vault else None
    result = get_bounded_recall(args.query, vault_root=v_root, max_chars=args.max_chars)
    if result:
        print(result)


if __name__ == "__main__":
    main()
