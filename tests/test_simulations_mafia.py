"""Mafia: hidden roles, witness-filtered night events, win conditions,
checkpoint/resume, all driven by deterministic scripted agents (no real or
mocked LLM calls needed for engine-level correctness)."""
import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec
from ollama_arena.simulations.scenarios.mafia import ROLE_MAFIA, ROLE_VILLAGER

AGENTS = ["a", "b", "c", "d", "e"]  # sorted -> mafia_count = 5 // 3 = 1 -> "a" is mafia


class ScriptedMafiaAgent(SimAgent):
    """Plays according to a phase -> action-builder mapping supplied by the
    test, so each test can script exactly the votes/kills it needs."""
    def __init__(self, agent_id, vote_target="a", kill_target="c", speak_text="hi"):
        self.agent_id = agent_id
        self.vote_target = vote_target
        self.kill_target = kill_target
        self.speak_text = speak_text

    def act(self, obs):
        phase = obs.status["phase"]
        if phase == "discussion":
            return Action(self.agent_id, "speak", {"text": self.speak_text}, "")
        if phase == "vote":
            target = self.vote_target(self.agent_id) if callable(self.vote_target) else self.vote_target
            return Action(self.agent_id, "vote", {"target": target}, "")
        if phase == "night":
            return Action(self.agent_id, "night_kill", {"target": self.kill_target}, "")
        raise AssertionError(f"unexpected phase {phase!r}")


def _factory_everyone_votes_a():
    """Round 1: every villager votes 'a' (the mafia), 'a' votes 'b' -- town
    should correctly identify and eliminate the mafia member."""
    agents = {
        aid: ScriptedMafiaAgent(aid, vote_target=("b" if aid == "a" else "a"))
        for aid in AGENTS
    }
    return lambda agent_spec, scenario: agents[agent_spec.agent_id]


def _factory_everyone_votes_b_mafia_kills_c():
    """Round 1: everyone votes for villager 'b' (mafia survives the vote),
    then mafia 'a' kills villager 'c' at night."""
    agents = {aid: ScriptedMafiaAgent(aid, vote_target="b", kill_target="c") for aid in AGENTS}
    return lambda agent_spec, scenario: agents[agent_spec.agent_id]


@pytest.fixture
def mgr(tmp_path):
    return SimulationManager(db_path=str(tmp_path / "sim.db"))


def test_roles_assigned_deterministically_from_sorted_agent_ids(tmp_path):
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory_everyone_votes_a())
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 10}, seed=1)
    result = mgr.start_run(run_id)
    assert result.outcome["roles"]["a"] == ROLE_MAFIA
    assert all(result.outcome["roles"][a] == ROLE_VILLAGER for a in AGENTS if a != "a")


def test_town_correctly_eliminates_mafia_and_wins(tmp_path):
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory_everyone_votes_a())
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 10}, seed=1)
    result = mgr.start_run(run_id)
    assert result.terminated is True
    assert result.outcome["winner_faction"] == ROLE_VILLAGER
    assert "a" not in result.outcome["living"]
    elimination_events = [e for e in mgr.store.get_events(run_id) if e.kind == "elimination"]
    assert elimination_events[0].payload["eliminated"] == "a"


def test_villager_never_witnesses_the_private_night_kill_event(tmp_path):
    """The core hidden-information guarantee: a villager's witness-filtered
    event log must never contain the mafia-only night_kill_decided event,
    only the derived public morning_announcement."""
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=_factory_everyone_votes_b_mafia_kills_c())
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 1}, seed=1)
    mgr.start_run(run_id)

    villager_kinds = {e.kind for e in mgr.store.get_events(run_id, witness_id="d")}
    mafia_kinds = {e.kind for e in mgr.store.get_events(run_id, witness_id="a")}

    assert "night_kill_decided" not in villager_kinds
    assert "morning_announcement" in villager_kinds
    assert "night_kill_decided" in mafia_kinds
    assert "morning_announcement" in mafia_kinds


def test_mafia_kill_removes_target_from_living_and_announces_publicly(tmp_path):
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=_factory_everyone_votes_b_mafia_kills_c())
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 1}, seed=1)
    mgr.start_run(run_id)
    announcements = [e for e in mgr.store.get_events(run_id) if e.kind == "morning_announcement"]
    assert len(announcements) == 1
    assert announcements[0].payload["killed"] == "c"


def test_observe_reveals_own_role_and_mafia_teammates_but_not_others(tmp_path):
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory_everyone_votes_a())
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 10, "mafia_count": 2}, seed=1)
    # build the world directly to inspect observe() without running a full episode
    from ollama_arena.simulations.scenarios.mafia import MafiaWorld
    world = MafiaWorld(AGENTS, config={"mafia_count": 2})
    world.reset(seed=1)
    mafia_ids = sorted(a for a, r in world.roles.items() if r == ROLE_MAFIA)
    villager_ids = sorted(a for a, r in world.roles.items() if r == ROLE_VILLAGER)

    obs_mafia = world.observe(mafia_ids[0])
    assert obs_mafia.status["role"] == ROLE_MAFIA
    assert obs_mafia.status["mafia_team"] == [m for m in mafia_ids if m != mafia_ids[0]]

    obs_villager = world.observe(villager_ids[0])
    assert obs_villager.status["role"] == ROLE_VILLAGER
    assert "mafia_team" not in obs_villager.status


def test_tie_vote_eliminates_nobody(tmp_path):
    """A 2-2 tie among 4 living voters (5th is mafia who votes differently)
    must not eliminate anyone -- ties are a no-op by design, not resolved
    by an arbitrary/random tiebreak, so the outcome is deterministic.

    Vote tally: "b" gets votes from {a, c} = 2; "a" gets votes from {b, d}
    = 2; "c" gets 1 vote from {e}. "a" and "b" are tied for the plurality,
    so nobody is eliminated this round."""
    agents = {
        "a": ScriptedMafiaAgent("a", vote_target="b"),
        "b": ScriptedMafiaAgent("b", vote_target="a"),
        "c": ScriptedMafiaAgent("c", vote_target="b"),
        "d": ScriptedMafiaAgent("d", vote_target="a"),
        "e": ScriptedMafiaAgent("e", vote_target="c"),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 1}, seed=1)
    mgr.start_run(run_id)
    elimination = [e for e in mgr.store.get_events(run_id) if e.kind == "elimination"][0]
    assert elimination.payload["eliminated"] is None


def test_off_phase_action_is_discarded_not_applied(tmp_path):
    """An agent submitting a 'vote' action during the discussion phase (off-
    phase, e.g. an LLM ignoring obs.status['valid_kinds']) must not corrupt
    state -- the engine discards it and still advances the phase once every
    agent has acted once, rather than stalling or crashing."""
    class StubbornVoter(SimAgent):
        def __init__(self, agent_id):
            self.agent_id = agent_id

        def act(self, obs):
            # Always tries to vote, even during discussion.
            return Action(self.agent_id, "vote", {"target": "a"}, "")

    agents = {aid: StubbornVoter(aid) for aid in AGENTS}
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 1}, seed=1)
    result = mgr.start_run(run_id)
    assert result.ticks >= 1
    invalid_events = [e for e in mgr.store.get_events(run_id) if e.kind == "invalid_action"]
    assert len(invalid_events) == 5  # all 5 agents' discussion-phase votes were discarded
    assert all(e.witness_ids == frozenset() for e in invalid_events)


def test_pause_then_resume_continues_with_same_roles_and_living_set(tmp_path):
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=_factory_everyone_votes_b_mafia_kills_c())
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 5}, seed=1)

    def pause_after_discussion(d):
        if d["phase"] == "vote":  # paused right after discussion finalized
            mgr.pause_run(run_id)

    mgr.start_run(run_id, on_tick=pause_after_discussion)
    assert mgr.get_status(run_id).value == "paused"
    checkpoint = mgr.store.latest_checkpoint(run_id)
    assert checkpoint["state"]["phase"] == "vote"
    assert checkpoint["state"]["roles"]["a"] == ROLE_MAFIA

    pre_resume_event_count = len(mgr.store.get_events(run_id))

    result = mgr.resume_run(run_id)
    assert result.terminated is False
    assert result.truncated is True  # max_rounds=5, no winner with this script
    # Resuming must continue play (more rounds happen, more events accumulate),
    # not silently restart from round 0 with a fresh, empty event log.
    assert len(mgr.store.get_events(run_id)) > pre_resume_event_count
    assert result.ticks > 1


def test_too_few_agents_raises_at_world_construction(tmp_path):
    from ollama_arena.simulations.scenarios.mafia import MafiaWorld
    with pytest.raises(ValueError, match="at least 3"):
        MafiaWorld(["a", "b"])


def test_mafia_wins_when_all_villagers_eliminated(tmp_path):
    """A 3-agent game (1 mafia, 2 villagers): the vote eliminates one
    villager, the mafia's night kill finishes off the other -- mafia wins.
    Only the mafia member's kill_target is ever actually used, since
    acting_agents() restricts night-phase actors to living mafia."""
    agents = {
        "a": ScriptedMafiaAgent("a", vote_target="b", kill_target="c"),
        "b": ScriptedMafiaAgent("b", vote_target="c", kill_target="c"),
        "c": ScriptedMafiaAgent("c", vote_target="b", kill_target="c"),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in ["a", "b", "c"]],
                             config={"max_rounds": 5, "mafia_count": 1}, seed=1)
    result = mgr.start_run(run_id)
    # round 1 vote eliminates "b" (2 of 3 votes); mafia "a" then kills "c" at night.
    assert result.terminated is True
    assert result.outcome["winner_faction"] == ROLE_MAFIA


def test_observe_gives_mafia_and_villager_different_strategy_hints(tmp_path):
    """Role-specific strategic framing (paraphrased from the Mini-Mafia
    benchmark's finding that explicit role strategy measurably improves
    both deception and detection quality) must reach each role's prompt
    via the generic Observation.status["strategy_hint"] channel."""
    from ollama_arena.simulations.scenarios.mafia import MafiaWorld
    world = MafiaWorld(AGENTS)
    world.reset(seed=1)
    mafia_hint = world.observe("a").status["strategy_hint"]
    villager_hint = world.observe("b").status["strategy_hint"]
    assert mafia_hint != villager_hint
    assert "consistent" in mafia_hint.lower()
    assert "contradiction" in villager_hint.lower()


def test_action_schemas_require_reasoning_field():
    """Extended reasoning before committing to an action measurably
    improved deception/detection/disclosure quality in the Mini-Mafia
    benchmark -- reasoning is a required field so a model that omits it
    fails to parse and gets the standard retry-once-then-forfeit
    treatment, the same as any other missing required field."""
    from ollama_arena.simulations.core.action_schema import ActionParseError, parse_action
    from ollama_arena.simulations.scenarios.mafia import SpeakAction, VoteAction, NightKillAction

    schemas = {"speak": SpeakAction, "vote": VoteAction, "night_kill": NightKillAction}
    with pytest.raises(ActionParseError):
        parse_action('{"kind": "vote", "target": "a"}', "x", schemas)
    action = parse_action(
        '{"kind": "vote", "reasoning": "b contradicted themself", "target": "a"}', "x", schemas,
    )
    assert action.payload["reasoning"] == "b contradicted themself"
    assert action.payload["target"] == "a"


def test_reasoning_field_never_leaks_into_public_events(tmp_path):
    """reasoning is recorded on the Action/Transition for replay/eval, but
    must never be copied into a witnessed Event payload -- that would let
    private deliberation leak to other agents and change game balance,
    which is out of scope for a prompt-quality improvement."""
    agents = {
        aid: ScriptedMafiaAgent(aid, vote_target=("b" if aid == "a" else "a"))
        for aid in AGENTS
    }
    for aid, agent in agents.items():
        orig_act = agent.act
        def act(obs, orig_act=orig_act):
            action = orig_act(obs)
            return Action(action.agent_id, action.kind,
                          {**action.payload, "reasoning": "SECRET_DELIBERATION"}, "")
        agent.act = act
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("mafia", [AgentSpec(agent_id=a, model="x") for a in AGENTS],
                             config={"max_rounds": 1}, seed=1)
    mgr.start_run(run_id)
    for event in mgr.store.get_events(run_id):
        assert "SECRET_DELIBERATION" not in str(event.payload)
