"""Educational training -- each agent works through a shared curriculum of
real built-in benchmark tasks (ollama_arena.tasks.get_tasks()), one task per
tick, scored with the same evaluator the rest of the arena uses.

Unlike Mafia/Sims-world, the per-tick "observation" legitimately includes
the current task's full instruction text -- that's not a ground-truth leak,
it's literally the question being put to the agent, exactly like a student
being handed the next problem in a workbook. Agents progress through the
curriculum independently and "graduate" (are removed from `living`) once
they've answered every task; the episode terminates once every agent has
graduated, or truncates once the curriculum length is exhausted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..core.action_schema import ActionSchema
from ..core.scenario import ScenarioSpec, register_scenario
from ..core.types import (
    Action, AgentId, EpisodeResult, Event, Observation, StepMode, Transition,
    WITNESS_ALL,
)
from ..core.world import World
from ..eval.scoring import ScenarioScorer

PHASE_CURRICULUM = "curriculum"


@dataclass
class AnswerAction(ActionSchema):
    answer: str


def _build_curriculum(config: dict) -> list[dict]:
    from ...tasks import get_tasks
    category = config.get("category") or "math"
    n_tasks = config.get("n_tasks") or 5
    tasks = get_tasks(category=category, limit=n_tasks)
    if not tasks:
        raise ValueError(f"no built-in tasks found for category {category!r}")
    return tasks


class EducationalWorld(World):
    def __init__(self, agent_ids: list[AgentId], config: dict | None = None):
        if not agent_ids:
            raise ValueError("Educational requires at least 1 agent")
        self.agent_ids = list(agent_ids)
        config = config or {}
        self.curriculum = config.get("curriculum") or _build_curriculum(config)
        self._event_ids_issued = 0
        self._new_events: list[Event] = []
        self._all_events: list[Event] = []
        self.tick_count = 0
        self.living: set[AgentId] = set()
        self.progress: dict[AgentId, int] = {}
        self.scores: dict[AgentId, list[float]] = {}

    def _next_event_id(self) -> str:
        self._event_ids_issued += 1
        return f"e{self._event_ids_issued}"

    def _emit(self, kind: str, payload: dict, witness_ids=WITNESS_ALL, actor_id=None) -> Event:
        event = Event(
            id=self._next_event_id(), tick=self.tick_count, kind=kind, payload=payload,
            witness_ids=witness_ids, actor_id=actor_id,
        )
        self._all_events.append(event)
        self._new_events.append(event)
        return event

    # ── lifecycle ────────────────────────────────────────────────────────

    def reset(self, seed: int | None = None) -> dict[AgentId, Observation]:
        self.tick_count = 0
        self.living = set(self.agent_ids)
        self.progress = {aid: 0 for aid in self.agent_ids}
        self.scores = {aid: [] for aid in self.agent_ids}
        self._all_events = []
        self._new_events = []
        self._event_ids_issued = 0
        return {a: self.observe(a) for a in self.agent_ids}

    def restore_state(self, state: dict) -> None:
        self.tick_count = state["tick"]
        self.living = set(state["living"])
        self.progress = dict(state["progress"])
        self.scores = {aid: list(s) for aid, s in state["scores"].items()}
        self._event_ids_issued = state["event_ids_issued"]
        self._all_events = [
            Event(id=e["id"], tick=e["tick"], kind=e["kind"], payload=e["payload"],
                  witness_ids=frozenset(e["witness_ids"]), actor_id=e.get("actor_id"))
            for e in state["events"]
        ]
        self._new_events = []

    # ── observation / ground truth ──────────────────────────────────────

    def _current_task(self, agent_id: AgentId) -> dict | None:
        idx = self.progress.get(agent_id, 0)
        if idx >= len(self.curriculum):
            return None
        return self.curriculum[idx]

    def observe(self, agent_id: AgentId) -> Observation:
        visible = tuple(e for e in self._all_events if e.visible_to(agent_id))
        task = self._current_task(agent_id)
        status = {
            "alive": agent_id in self.living, "tick": self.tick_count,
            "progress": self.progress.get(agent_id, 0), "total_tasks": len(self.curriculum),
            "current_task": {"id": task["id"], "instruction": task["instruction"]} if task else None,
        }
        return Observation(agent_id=agent_id, tick=self.tick_count, visible_events=visible, status=status)

    def state(self) -> dict:
        avg_scores = {
            aid: (sum(s) / len(s) if s else 0.0) for aid, s in self.scores.items()
        }
        return {
            "tick": self.tick_count, "living": sorted(self.living),
            "progress": dict(self.progress),
            "scores": {aid: list(s) for aid, s in self.scores.items()},
            "event_ids_issued": self._event_ids_issued,
            "events": [
                {"id": e.id, "tick": e.tick, "kind": e.kind, "payload": e.payload,
                 "witness_ids": sorted(e.witness_ids), "actor_id": e.actor_id}
                for e in self._all_events
            ],
            "outcome": {
                "graduated": sorted(a for a in self.agent_ids if a not in self.living),
                "avg_scores": avg_scores,
            },
        }

    # ── stepping ─────────────────────────────────────────────────────────

    def agent_iter(self) -> Iterator[AgentId]:
        return iter(())  # always simultaneous

    def acting_agents(self) -> set[AgentId] | None:
        return set(self.living)

    def current_step_mode(self) -> StepMode:
        return StepMode.SIMULTANEOUS

    def current_phase(self) -> str:
        return PHASE_CURRICULUM

    def drain_new_events(self) -> list[Event]:
        events, self._new_events = self._new_events, []
        return events

    def step_turn_based(self, agent_id: AgentId, action: Action) -> Transition:
        raise NotImplementedError("Educational only steps simultaneously")

    def step_simultaneous(self, actions: dict[AgentId, Action]) -> dict[AgentId, Transition]:
        from ...evaluator import evaluate

        obs_before = {aid: self.observe(aid) for aid in actions}

        for aid, action in actions.items():
            task = self._current_task(aid)
            if task is None or action.kind != "answer":
                self._emit("invalid_action", {"agent": aid, "kind": action.kind},
                            witness_ids=frozenset(), actor_id=aid)
                continue
            score = evaluate(task, action.payload.get("answer", "")) or 0.0
            self.scores[aid].append(score)
            self._emit("answered", {"agent": aid, "task_id": task["id"], "score": score}, actor_id=aid)
            self.progress[aid] += 1
            if self.progress[aid] >= len(self.curriculum):
                self.living.discard(aid)
                self._emit("graduated", {"agent": aid}, witness_ids=WITNESS_ALL)

        self.tick_count += 1

        return {
            aid: Transition(
                tick=self.tick_count, agent_id=aid, obs=obs_before[aid], action=actions[aid],
                reward=self.scores[aid][-1] if self.scores.get(aid) else 0.0,
                terminated=self.is_terminated(), truncated=self.is_truncated(),
                info={},
            )
            for aid in actions
        }

    def is_terminated(self) -> bool:
        return len(self.living) == 0

    def is_truncated(self) -> bool:
        return self.tick_count >= len(self.curriculum) and bool(self.living)


class EducationalScorer(ScenarioScorer):
    def score(self, episode: EpisodeResult) -> dict[str, float]:
        avg_scores = episode.outcome.get("avg_scores", {})
        overall = sum(avg_scores.values()) / len(avg_scores) if avg_scores else 0.0
        graduated = len(episode.outcome.get("graduated", []))
        return {
            "avg_score": overall,
            "graduation_rate": graduated / max(1, len(avg_scores)),
        }


register_scenario(ScenarioSpec(
    name="educational",
    description="Sequential curriculum: agents answer real built-in "
                 "benchmark tasks one at a time, scored with the arena's "
                 "own evaluator.",
    world_factory=EducationalWorld,
    action_schema_by_kind={"answer": AnswerAction},
    step_mode_by_phase={PHASE_CURRICULUM: StepMode.SIMULTANEOUS},
    default_config={"category": "math", "n_tasks": 5},
    scorer_factory=EducationalScorer,
))
