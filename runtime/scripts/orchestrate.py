#!/usr/bin/env python3
"""CLI Entrypoint for Respected Brain Any-to-Any Orchestrator.

Usage:
  python scripts/orchestrate.py --task "Add SQLite FTS index" --master codex --worker antigravity
  python scripts/orchestrate.py --task "Fix edge case in parser" --master claude --worker gemini --test "pytest"
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BEYIN_DIR = REPO_ROOT / "template" / ".beyin"

if str(BEYIN_DIR) not in sys.path:
    sys.path.insert(0, str(BEYIN_DIR))

try:
    from orchestrator.runner import main
except ImportError:
    # If run in vault environment where .beyin is at vault root:
    vault_beyin = REPO_ROOT / ".beyin"
    if str(vault_beyin) not in sys.path:
        sys.path.insert(0, str(vault_beyin))
    from orchestrator.runner import main


if __name__ == "__main__":
    sys.exit(main())
