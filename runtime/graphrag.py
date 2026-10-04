"""Deprecated import adapter; package implementation is authoritative."""
import importlib

_implementation = importlib.import_module("respectedbrain.memory.graph.graphrag")
__getattr__ = _implementation.__getattribute__
