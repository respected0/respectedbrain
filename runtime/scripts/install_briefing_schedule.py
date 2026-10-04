"""Deprecated source adapter; the installed package owns all behavior."""
import sys
import importlib
_implementation = importlib.import_module("respectedbrain.integrations.scheduling.service")
__getattr__ = _implementation.__getattribute__

def main(argv=None):
    from respectedbrain.cli import main as dispatch
    return dispatch(["repair", *(sys.argv[1:] if argv is None else argv)])

if __name__ == "__main__":
    raise SystemExit(main())
