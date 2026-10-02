"""Tests package initialization.
Ensures runtime/scripts is available on sys.path and sys.modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNTIME_SCRIPTS = ROOT / "runtime" / "scripts"
if RUNTIME_SCRIPTS.is_dir():
    if str(RUNTIME_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(RUNTIME_SCRIPTS))
    if "scripts" not in sys.modules:
        try:
            import runtime.scripts
            sys.modules["scripts"] = runtime.scripts
        except Exception:
            pass
