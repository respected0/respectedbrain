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
from typing import List, Optional
from ..core.context import AppContext

MAX_NOTES = 3
MAX_CHARS = 900
MIN_QUERY_CHARS = 12

CONVERSATIONAL_WORDS = {
    "ok", "tamam", "evet", "hayır", "olur", "peki", "merhaba", "selam",
    "günaydın", "iyi akşamlar", "teşekkürler", "sağol", "devam", "devam et", "et",
    "anladım", "başla", "hazırım", "yes", "no", "thanks", "hello", "hi", "companion", "asistan"
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


def _get_search_engine(ctx: AppContext):
    from ..search.engine import SearchEngine
    return SearchEngine(ctx)


def get_bounded_recall(
    query: str,
    ctx: AppContext,
    max_notes: int = MAX_NOTES,
    max_chars: int = MAX_CHARS,
) -> str:
    """Prompt için en fazla max_chars uzunluğunda hafıza fısıltısı üretir."""
    try:
        if should_abstain(query):
            return ""

        engine = _get_search_engine(ctx)
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
