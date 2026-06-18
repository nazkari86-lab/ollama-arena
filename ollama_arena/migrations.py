"""Backward-compatible re-export of migration runner."""
from .storage.sqlite.migrations import (  # noqa: F401
    MIGRATIONS,
    _COLUMN_ADDS,
    apply_migrations,
    current_version,
)

__all__ = ["MIGRATIONS", "_COLUMN_ADDS", "apply_migrations", "current_version"]
