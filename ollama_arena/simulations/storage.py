"""sim.db -- persistence for simulation runs, events, transitions, and
checkpoints. Deliberately a separate SQLite file from arena.db (different
schema shape: worlds/events/episodes, not matches/ELO), modeled on
genome/db.py's pattern: own file, own idempotent CREATE-IF-NOT-EXISTS
schema, reusing storage.sqlite._conn's pooled/WAL connection helpers rather
than hand-rolling sqlite3.connect() calls.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid

from ..storage.sqlite._conn import read_conn, write_conn
from .core.types import Action, AgentSpec, Event, Observation, Transition

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sim_runs (
    run_id      TEXT PRIMARY KEY,
    scenario    TEXT NOT NULL,
    agents_json TEXT NOT NULL,
    config_json TEXT NOT NULL,
    seed        INTEGER,
    status      TEXT NOT NULL,
    created_at  REAL NOT NULL,
    started_at  REAL,
    completed_at REAL,
    outcome_json TEXT
);
CREATE TABLE IF NOT EXISTS sim_events (
    rowid_pk    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    tick        INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    witness_ids_json TEXT NOT NULL,
    actor_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_sim_events_run ON sim_events(run_id, tick);
CREATE TABLE IF NOT EXISTS sim_transitions (
    rowid_pk    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    tick        INTEGER NOT NULL,
    agent_id    TEXT NOT NULL,
    obs_json    TEXT NOT NULL,
    action_json TEXT NOT NULL,
    reward      REAL NOT NULL,
    terminated  INTEGER NOT NULL,
    truncated   INTEGER NOT NULL,
    info_json   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sim_transitions_run ON sim_transitions(run_id, tick);
CREATE TABLE IF NOT EXISTS sim_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    tick        INTEGER NOT NULL,
    state_json  TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sim_checkpoints_run ON sim_checkpoints(run_id, created_at);
CREATE TABLE IF NOT EXISTS sim_metrics (
    rowid_pk    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value       REAL NOT NULL,
    tick        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sim_metrics_run ON sim_metrics(run_id, metric_name);
"""


def _event_to_row(run_id: str, event: Event) -> tuple:
    return (
        run_id, event.id, event.tick, event.kind,
        json.dumps(event.payload),
        json.dumps(sorted(event.witness_ids)),
        event.actor_id,
    )


def _row_to_event(row: tuple) -> Event:
    _, event_id, tick, kind, payload_json, witness_json, actor_id = row
    return Event(
        id=event_id, tick=tick, kind=kind,
        payload=json.loads(payload_json),
        witness_ids=frozenset(json.loads(witness_json)),
        actor_id=actor_id,
    )


def _obs_to_json(obs: Observation) -> str:
    return json.dumps({
        "agent_id": obs.agent_id,
        "tick": obs.tick,
        "visible_event_ids": [e.id for e in obs.visible_events],
        "status": obs.status,
    })


def _action_to_json(action: Action) -> str:
    return json.dumps({
        "agent_id": action.agent_id,
        "kind": action.kind,
        "payload": action.payload,
        "raw_llm_output": action.raw_llm_output,
    })


class SimStore:
    """Thin SQLite-backed store for one sim.db file.

    Mirrors genome/db.py's shape: a `_conn()` helper (special-cased for
    `:memory:` so tests get one shared connection rather than a fresh empty
    DB per call), upsert/insert/list methods that hide the JSON
    serialization, no ORM.
    """

    def __init__(self, db_path: str = "sim.db"):
        self.db = db_path
        self._shared: sqlite3.Connection | None = None
        if db_path == ":memory:":
            self._shared = sqlite3.connect(":memory:", check_same_thread=False)
        with self._write() as cx:
            cx.executescript(_SCHEMA)

    def _write(self):
        if self._shared is not None:
            return self._shared
        return write_conn(self.db)

    def _read(self):
        if self._shared is not None:
            return self._shared
        return read_conn(self.db)

    # ── runs ─────────────────────────────────────────────────────────────

    def create_run(
        self, scenario: str, agents: list[AgentSpec], config: dict,
        seed: int | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex[:12]
        agents_json = json.dumps([
            {"agent_id": a.agent_id, "model": a.model, "config": a.config}
            for a in agents
        ])
        with self._write() as cx:
            cx.execute(
                "INSERT INTO sim_runs (run_id, scenario, agents_json, config_json, "
                "seed, status, created_at) VALUES (?,?,?,?,?,?,?)",
                (run_id, scenario, agents_json, json.dumps(config), seed,
                 "not_started", time.time()),
            )
        return run_id

    def update_run_status(self, run_id: str, status: str, **timestamps) -> None:
        cols = ", ".join(f"{k}=?" for k in timestamps) + ", status=?" if timestamps else "status=?"
        params = list(timestamps.values()) + [status, run_id]
        with self._write() as cx:
            cx.execute(f"UPDATE sim_runs SET {cols} WHERE run_id=?", params)

    def set_run_outcome(self, run_id: str, outcome: dict) -> None:
        with self._write() as cx:
            cx.execute(
                "UPDATE sim_runs SET outcome_json=? WHERE run_id=?",
                (json.dumps(outcome), run_id),
            )

    def get_run(self, run_id: str) -> dict | None:
        with self._read() as cx:
            row = cx.execute(
                "SELECT run_id, scenario, agents_json, config_json, seed, status, "
                "created_at, started_at, completed_at, outcome_json "
                "FROM sim_runs WHERE run_id=?", (run_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_run(row)

    def list_runs(self, scenario: str | None = None) -> list[dict]:
        sql = ("SELECT run_id, scenario, agents_json, config_json, seed, status, "
               "created_at, started_at, completed_at, outcome_json FROM sim_runs")
        params: tuple = ()
        if scenario:
            sql += " WHERE scenario=?"
            params = (scenario,)
        sql += " ORDER BY created_at DESC"
        with self._read() as cx:
            rows = cx.execute(sql, params).fetchall()
        return [self._row_to_run(r) for r in rows]

    @staticmethod
    def _row_to_run(row: tuple) -> dict:
        keys = ["run_id", "scenario", "agents_json", "config_json", "seed", "status",
                "created_at", "started_at", "completed_at", "outcome_json"]
        d = dict(zip(keys, row))
        d["agents"] = json.loads(d.pop("agents_json"))
        d["config"] = json.loads(d.pop("config_json"))
        d["outcome"] = json.loads(d.pop("outcome_json")) if d.get("outcome_json") else None
        return d

    # ── events ───────────────────────────────────────────────────────────

    def append_events(self, run_id: str, events: list[Event]) -> None:
        if not events:
            return
        with self._write() as cx:
            cx.executemany(
                "INSERT INTO sim_events (run_id, event_id, tick, kind, payload_json, "
                "witness_ids_json, actor_id) VALUES (?,?,?,?,?,?,?)",
                [_event_to_row(run_id, e) for e in events],
            )

    def get_events(self, run_id: str, witness_id: str | None = None) -> list[Event]:
        """All events for a run, optionally pre-filtered to those a given
        agent witnessed. Filtering here (not just at observe()-time) is what
        the replay/eval layers use to reconstruct "what did agent X know."
        """
        with self._read() as cx:
            rows = cx.execute(
                "SELECT run_id, event_id, tick, kind, payload_json, witness_ids_json, actor_id "
                "FROM sim_events WHERE run_id=? ORDER BY tick, rowid_pk", (run_id,),
            ).fetchall()
        events = [_row_to_event(r) for r in rows]
        if witness_id is None:
            return events
        return [e for e in events if e.visible_to(witness_id)]

    # ── transitions ──────────────────────────────────────────────────────

    def append_transitions(self, run_id: str, transitions: list[Transition]) -> None:
        if not transitions:
            return
        with self._write() as cx:
            cx.executemany(
                "INSERT INTO sim_transitions (run_id, tick, agent_id, obs_json, "
                "action_json, reward, terminated, truncated, info_json) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (run_id, t.tick, t.agent_id, _obs_to_json(t.obs),
                     _action_to_json(t.action), t.reward, int(t.terminated),
                     int(t.truncated), json.dumps(t.info))
                    for t in transitions
                ],
            )

    def get_transitions(self, run_id: str) -> list[dict]:
        with self._read() as cx:
            rows = cx.execute(
                "SELECT tick, agent_id, obs_json, action_json, reward, terminated, "
                "truncated, info_json FROM sim_transitions WHERE run_id=? "
                "ORDER BY tick, rowid_pk", (run_id,),
            ).fetchall()
        keys = ["tick", "agent_id", "obs", "action", "reward", "terminated",
                "truncated", "info"]
        out = []
        for r in rows:
            d = dict(zip(keys, r))
            d["obs"] = json.loads(d["obs"])
            d["action"] = json.loads(d["action"])
            d["info"] = json.loads(d["info"])
            d["terminated"] = bool(d["terminated"])
            d["truncated"] = bool(d["truncated"])
            out.append(d)
        return out

    # ── checkpoints ──────────────────────────────────────────────────────

    def save_checkpoint(self, run_id: str, tick: int, state: dict) -> str:
        checkpoint_id = uuid.uuid4().hex[:12]
        with self._write() as cx:
            cx.execute(
                "INSERT INTO sim_checkpoints (checkpoint_id, run_id, tick, state_json, "
                "created_at) VALUES (?,?,?,?,?)",
                (checkpoint_id, run_id, tick, json.dumps(state), time.time()),
            )
        return checkpoint_id

    def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        with self._read() as cx:
            row = cx.execute(
                "SELECT checkpoint_id, run_id, tick, state_json, created_at "
                "FROM sim_checkpoints WHERE checkpoint_id=?", (checkpoint_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_checkpoint(row)

    def latest_checkpoint(self, run_id: str) -> dict | None:
        with self._read() as cx:
            row = cx.execute(
                "SELECT checkpoint_id, run_id, tick, state_json, created_at "
                "FROM sim_checkpoints WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_checkpoint(row)

    @staticmethod
    def _row_to_checkpoint(row: tuple) -> dict:
        checkpoint_id, run_id, tick, state_json, created_at = row
        return {
            "checkpoint_id": checkpoint_id, "run_id": run_id, "tick": tick,
            "state": json.loads(state_json), "created_at": created_at,
        }

    # ── metrics ──────────────────────────────────────────────────────────

    def record_metric(self, run_id: str, metric_name: str, value: float,
                       tick: int | None = None) -> None:
        with self._write() as cx:
            cx.execute(
                "INSERT INTO sim_metrics (run_id, metric_name, value, tick) "
                "VALUES (?,?,?,?)", (run_id, metric_name, value, tick),
            )

    def get_metrics(self, run_id: str) -> list[dict]:
        with self._read() as cx:
            rows = cx.execute(
                "SELECT metric_name, value, tick FROM sim_metrics WHERE run_id=? "
                "ORDER BY rowid_pk", (run_id,),
            ).fetchall()
        return [dict(zip(["metric_name", "value", "tick"], r)) for r in rows]
