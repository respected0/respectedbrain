#!/usr/bin/env python3
"""Persist the preferred background summary provider for one brain vault."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def _configure_console_output() -> None:
    """Keep Windows OEM consoles from aborting on non-ASCII output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


_configure_console_output()


PROVIDERS = ("auto", "claude", "codex", "antigravity", "cursor")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=PROVIDERS, nargs="?", default=None, help="Birincil özetleyici veya auto")
    parser.add_argument("--priority", nargs="+", help="Arka plan sağlayıcılarının öncelik sırası (örn: --priority antigravity codex claude)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="vault kökü")
    args = parser.parse_args()
    if args.provider is None and not args.priority:
        parser.error("Lütfen bir provider belirtin veya --priority ile öncelik listesi verin.")
    root = args.root.expanduser().resolve()
    path = root / ".beyin/config.json"
    document = {}
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            parser.error(".beyin/config.json bir JSON nesnesi değil")
        document.update(value)
    if args.provider is not None:
        document["summary_provider"] = args.provider
    if args.priority:
        valid_providers = ("claude", "codex", "antigravity", "cursor")
        normalized = []
        for p in args.priority:
            p_low = p.lower()
            if p_low not in valid_providers:
                parser.error(f"Geçersiz priority sağlayıcısı: {p}. Geçerliler: {', '.join(valid_providers)}")
            if p_low not in normalized:
                normalized.append(p_low)
        document["provider_priority"] = normalized
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    provider_info = f"özetleyici: {document.get('summary_provider', 'auto')}"
    if "provider_priority" in document:
        provider_info += f" | öncelik: {' -> '.join(document['provider_priority'])}"
    print(f"{provider_info} ({path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
