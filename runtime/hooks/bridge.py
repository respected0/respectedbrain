"""Deprecated command adapter; use respectedbrain hook."""
import sys
from respectedbrain.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["hook", *sys.argv[1:]]))
