"""Tests for agentic/swarm.py — SwarmAgent, SwarmTeam, SwarmBattle."""
from __future__ import annotations

import unittest.mock as mock
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# AgentRole enum
# ──────────────────────────────────────────────────────────────────────────────

class TestAgentRole:
    def test_all_roles(self):
        from ollama_arena.agentic.swarm import AgentRole
        assert AgentRole.CODER == "coder"
        assert AgentRole.TESTER == "tester"
        assert AgentRole.REVIEWER == "reviewer"
        assert AgentRole.PLANNER == "planner"
        assert AgentRole.RESEARCHER == "researcher"
        assert AgentRole.COORDINATOR == "coordinator"
        assert AgentRole.GENERALIST == "generalist"
        assert len(AgentRole) == 7


# ──────────────────────────────────────────────────────────────────────────────
# SwarmAgent
# ──────────────────────────────────────────────────────────────────────────────

class TestSwarmAgent:
    def _make(self):
        from ollama_arena.agentic.swarm import SwarmAgent, AgentRole
        return SwarmAgent(model="phi-4", role=AgentRole.CODER)

    def test_defaults(self):
        agent = self._make()
        assert agent.messages == []
        assert agent.contributions == []
        assert agent.tool_calls == 0
        assert agent.system_prompt == ""

    def test_add_message(self):
        agent = self._make()
        agent.add_message("user", "hello")
        assert len(agent.messages) == 1
        assert agent.messages[0] == {"role": "user", "content": "hello"}

    def test_add_contribution(self):
        agent = self._make()
        agent.add_contribution("wrote a function")
        assert len(agent.contributions) == 1
        assert agent.contributions[0] == "wrote a function"

    def test_get_summary(self):
        agent = self._make()
        agent.add_message("user", "x")
        agent.add_contribution("y")
        s = agent.get_summary()
        assert s["model"] == "phi-4"
        assert s["role"] == "coder"
        assert s["messages_count"] == 1
        assert s["contributions_count"] == 1
        assert s["tool_calls"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# SwarmTeam
# ──────────────────────────────────────────────────────────────────────────────

class TestSwarmTeam:
    def _make_team(self):
        from ollama_arena.agentic.swarm import SwarmTeam, SwarmAgent, AgentRole
        agents = [
            SwarmAgent(model="phi-4", role=AgentRole.CODER),
            SwarmAgent(model="qwen", role=AgentRole.TESTER),
        ]
        return SwarmTeam(name="TeamA", agents=agents)

    def test_get_agent_by_role_found(self):
        from ollama_arena.agentic.swarm import AgentRole
        team = self._make_team()
        agent = team.get_agent_by_role(AgentRole.CODER)
        assert agent is not None
        assert agent.model == "phi-4"

    def test_get_agent_by_role_not_found(self):
        from ollama_arena.agentic.swarm import AgentRole
        team = self._make_team()
        agent = team.get_agent_by_role(AgentRole.PLANNER)
        assert agent is None

    def test_broadcast_message(self):
        from ollama_arena.agentic.swarm import AgentRole
        team = self._make_team()
        team.broadcast_message(AgentRole.CODER, "here is my code")
        coder = team.get_agent_by_role(AgentRole.CODER)
        tester = team.get_agent_by_role(AgentRole.TESTER)
        # Coder gets the message as assistant, tester as user
        assert any(m["role"] == "assistant" for m in coder.messages)
        assert any(m["role"] == "user" for m in tester.messages)

    def test_broadcast_from_unknown_role(self):
        from ollama_arena.agentic.swarm import AgentRole
        team = self._make_team()
        # Should not crash even if sender role doesn't exist
        team.broadcast_message(AgentRole.PLANNER, "message from planner")
        for agent in team.agents:
            assert len(agent.messages) >= 1  # all received the message

    def test_add_shared_context(self):
        team = self._make_team()
        team.add_shared_context("key", [1, 2, 3])
        assert team.shared_context["key"] == [1, 2, 3]

    def test_calculate_collaboration_score_empty_team(self):
        from ollama_arena.agentic.swarm import SwarmTeam
        team = SwarmTeam(name="Empty", agents=[])
        score = team.calculate_collaboration_score()
        assert score == 0.0

    def test_calculate_collaboration_score_with_messages(self):
        team = self._make_team()
        for agent in team.agents:
            for i in range(5):
                agent.add_message("user", f"msg {i}")
        score = team.calculate_collaboration_score()
        assert 0.0 <= score <= 1.2  # diversity bonus can push above 1

    def test_collaboration_score_stored(self):
        team = self._make_team()
        team.calculate_collaboration_score()
        assert team.collaboration_score >= 0.0


# ──────────────────────────────────────────────────────────────────────────────
# SwarmBattle
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def battle():
    from ollama_arena.agentic.swarm import SwarmBattle
    backend = mock.MagicMock()
    mcp = mock.MagicMock()
    return SwarmBattle(backend=backend, mcp=mcp)


class TestSwarmBattleCreateTeam:
    def test_create_team_returns_swarm_team(self, battle):
        from ollama_arena.agentic.swarm import SwarmTeam, AgentRole
        team = battle.create_team("Alpha", {"phi-4": AgentRole.CODER, "qwen": AgentRole.TESTER})
        assert isinstance(team, SwarmTeam)
        assert team.name == "Alpha"
        assert len(team.agents) == 2

    def test_create_team_with_custom_prompts(self, battle):
        from ollama_arena.agentic.swarm import AgentRole
        prompts = {AgentRole.CODER: "You are a specialist."}
        team = battle.create_team("Beta", {"phi-4": AgentRole.CODER}, system_prompts=prompts)
        coder = team.get_agent_by_role(AgentRole.CODER)
        assert coder.system_prompt == "You are a specialist."

    def test_create_team_uses_default_prompts(self, battle):
        from ollama_arena.agentic.swarm import AgentRole
        team = battle.create_team("Gamma", {"phi-4": AgentRole.GENERALIST})
        generalist = team.get_agent_by_role(AgentRole.GENERALIST)
        assert len(generalist.system_prompt) > 0


class TestSwarmBattleDefaultPrompts:
    def test_all_roles_have_prompts(self, battle):
        from ollama_arena.agentic.swarm import AgentRole
        for role in AgentRole:
            prompt = battle._default_system_prompt(role)
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_unknown_role_fallback(self, battle):
        prompt = battle._default_system_prompt("unknown_role")
        assert "helpful" in prompt.lower()


class TestSwarmBattleHelpers:
    def _make_team(self, n_agents=2):
        from ollama_arena.agentic.swarm import SwarmTeam, SwarmAgent, AgentRole
        agents = [
            SwarmAgent(model=f"model_{i}", role=list(AgentRole)[i % len(AgentRole)])
            for i in range(n_agents)
        ]
        return SwarmTeam(name="TestTeam", agents=agents)

    def test_check_task_completion_not_done(self, battle):
        team = self._make_team(2)
        assert battle._check_task_completion(team) is False

    def test_check_task_completion_done(self, battle):
        team = self._make_team(2)
        for agent in team.agents:
            agent.add_contribution("c1")
            agent.add_contribution("c2")
        assert battle._check_task_completion(team) is True

    def test_evaluate_completion_returns_float(self, battle):
        team = self._make_team(2)
        for agent in team.agents:
            for i in range(3):
                agent.add_message("user", f"msg{i}")
        score = battle._evaluate_completion(team, "do stuff")
        assert 0.0 <= score <= 1.0


class TestSwarmBattleRunBattle:
    def _make_teams(self, battle):
        from ollama_arena.agentic.swarm import AgentRole
        team_a = battle.create_team("A", {"phi-4": AgentRole.CODER, "qwen": AgentRole.TESTER})
        team_b = battle.create_team("B", {"llama": AgentRole.CODER, "mistral": AgentRole.TESTER})
        return team_a, team_b

    def test_run_battle_returns_swarm_result(self, battle):
        from ollama_arena.agentic.swarm import SwarmResult
        resp = mock.MagicMock()
        resp.text = "Here is my implementation."
        resp.tokens_out = 100
        resp.latency_s = 0.5
        battle.backend.generate.return_value = resp
        team_a, team_b = self._make_teams(battle)
        result = battle.run_battle(team_a, team_b, "Build a simple function", rounds=1)
        assert isinstance(result, SwarmResult)
        assert result.winner in [team_a.name, team_b.name, "draw"]

    def test_run_battle_appends_to_history(self, battle):
        resp = mock.MagicMock()
        resp.text = "x"
        resp.tokens_out = 10
        resp.latency_s = 0.1
        battle.backend.generate.return_value = resp
        team_a, team_b = self._make_teams(battle)
        battle.run_battle(team_a, team_b, "task", rounds=1)
        assert len(battle.battle_history) == 1

    def test_run_battle_error_in_backend(self, battle):
        battle.backend.generate.side_effect = RuntimeError("timeout")
        from ollama_arena.agentic.swarm import AgentRole
        team_a = battle.create_team("A", {"phi-4": AgentRole.CODER})
        team_b = battle.create_team("B", {"llama": AgentRole.CODER})
        result = battle.run_battle(team_a, team_b, "task", rounds=1)
        assert result is not None  # Should still complete despite errors

    def test_run_battle_zero_rounds_does_not_crash(self, battle):
        """Regression: rounds=0 used to raise UnboundLocalError because
        `round_num` (the loop variable) was referenced after the loop in
        `rounds_completed=round_num` without ever being bound when
        range(1, rounds + 1) is empty. CLI-reachable via
        `ollama-arena swarm --rounds 0`."""
        resp = mock.MagicMock()
        resp.text = "x"
        resp.tokens_out = 1
        resp.latency_s = 0.1
        battle.backend.generate.return_value = resp
        team_a, team_b = self._make_teams(battle)
        result = battle.run_battle(team_a, team_b, "task", rounds=0)
        assert result.rounds_completed == 0

    def test_run_battle_negative_rounds_does_not_crash(self, battle):
        resp = mock.MagicMock()
        resp.text = "x"
        resp.tokens_out = 1
        resp.latency_s = 0.1
        battle.backend.generate.return_value = resp
        team_a, team_b = self._make_teams(battle)
        result = battle.run_battle(team_a, team_b, "task", rounds=-1)
        assert result.rounds_completed == 0


class TestSwarmBattleStatistics:
    def test_empty_statistics(self, battle):
        assert battle.get_battle_statistics() == {}

    def test_statistics_with_battles(self, battle):
        from ollama_arena.agentic.swarm import SwarmResult
        result = SwarmResult(
            team_a_name="A", team_b_name="B",
            team_a_score=0.8, team_b_score=0.3,
            team_a_details={}, team_b_details={},
            winner="A", task="test", duration_s=2.5,
            rounds_completed=3,
            collaboration_metrics={},
        )
        battle.battle_history.append(result)
        stats = battle.get_battle_statistics()
        assert stats["total_battles"] == 1
        assert stats["team_wins"]["A"] == 1
        assert stats["average_duration_s"] == pytest.approx(2.5)

    def test_statistics_draw_not_counted(self, battle):
        from ollama_arena.agentic.swarm import SwarmResult
        result = SwarmResult(
            team_a_name="A", team_b_name="B",
            team_a_score=0.5, team_b_score=0.5,
            team_a_details={}, team_b_details={},
            winner="draw", task="test", duration_s=1.0,
            rounds_completed=3,
            collaboration_metrics={},
        )
        battle.battle_history.append(result)
        stats = battle.get_battle_statistics()
        assert "draw" not in stats.get("team_wins", {})


# ──────────────────────────────────────────────────────────────────────────────
# Example setup functions
# ──────────────────────────────────────────────────────────────────────────────

class TestExampleSetups:
    def test_example_2v2(self):
        from ollama_arena.agentic.swarm import example_2v2_setup, AgentRole
        team_a, team_b = example_2v2_setup()
        assert AgentRole.CODER in team_a.values()
        assert AgentRole.TESTER in team_a.values()
        assert AgentRole.CODER in team_b.values()

    def test_example_3v3(self):
        from ollama_arena.agentic.swarm import example_3v3_setup, AgentRole
        team_a, team_b = example_3v3_setup()
        assert AgentRole.CODER in team_a.values()
        assert AgentRole.REVIEWER in team_a.values()
        assert AgentRole.PLANNER in team_b.values()
