#!/usr/bin/env python3
"""Persist the preferred background summary provider for one brain vault."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


PROVIDERS = ("auto", "claude", "codex", "antigravity", "cursor")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=PROVIDERS)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="vault kökü")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    path = root / ".beyin/config.json"
    document = {}
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            parser.error(".beyin/config.json bir JSON nesnesi değil")
        document.update(value)
    document["summary_provider"] = args.provider
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"özetleyici tercihi: {args.provider} ({path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
