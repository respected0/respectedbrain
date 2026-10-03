"""Explicit context shared by product services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .paths import AppPaths
from .resources import ResourceCatalog


@dataclass(frozen=True)
class AppContext:
    paths: AppPaths
    config: dict[str, Any]
    resources: ResourceCatalog
