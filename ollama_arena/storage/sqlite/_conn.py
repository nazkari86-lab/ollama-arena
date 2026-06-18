"""Shared SQLite connection helpers."""
from __future__ import annotations

import sqlite3


def read_conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, timeout=30.0)


def write_conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, timeout=30.0, isolation_level="IMMEDIATE")
