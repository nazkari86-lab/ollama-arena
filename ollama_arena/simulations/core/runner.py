"""SimulationManager -- the run lifecycle state machine.

Modeled directly on `tasks.long_horizon.LongHorizonTaskManager`'s verbs
(create/start/pause/resume/complete), but backed by sim.db (SQLite) instead
of in-memory dicts + JSON checkpoint files, so runs/events/transitions are
queryable and survive a process restart.
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Callable

from ..agents.base import SimAgent
from ..agents.llm_agent import LLMSimAgent
from ..storage import SimStore
from .scenario import ScenarioSpec, get_scenario
from .types import AgentSpec, EpisodeResult, StepMode, WITNESS_ALL

log = logging.getLogger("arena.simulations.runner")


class SimStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationManager:
    """Owns the create/start/pause/resume/complete lifecycle for sim runs.

    One instance per `sim.db` file. Agent construction is pluggable via
    `agent_factory` (defaults to wrapping each AgentSpec in an
    `LLMSimAgent`) so tests can substitute scripted agents without touching
    the manager itself.
    """

    def __init__(
        self,
        db_path: str = "sim.db",
        agent_factory: Callable[[AgentSpec, ScenarioSpec], SimAgent] | None = None,
    ):
        self.store = SimStore(db_path)
        self._agent_factory = agent_factory or self._default_agent_factory
        self._paused = False

    @staticmethod
    def _default_agent_factory(agent_spec: AgentSpec, scenario: ScenarioSpec) -> SimAgent:
        return LLMSimAgent(
            agent_id=agent_spec.agent_id,
            model=agent_spec.model,
            action_schema_by_kind=scenario.action_schema_by_kind,
            config=agent_spec.config,
        )

    # ── lifecycle ────────────────────────────────────────────────────────

    def create_run(
        self, scenario_name: str, agents: list[AgentSpec], config: dict | None = None,
        seed: int | None = None,
    ) -> str:
        get_scenario(scenario_name)  # raises KeyError early if unknown
        return self.store.create_run(scenario_name, agents, config or {}, seed=seed)

    def get_status(self, run_id: str) -> SimStatus:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown run {run_id!r}")
        return SimStatus(run["status"])

    def list_runs(self, scenario_name: str | None = None) -> list[dict]:
        return self.store.list_runs(scenario_name)

    def start_run(
        self,
        run_id: str,
        on_tick: Callable[[dict[str, Any]], None] | None = None,
        max_ticks: int = 1000,
    ) -> EpisodeResult:
        """Run from tick 0 (or from the latest checkpoint, if resuming a
        previously-paused run) through to termination/truncation/a pause
        request, persisting every event/transition as it happens."""
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown run {run_id!r}")
        spec = get_scenario(run["scenario"])
        agent_specs = [
            AgentSpec(agent_id=a["agent_id"], model=a["model"], config=a.get("config", {}))
            for a in run["agents"]
        ]
        agents = {a.agent_id: self._agent_factory(a, spec) for a in agent_specs}
        models_by_agent = {a.agent_id: a.model for a in agent_specs}

        world = spec.world_factory(
            agent_ids=[a.agent_id for a in agent_specs], config=run["config"],
        )

        checkpoint = self.store.latest_checkpoint(run_id)
        if checkpoint is not None:
            world.restore_state(checkpoint["state"])
            tick = checkpoint["tick"]
        else:
            world.reset(seed=run["seed"])
            tick = 0

        self.store.update_run_status(run_id, "in_progress", started_at=time.time())
        self._paused = False

        while not world.is_terminated() and not world.is_truncated() and tick < max_ticks:
            if self._paused:
                break
            mode = world.current_step_mode()
            if mode == StepMode.TURN_BASED:
                transitions = []
                for agent_id in world.agent_iter():
                    obs = world.observe(agent_id)
                    action = agents[agent_id].act(obs)
                    transitions.append(world.step_turn_based(agent_id, action))
            else:
                acting = world.acting_agents()
                target_ids = agents.keys() if acting is None else (acting & agents.keys())
                actions = {aid: agents[aid].act(world.observe(aid)) for aid in target_ids}
                transitions = list(world.step_simultaneous(actions).values())

            new_events = world.drain_new_events()
            self.store.append_events(run_id, new_events)
            self.store.append_transitions(run_id, transitions)
            tick += 1

            if on_tick:
                agent_states = {}
                for agent_id in agents:
                    try:
                        agent_states[agent_id] = world.observe(agent_id).status
                    except KeyError:
                        agent_states[agent_id] = {"available": False}
                on_tick({
                    "run_id": run_id, "tick": tick, "phase": world.current_phase(),
                    "n_events": len(new_events),
                    "step_mode": mode.value,
                    "progress": min(1.0, tick / max(max_ticks, 1)),
                    "agents": [
                        {
                            "agent_id": transition.agent_id,
                            "model": models_by_agent.get(transition.agent_id, transition.agent_id),
                            "action": {
                                "kind": transition.action.kind,
                                "payload": transition.action.payload,
                            },
                            "reward": transition.reward,
                            "terminated": transition.terminated,
                            "truncated": transition.truncated,
                            "status": agent_states.get(transition.agent_id, {}),
                        }
                        for transition in transitions
                    ],
                    "events": [
                        {
                            "id": event.id,
                            "tick": event.tick,
                            "kind": event.kind,
                            "payload": event.payload,
                            "actor_id": event.actor_id,
                            "visibility": (
                                "public" if event.witness_ids == WITNESS_ALL else "private"
                            ),
                        }
                        for event in new_events
                    ],
                })

        if self._paused:
            # pause_run() already set status="paused" and broke the loop
            # above -- checkpoint here so resume_run() picks up at this
            # exact tick, and return without overwriting that status.
            self.store.save_checkpoint(run_id, tick, world.state())
            return EpisodeResult(
                scenario=run["scenario"], run_id=run_id, ticks=tick,
                terminated=False, truncated=False, outcome={},
            )

        truncated_by_budget = tick >= max_ticks and not world.is_terminated()
        result = EpisodeResult(
            scenario=run["scenario"], run_id=run_id, ticks=tick,
            terminated=world.is_terminated(),
            truncated=world.is_truncated() or truncated_by_budget,
            outcome=world.state().get("outcome", {}),
        )
        if spec.scorer_factory is not None:
            result.metrics = spec.scorer_factory().score(result)
            for name, value in result.metrics.items():
                self.store.record_metric(run_id, name, value, tick=tick)

        self.store.set_run_outcome(run_id, result.outcome)
        self.store.update_run_status(run_id, "completed", completed_at=time.time())
        return result

    def pause_run(self, run_id: str) -> str:
        """Request the in-progress run loop stop after its current tick and
        write a checkpoint. Note: in this in-process runner, pause only has
        an effect if called from the `on_tick` callback of the same
        `start_run()` call (there is no background thread) -- the primary
        use case is a long Sims-world run explicitly checkpointing every
        N ticks via its own on_tick hook, not pausing another thread."""
        self._paused = True
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown run {run_id!r}")
        self.store.update_run_status(run_id, "paused")
        return run_id

    def resume_run(
        self, run_id: str, on_tick: Callable[[dict[str, Any]], None] | None = None,
        max_ticks: int = 1000,
    ) -> EpisodeResult:
        """Resume a paused run from its latest checkpoint. Implemented as
        `start_run()` since that already checks for + restores a checkpoint
        before resetting -- a fresh run simply has none yet."""
        return self.start_run(run_id, on_tick=on_tick, max_ticks=max_ticks)

    def checkpoint_now(self, run_id: str, world, tick: int) -> str:
        """Explicit checkpoint helper for long-running scenarios (Sims-world)
        that want to save state every N ticks rather than only on pause."""
        return self.store.save_checkpoint(run_id, tick, world.state())
