"""Explicit context shared by product services."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from .paths import AppPaths
from .resources import ResourceCatalog


@dataclass(frozen=True)
class AppContext:
    paths: AppPaths
    config: dict[str, Any]
    resources: ResourceCatalog


@dataclass(frozen=True)
class ModelResult:
    text: str | None
    provider: str | None
    error: str | None


class ModelService(Protocol):
    def run(self, prompt: str, *, cwd: Path, mode: Literal["text", "workspace"], timeout: float) -> ModelResult:
        """Run a model in an explicitly supplied workspace."""
        ...
