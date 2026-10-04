"""Deprecated preference adapter; configuration stays in DataRoot."""
import sys

def main(argv=None):
    from respectedbrain.cli import main as dispatch
    args = list(sys.argv[1:] if argv is None else argv)
    if args and not args[0].startswith("-"):
        args = ["--summary-provider", *args]
    return dispatch(["configure", *args])

if __name__ == "__main__":
    raise SystemExit(main())
