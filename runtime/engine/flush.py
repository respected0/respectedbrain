"""Deprecated command adapter; use respectedbrain flush."""
import sys
from respectedbrain.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["flush", *sys.argv[1:]]))
