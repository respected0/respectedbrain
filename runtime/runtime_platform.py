"""Deprecated import adapter; package implementation is authoritative."""
import importlib

_implementation = importlib.import_module("respectedbrain.core.platform")
__getattr__ = _implementation.__getattribute__
