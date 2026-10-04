"""Deprecated command adapter; use respectedbrain compile."""
import sys
from respectedbrain.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["compile", *sys.argv[1:]]))
