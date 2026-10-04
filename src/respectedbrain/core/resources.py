"""Read immutable resources independently of the source checkout."""
from __future__ import annotations

from contextlib import contextmanager
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Iterator


class ResourceCatalog:
    def _locate(self, relative: str) -> Traversable:
        if not isinstance(relative, str) or "\\" in relative or ":" in relative or "\0" in relative:
            raise ValueError("Resource names must be relative POSIX paths")
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Resource name escapes the package")
        return files("respectedbrain.resources").joinpath(*path.parts)

    def read_text(self, relative: str) -> str:
        return self._locate(relative).read_text(encoding="utf-8")

    def iter_files(self, relative: str) -> tuple[str, ...]:
        root = self._locate(relative)
        if not root.is_dir():
            raise NotADirectoryError(relative)

        def walk(node: Traversable, prefix: str = "") -> Iterator[str]:
            for child in sorted(node.iterdir(), key=lambda item: item.name):
                name = prefix + child.name
                if child.is_dir():
                    yield from walk(child, name + "/")
                else:
                    yield name

        return tuple(walk(root))

    @contextmanager
    def materialize(self, relative: str) -> Iterator[Path]:
        """Yield an isolated copy, including directory resources on Python 3.10."""
        source = self._locate(relative)
        if not source.is_file() and not source.is_dir():
            raise FileNotFoundError(relative)
        with TemporaryDirectory(prefix="respected-resource-") as temporary:
            # Canonicalize only the directory freshly allocated by this owner.
            destination = Path(temporary).resolve() / source.name

            def copy(node: Traversable, target: Path) -> None:
                if node.is_dir():
                    target.mkdir()
                    for child in node.iterdir():
                        copy(child, target / child.name)
                else:
                    target.write_bytes(node.read_bytes())

            copy(source, destination)
            yield destination
