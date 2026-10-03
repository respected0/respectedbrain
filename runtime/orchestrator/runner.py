"""Temporary compatibility entry; product behavior lives in respectedbrain.orchestration.runner."""
from importlib import import_module
import sys

_service = import_module("respectedbrain.orchestration.runner")
globals().update({name: getattr(_service, name) for name in dir(_service) if not name.startswith("__")})
if __name__ != "__main__":
    sys.modules[__name__] = _service
else:
    from pathlib import Path
    from respectedbrain.cli import main
    args = sys.argv[1:]
    project = Path.cwd()
    for index, item in enumerate(args):
        if item in ("--repo", "-r") and index + 1 < len(args):
            project = Path(args[index + 1]).resolve()
        elif item.startswith("--repo="):
            project = Path(item.split("=", 1)[1]).resolve()
    forward = ["antigravity", *args] if "runner" == "antigravity_orchestrator" else ["--", *args]
    raise SystemExit(main(["orchestrate", "--project-root", str(project), *forward]))
