"""Temporary compatibility entry; product behavior lives in respectedbrain.maintenance.ingestion.mine_agent_history."""
from importlib import import_module
import sys

_service = import_module("respectedbrain.maintenance.ingestion.mine_agent_history")
globals().update({name: getattr(_service, name) for name in dir(_service) if not name.startswith("__")})
if __name__ != "__main__":
    sys.modules[__name__] = _service
else:
    from respectedbrain.cli import main
    args = sys.argv[1:]
    selector = []
    for index, item in enumerate(args):
        if item in ("--vault", "--vault-root") and index + 1 < len(args):
            selector = ["--vault", args[index + 1]]
        elif item.startswith(("--vault=", "--vault-root=")):
            selector = ["--vault", item.split("=", 1)[1]]
    if "mine_agent_history" in ("backup_restic", "publish_git_snapshot") and args and not args[0].startswith("-"):
        selector = ["--vault", args[0]]
    raise SystemExit(main(["maintenance", *selector, "mine_agent_history", *args]))
