"""Deprecated command adapter; use respectedbrain hook."""
import sys
from respectedbrain.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["hook", "--provider", "codex", "--event", "notify", *sys.argv[1:]]))
