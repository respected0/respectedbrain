"""Pure application, data and UUID-bound vault path contracts."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .errors import SelectionError


def _absolute(value: Path | str) -> Path:
    if not value or not Path(value).is_absolute():
        raise SelectionError(f"Root must be an absolute path: {value!s}")
    return Path(value).resolve()


def _disjoint(*roots: Path) -> None:
    for index, left in enumerate(roots):
        for right in roots[index + 1:]:
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise SelectionError(f"Application, data and vault roots must be separate: {left}, {right}")


@dataclass(frozen=True)
class Roots:
    app_root: Path
    data_root: Path
    default_vault: Path

    def __post_init__(self) -> None:
        for name in ("app_root", "data_root", "default_vault"):
            object.__setattr__(self, name, _absolute(getattr(self, name)))
        _disjoint(self.app_root, self.data_root, self.default_vault)


def resolve_roots(*, platform: str, home: Path, env: Mapping[str, str], known_folder: Callable[[str], Path]) -> Roots:
    home = _absolute(home)
    if platform in ("win32", "windows"):
        local = _absolute(known_folder("LocalAppData"))
        app, data = local / "Programs/RespectedBrain", local / "RespectedBrain"
        documents = _absolute(known_folder("Documents"))
    elif platform == "darwin":
        app, data = home / "Applications/RespectedBrain.app", home / "Library/Application Support/RespectedBrain"
        documents = home / "Documents" if (home / "Documents").is_dir() else home
    elif platform.startswith("linux"):
        app = home / ".local/lib/respectedbrain"
        base = _absolute(env["XDG_DATA_HOME"]) if env.get("XDG_DATA_HOME") else home / ".local/share"
        data = base / "respectedbrain"
        documents = home / "Documents" if (home / "Documents").is_dir() else home
    else:
        raise SelectionError(f"Unsupported platform: {platform}")
    if "RESPECTED_APP_DIR" in env:
        app = _absolute(env["RESPECTED_APP_DIR"])
    if "RESPECTED_DATA_DIR" in env:
        data = _absolute(env["RESPECTED_DATA_DIR"])
    return Roots(app, data, documents / "RespectedOS")


@dataclass(frozen=True)
class AppPaths:
    app_root: Path
    data_root: Path
    vault_root: Path
    vault_id: str

    def __post_init__(self) -> None:
        for name in ("app_root", "data_root", "vault_root"):
            object.__setattr__(self, name, _absolute(getattr(self, name)))
        _disjoint(self.app_root, self.data_root, self.vault_root)
        try:
            identity = str(UUID(self.vault_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise SelectionError("Vault identity must be a UUID") from exc
        object.__setattr__(self, "vault_id", identity)

    @property
    def state_dir(self) -> Path:
        return self.data_root / "vaults" / self.vault_id / "state"

    @property
    def cache_dir(self) -> Path:
        return self.data_root / "vaults" / self.vault_id / "cache"

    @property
    def overrides_dir(self) -> Path:
        return self.data_root / "vaults" / self.vault_id / "overrides"

    @property
    def log_dir(self) -> Path:
        return self.data_root / "logs"

    @property
    def backup_dir(self) -> Path:
        return self.data_root / "backups"
