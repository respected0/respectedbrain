"""Temporary compatibility entry; product behavior lives in respectedbrain.maintenance.ingestion.url_safety."""
from importlib import import_module
import sys

_service = import_module("respectedbrain.maintenance.ingestion.url_safety")
globals().update({name: getattr(_service, name) for name in dir(_service) if not name.startswith("__")})
if __name__ != "__main__":
    sys.modules[__name__] = _service
else:
    raise SystemExit(_service.main())
