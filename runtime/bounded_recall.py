"""Deprecated import adapter; package implementation is authoritative."""
import importlib

_implementation = importlib.import_module("respectedbrain.memory.bounded_recall")
__getattr__ = _implementation.__getattribute__
