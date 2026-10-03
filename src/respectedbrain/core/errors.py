"""Failures shared across the application without feature dependencies."""

class FoundationError(Exception):
    """An application operation could not meet its contract."""


class SelectionError(FoundationError, ValueError):
    """An explicit root or vault selection is invalid."""


class IdentityConflict(SelectionError):
    """Two live vault locations claim the same identity."""


class StateConflict(FoundationError):
    """State sources contain incompatible values."""


class OwnershipConflict(FoundationError):
    """A destination no longer matches the recorded ownership."""


class BusyError(FoundationError):
    """A live writer prevents exclusive access."""
