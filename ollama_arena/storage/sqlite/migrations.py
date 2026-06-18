"""Tiny forward-only SQLite migration runner.

We deliberately don't pull in Alembic — the arena ships a single SQLite
file, never has parallel writers across hosts, and the schema evolves
slowly. A 60-line versioned-DDL list keeps the dependency tree small.

Usage
-----
    from .migrations import apply_migrations
    apply_migrations(db_path)             # idempotent; safe to call every boot

How it works
------------
* PRAGMA user_version stores the highest migration index already applied.
* `MIGRATIONS` is an ordered list of (description, sql) tuples.
* Index 0 is the initial schema (idempotent CREATE IF NOT EXISTS).
* Each subsequent index runs once, in a transaction. On failure the entire
  transaction rolls back and user_version stays put.

Adding a new migration
----------------------
1. Append a tuple to `MIGRATIONS` — do NOT reorder existing entries.
2. Write SQL that's idempotent where possible (CREATE IF NOT EXISTS,
   ALTER TABLE … ADD COLUMN behind a try/except).
3. Test on a fresh DB AND on an existing DB.
"""
from __future__ import annotations

import logging
import sqlite3
log = logging.getLogger("arena.storage.migrations")


# ── Migration table ─────────────────────────────────────────────────────────
# Each entry is (description, sql). The first entry doubles as the bootstrap
# CREATE for fresh installs; later entries are diffs.
MIGRATIONS: list[tuple[str, str]] = [
    # 1 — base schema (idempotent — covers both fresh + already-migrated DBs)
    ("base schema", """
        CREATE TABLE IF NOT EXISTS ratings (
            model      TEXT PRIMARY KEY,
            elo        REAL DEFAULT 1200,
            wins       INTEGER DEFAULT 0,
            losses     INTEGER DEFAULT 0,
            draws      INTEGER DEFAULT 0,
            matches    INTEGER DEFAULT 0,
            updated_at REAL
        );
        CREATE TABLE IF NOT EXISTS match_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_a       TEXT,
            model_b       TEXT,
            category      TEXT,
            score_a       REAL,
            score_b       REAL,
            elo_a_before  REAL,
            elo_b_before  REAL,
            elo_a_after   REAL,
            elo_b_after   REAL,
            ts            REAL
        );
        CREATE TABLE IF NOT EXISTS task_detail (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id     INTEGER,
            task_id      TEXT,
            category     TEXT,
            difficulty   TEXT,
            language     TEXT,
            instruction  TEXT,
            response_a   TEXT,
            response_b   TEXT,
            expected     TEXT,
            score_a      REAL,
            score_b      REAL,
            outcome      TEXT,
            tps_a        REAL,
            tps_b        REAL,
            latency_a    REAL,
            latency_b    REAL,
            ts           REAL
        );
        CREATE TABLE IF NOT EXISTS benchmark_runs (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            model              TEXT,
            score              REAL,
            scores_by_category TEXT,
            n_tasks            INTEGER,
            ts                 REAL
        );
        CREATE INDEX IF NOT EXISTS idx_task_detail_task   ON task_detail(task_id);
        CREATE INDEX IF NOT EXISTS idx_task_detail_match  ON task_detail(match_id);
    """),

    # 2 — performance: log timestamps + category lookups
    ("idx_match_log_ts + idx_task_detail_category", """
        CREATE INDEX IF NOT EXISTS idx_match_log_ts        ON match_log(ts);
        CREATE INDEX IF NOT EXISTS idx_match_log_models    ON match_log(model_a, model_b);
        CREATE INDEX IF NOT EXISTS idx_task_detail_cat     ON task_detail(category);
        CREATE INDEX IF NOT EXISTS idx_ratings_elo         ON ratings(elo DESC);
    """),

    # 3 — hallucination tagging (5.2)  ── add nullable columns; default None.
    ("task_detail.hallucination_a/b + match_log.kind", """
        -- ALTER TABLE ADD COLUMN — wrapped in TRY so re-run is safe
        -- (SQLite has no IF NOT EXISTS on columns until 3.35; we sniff via PRAGMA)
        -- The Python runner catches OperationalError when the column already exists.
    """),

    # 4 — Battle Royale storage: an N-way match needs its own table because
    #     match_log is locked to pairwise scoring.
    ("royale_log + royale_entries", """
        CREATE TABLE IF NOT EXISTS royale_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            category  TEXT,
            n_models  INTEGER,
            n_tasks   INTEGER,
            ts        REAL
        );
        CREATE TABLE IF NOT EXISTS royale_entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            royale_id  INTEGER,
            task_id    TEXT,
            model      TEXT,
            rank       INTEGER,
            score      REAL,
            response   TEXT,
            tps        REAL,
            latency_s  REAL,
            ts         REAL
        );
        CREATE INDEX IF NOT EXISTS idx_royale_entries_royale ON royale_entries(royale_id);
        CREATE INDEX IF NOT EXISTS idx_royale_entries_model  ON royale_entries(model);
    """),

    # 5 — tool-use support (extra columns hint per-attempt tool-call data)
    ("task_detail.tool_call_a/b", """
        -- Same idea as migration 3 — columns added via Python with PRAGMA sniff.
    """),

    # 6 — royale enhancements: hallucination + instruction
    ("royale_entries.hallucination + royale_entries.instruction", """
        -- Columns added via Python with PRAGMA sniff.
    """),

    # 7 — per-category ELO ratings (separate from global ratings table)
    ("category_ratings table", """
        CREATE TABLE IF NOT EXISTS category_ratings (
            model      TEXT,
            category   TEXT,
            elo        REAL DEFAULT 1200,
            wins       INTEGER DEFAULT 0,
            losses     INTEGER DEFAULT 0,
            draws      INTEGER DEFAULT 0,
            matches    INTEGER DEFAULT 0,
            updated_at REAL,
            PRIMARY KEY (model, category)
        );
        CREATE INDEX IF NOT EXISTS idx_cat_ratings_cat ON category_ratings(category);
        CREATE INDEX IF NOT EXISTS idx_cat_ratings_model ON category_ratings(model);
    """),
]


# ── ALTERs that need column-existence checking are kept here ────────────────
# (SQLite < 3.35 has no IF NOT EXISTS on columns.)
_COLUMN_ADDS: dict[int, list[tuple[str, str, str]]] = {
    3: [
        ("task_detail", "hallucination_a", "INTEGER"),
        ("task_detail", "hallucination_b", "INTEGER"),
        ("match_log",   "kind",            "TEXT DEFAULT 'duel'"),
    ],
    5: [
        ("task_detail", "tool_call_a",  "TEXT"),
        ("task_detail", "tool_call_b",  "TEXT"),
    ],
    6: [
        ("royale_entries", "hallucination", "INTEGER"),
        ("royale_entries", "instruction",   "TEXT"),
    ],
}


# ── Public API ──────────────────────────────────────────────────────────────

def current_version(cx: sqlite3.Connection) -> int:
    return cx.execute("PRAGMA user_version").fetchone()[0]


def _columns(cx: sqlite3.Connection, table: str) -> set[str]:
    rows = cx.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _safe_add_column(cx: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = _columns(cx, table)
    if col in cols:
        return
    cx.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def apply_migrations(db_path: str) -> tuple[int, int]:
    """Run every pending migration. Returns (before, after) version pair.

    Each migration runs to completion or the runner raises and the
    unmigrated tail stays pending for the next boot. We can't wrap
    `executescript()` in our own BEGIN/COMMIT — it issues its own
    implicit COMMIT — so we rely on Python's connection commit instead.
    """
    target = len(MIGRATIONS)
    cx = sqlite3.connect(db_path, timeout=30.0)
    try:
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=NORMAL")
        cx.execute("PRAGMA foreign_keys=ON")
        before = current_version(cx)
        for idx in range(before, target):
            desc, sql = MIGRATIONS[idx]
            try:
                if sql.strip():
                    cx.executescript(sql)
                for table, col, ddl in _COLUMN_ADDS.get(idx + 1, []):
                    _safe_add_column(cx, table, col, ddl)
                cx.execute(f"PRAGMA user_version = {idx + 1}")
                cx.commit()
                log.info(f"[migrations] applied #{idx+1}: {desc}")
            except Exception as e:
                cx.rollback()
                log.error(f"[migrations] FAILED #{idx+1} ({desc}): {e}")
                raise
        after = current_version(cx)
    finally:
        cx.close()
    return before, after
