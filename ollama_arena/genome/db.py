"""Genome knowledge base backed by SQLite (separate from arena.db)."""
from __future__ import annotations
import json, sqlite3, time
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS canonical_models (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    family      TEXT,
    org         TEXT,
    license     TEXT,
    source_url  TEXT,
    architecture TEXT DEFAULT '{}',
    lineage      TEXT DEFAULT '{}',
    updated_at  REAL
);
CREATE TABLE IF NOT EXISTS local_models (
    name        TEXT PRIMARY KEY,
    genome_id   TEXT,
    confidence  TEXT DEFAULT 'Unknown',
    quant       TEXT,
    size_gb     REAL,
    modelfile   TEXT,
    scanned_at  REAL
);
CREATE TABLE IF NOT EXISTS genome_lineage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id        TEXT,
    parent_id       TEXT,
    relation        TEXT,
    confidence      REAL,
    evidence_source TEXT,
    ts              REAL
);
CREATE INDEX IF NOT EXISTS idx_lin_child ON genome_lineage(child_id);
CREATE INDEX IF NOT EXISTS idx_lin_parent ON genome_lineage(parent_id);
"""


class GenomeStore:
    def __init__(self, db_path: str = "genome.db"):
        self.db = db_path
        # :memory: creates a new DB per connect() — keep a single shared connection
        self._shared: sqlite3.Connection | None = None
        if db_path == ":memory:":
            self._shared = sqlite3.connect(":memory:", check_same_thread=False)
        with self._conn() as cx:
            cx.executescript(_SCHEMA)

    def _conn(self):
        if self._shared is not None:
            return self._shared
        return sqlite3.connect(self.db, timeout=10.0)

    def upsert_canonical(self, data: dict) -> None:
        with self._conn() as cx:
            cx.execute("""
                INSERT INTO canonical_models
                    (id, name, family, org, license, source_url,
                     architecture, lineage, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, family=excluded.family,
                    org=excluded.org, architecture=excluded.architecture,
                    lineage=excluded.lineage, updated_at=excluded.updated_at
            """, (data["id"], data.get("name", ""), data.get("family", ""),
                  data.get("org", ""), data.get("license", ""),
                  data.get("source_url", ""),
                  json.dumps(data.get("architecture", {})),
                  json.dumps(data.get("lineage", {})),
                  time.time()))

    def get_canonical(self, model_id: str) -> dict | None:
        with self._conn() as cx:
            row = cx.execute(
                "SELECT id,name,family,org,license,source_url,architecture,lineage "
                "FROM canonical_models WHERE id=?", (model_id,)
            ).fetchone()
        if not row:
            return None
        keys = ["id", "name", "family", "org", "license", "source_url", "architecture", "lineage"]
        d = dict(zip(keys, row))
        d["architecture"] = json.loads(d["architecture"])
        d["lineage"] = json.loads(d["lineage"])
        return d

    def all_canonical(self) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute(
                "SELECT id,name,family,org,architecture,lineage FROM canonical_models"
            ).fetchall()
        result = []
        for r in rows:
            d = dict(zip(["id", "name", "family", "org", "architecture", "lineage"], r))
            d["architecture"] = json.loads(d["architecture"])
            d["lineage"] = json.loads(d["lineage"])
            result.append(d)
        return result

    def upsert_local(self, name: str, genome_id: str | None,
                     confidence: str, quant: str, size_gb: float,
                     modelfile: str) -> None:
        with self._conn() as cx:
            cx.execute("""
                INSERT INTO local_models
                    (name, genome_id, confidence, quant, size_gb, modelfile, scanned_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                    genome_id=excluded.genome_id,
                    confidence=excluded.confidence,
                    quant=excluded.quant,
                    size_gb=excluded.size_gb,
                    modelfile=excluded.modelfile,
                    scanned_at=excluded.scanned_at
            """, (name, genome_id, confidence, quant, size_gb, modelfile, time.time()))

    def list_local(self) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute(
                "SELECT name,genome_id,confidence,quant,size_gb,scanned_at "
                "FROM local_models ORDER BY name"
            ).fetchall()
        keys = ["name", "genome_id", "confidence", "quant", "size_gb", "scanned_at"]
        return [dict(zip(keys, r)) for r in rows]

    def add_lineage(self, child_id: str, parent_id: str, relation: str,
                    confidence: float, evidence_source: str) -> None:
        with self._conn() as cx:
            cx.execute("""
                INSERT INTO genome_lineage
                    (child_id,parent_id,relation,confidence,evidence_source,ts)
                VALUES (?,?,?,?,?,?)
            """, (child_id, parent_id, relation, confidence, evidence_source, time.time()))

    def add_lineage_if_absent(self, child_id: str, parent_id: str, relation: str,
                              confidence: float, evidence_source: str) -> None:
        with self._conn() as cx:
            existing = cx.execute(
                "SELECT 1 FROM genome_lineage WHERE child_id=? AND parent_id=? AND relation=?",
                (child_id, parent_id, relation),
            ).fetchone()
            if existing:
                return
            cx.execute("""
                INSERT INTO genome_lineage
                    (child_id,parent_id,relation,confidence,evidence_source,ts)
                VALUES (?,?,?,?,?,?)
            """, (child_id, parent_id, relation, confidence, evidence_source, time.time()))

    def get_lineage(self, model_id: str) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute(
                "SELECT child_id,parent_id,relation,confidence,evidence_source "
                "FROM genome_lineage WHERE child_id=? OR parent_id=? ORDER BY ts",
                (model_id, model_id)
            ).fetchall()
        keys = ["child_id", "parent_id", "relation", "confidence", "evidence_source"]
        return [dict(zip(keys, r)) for r in rows]
