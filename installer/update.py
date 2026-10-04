"""Deprecated source adapter; the installed package owns all behavior."""
import sys
def main(argv=None):
    from respectedbrain.cli import main as dispatch
    return dispatch(["update", *(sys.argv[1:] if argv is None else argv)])

if __name__ == "__main__":
    raise SystemExit(main())
