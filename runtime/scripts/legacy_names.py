"""Deprecated pure constants adapter; core is the authoritative source."""
import importlib
_implementation = importlib.import_module("respectedbrain.core.legacy_names")
__getattr__ = _implementation.__getattribute__
