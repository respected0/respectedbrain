"""Deprecated import adapter; package implementation is authoritative."""
import importlib

_implementation = importlib.import_module("respectedbrain.memory.lifecycle")
__getattr__ = _implementation.__getattribute__
