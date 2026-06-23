"""Swarm Battles: Multi-agent team competitions (2v2, 3v3).

Implements multi-agent protocol for model teams, message passing between
agents in a team, and team scoring based on collaboration quality + task completion.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

log = logging.getLogger("arena.agentic.swarm")


class AgentRole(str, Enum):
    """Roles that agents can play in a swarm."""
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    RESEARCHER = "researcher"
    COORDINATOR = "coordinator"
    GENERALIST = "generalist"


@dataclass
class SwarmAgent:
    """Represents a single agent in a swarm team."""
    model: str
    role: AgentRole
    system_prompt: str = ""
    messages: list[dict] = field(default_factory=list)
    contributions: list[str] = field(default_factory=list)
    tool_calls: int = 0

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the agent's history."""
        self.messages.append({"role": role, "content": content})

    def add_contribution(self, contribution: str) -> None:
        """Record a contribution from this agent."""
        self.contributions.append(contribution)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of agent activity."""
        return {
            "model": self.model,
            "role": self.role.value,
            "messages_count": len(self.messages),
            "contributions_count": len(self.contributions),
            "tool_calls": self.tool_calls,
        }


@dataclass
class SwarmTeam:
    """Represents a team of agents working together."""
    name: str
    agents: list[SwarmAgent]
    shared_context: dict[str, Any] = field(default_factory=dict)
    collaboration_score: float = 0.0
    task_completion_score: float = 0.0

    def get_agent_by_role(self, role: AgentRole) -> Optional[SwarmAgent]:
        """Get an agent by role."""
        for agent in self.agents:
            if agent.role == role:
                return agent
        return None

    def broadcast_message(self, sender_role: AgentRole, message: str) -> None:
        """Send a message from one agent to all teammates."""
        sender = self.get_agent_by_role(sender_role)
        if sender:
            sender.add_message("assistant", message)

        for agent in self.agents:
            if agent.role != sender_role:
                sender_name = f"{sender_role.value} ({sender.model})" if sender else "Unknown"
                agent.add_message("user", f"[Team message from {sender_name}]: {message}")

    def add_shared_context(self, key: str, value: Any) -> None:
        """Add information to the team's shared context."""
        self.shared_context[key] = value

    def calculate_collaboration_score(self) -> float:
        """Calculate collaboration score based on message passing."""
        if not self.agents:
            return 0.0

        total_messages = sum(len(a.messages) for a in self.agents)
        avg_messages = total_messages / len(self.agents)

        # Score based on communication volume (with diminishing returns)
        collaboration = min(1.0, avg_messages / 10.0)

        # Bonus for diverse contributions
        unique_contributors = len(set(a.model for a in self.agents))
        diversity_bonus = min(0.2, (unique_contributors - 1) * 0.1)

        self.collaboration_score = round(collaboration + diversity_bonus, 3)
        return self.collaboration_score


@dataclass
class SwarmResult:
    """Result of a swarm battle."""
    team_a_name: str
    team_b_name: str
    team_a_score: float
    team_b_score: float
    team_a_details: dict[str, Any]
    team_b_details: dict[str, Any]
    winner: str
    task: str
    duration_s: float
    rounds_completed: int
    collaboration_metrics: dict[str, Any]
    trace: list[dict] = field(default_factory=list)


class SwarmBattle:
    """Orchestrates swarm battles between teams of agents.

    Manages the multi-agent protocol, message passing, and scoring.
    """

    def __init__(
        self,
        backend: Any,  # Backend interface for model inference
        mcp: Any,  # MCP orchestrator for tool use
    ):
        self.backend = backend
        self.mcp = mcp
        self.battle_history: list[SwarmResult] = []

    def create_team(
        self,
        name: str,
        model_roles: dict[str, AgentRole],
        system_prompts: Optional[dict[AgentRole, str]] = None,
    ) -> SwarmTeam:
        """Create a swarm team with specified models and roles.

        Args:
            name: Team name
            model_roles: Mapping of model names to agent roles
            system_prompts: Optional role-specific system prompts

        Returns:
            Configured SwarmTeam
        """
        agents = []
        for model, role in model_roles.items():
            prompt = (system_prompts or {}).get(role, self._default_system_prompt(role))
            agents.append(SwarmAgent(model=model, role=role, system_prompt=prompt))

        return SwarmTeam(name=name, agents=agents)

    def _default_system_prompt(self, role: AgentRole) -> str:
        """Get default system prompt for a role."""
        prompts = {
            AgentRole.CODER: "You are an expert programmer. Write clean, efficient code. "
                           "Collaborate with your team to produce high-quality solutions.",
            AgentRole.TESTER: "You are a QA specialist. Write comprehensive tests and "
                             "identify edge cases. Collaborate with coders to ensure quality.",
            AgentRole.REVIEWER: "You are a code reviewer. Check for correctness, style, "
                               "security, and best practices. Provide constructive feedback.",
            AgentRole.PLANNER: "You are a project planner. Break down tasks and coordinate "
                              "team efforts. Ensure all aspects of the problem are addressed.",
            AgentRole.RESEARCHER: "You are a researcher. Find relevant information and "
                                 "provide context to the team.",
            AgentRole.COORDINATOR: "You are the team coordinator. Facilitate communication "
                                  "and ensure all agents contribute effectively.",
            AgentRole.GENERALIST: "You are a generalist. Help wherever needed and provide "
                                 "broad support to the team.",
        }
        return prompts.get(role, "You are a helpful AI assistant working in a team.")

    def run_battle(
        self,
        team_a: SwarmTeam,
        team_b: SwarmTeam,
        task: str,
        rounds: int = 3,
        max_steps_per_round: int = 5,
    ) -> SwarmResult:
        """Run a swarm battle between two teams.

        Args:
            team_a: First team
            team_b: Second team
            task: Task description for both teams
            rounds: Number of collaboration rounds
            max_steps_per_round: Max agent steps per round

        Returns:
            SwarmResult with battle outcome
        """
        log.info(f"Starting swarm battle: {team_a.name} vs {team_b.name}")
        t0 = time.time()
        trace = []

        # Initialize teams with task
        for team in [team_a, team_b]:
            for agent in team.agents:
                agent.add_message(
                    "system",
                    agent.system_prompt + f"\n\nTeam task: {task}\n"
                    f"Your team: {', '.join(a.role.value for a in team.agents)}\n"
                    f"Collaborate with your teammates to complete this task.",
                )
                agent.add_message("user", f"Task: {task}")

        # Run collaboration rounds
        round_num = 0
        for round_num in range(1, rounds + 1):
            log.info(f"Swarm battle round {round_num}/{rounds}")
            round_trace = self._run_round(team_a, team_b, round_num, max_steps_per_round)
            trace.append({"round": round_num, "events": round_trace})

            # Check for early completion
            if self._check_task_completion(team_a) and self._check_task_completion(team_b):
                log.info("Both teams completed task early")
                break

        # Calculate final scores
        team_a.calculate_collaboration_score()
        team_b.calculate_collaboration_score()

        # Evaluate task completion (simplified - in production would use actual evaluation)
        team_a.task_completion_score = self._evaluate_completion(team_a, task)
        team_b.task_completion_score = self._evaluate_completion(team_b, task)

        # Final scores: 70% task completion, 30% collaboration
        team_a_final = 0.7 * team_a.task_completion_score + 0.3 * team_a.collaboration_score
        team_b_final = 0.7 * team_b.task_completion_score + 0.3 * team_b.collaboration_score

        duration = round(time.time() - t0, 3)
        winner = team_a.name if team_a_final > team_b_final else team_b.name
        if team_a_final == team_b_final:
            winner = "draw"

        result = SwarmResult(
            team_a_name=team_a.name,
            team_b_name=team_b.name,
            team_a_score=round(team_a_final, 3),
            team_b_score=round(team_b_final, 3),
            team_a_details={"agents": [a.get_summary() for a in team_a.agents]},
            team_b_details={"agents": [a.get_summary() for a in team_b.agents]},
            winner=winner,
            task=task,
            duration_s=duration,
            rounds_completed=round_num,
            collaboration_metrics={
                "team_a_collaboration": team_a.collaboration_score,
                "team_b_collaboration": team_b.collaboration_score,
                "team_a_completion": team_a.task_completion_score,
                "team_b_completion": team_b.task_completion_score,
            },
            trace=trace,
        )

        self.battle_history.append(result)
        log.info(f"Swarm battle completed: {winner} wins ({team_a_final:.3f} vs {team_b_final:.3f})")
        return result

    def _run_round(
        self,
        team_a: SwarmTeam,
        team_b: SwarmTeam,
        round_num: int,
        max_steps: int,
    ) -> list[dict]:
        """Run a single collaboration round for both teams."""
        events = []

        # Process team A
        for agent in team_a.agents:
            event = self._run_agent_step(agent, team_a, max_steps)
            if event:
                events.append({"team": team_a.name, "agent": agent.role.value, **event})

        # Process team B
        for agent in team_b.agents:
            event = self._run_agent_step(agent, team_b, max_steps)
            if event:
                events.append({"team": team_b.name, "agent": agent.role.value, **event})

        return events

    def _run_agent_step(
        self,
        agent: SwarmAgent,
        team: SwarmTeam,
        max_steps: int,
    ) -> Optional[dict]:
        """Run a single agent step."""
        try:
            # Generate response from agent
            response = self.backend.generate(
                agent.model,
                agent.messages[-1]["content"],
            )

            # Record the response
            agent.add_message("assistant", response.text)
            agent.add_contribution(response.text[:200])

            return {
                "content": response.text[:500],
                "tokens": response.tokens_out,
                "latency": response.latency_s,
            }
        except Exception as e:
            log.error(f"Error in agent step for {agent.model}: {e}")
            return {"error": str(e)}

    def _check_task_completion(self, team: SwarmTeam) -> bool:
        """Check if team has completed the task (simplified heuristic)."""
        # In production, this would use actual task evaluation
        total_contributions = sum(len(a.contributions) for a in team.agents)
        return total_contributions >= len(team.agents) * 2

    def _evaluate_completion(self, team: SwarmTeam, task: str) -> float:
        """Evaluate task completion score (simplified heuristic)."""
        # In production, this would use actual evaluation against task criteria
        total_messages = sum(len(a.messages) for a in team.agents)
        base_score = min(1.0, total_messages / (len(team.agents) * 5))

        # Add randomness to simulate evaluation variance
        import random
        variance = random.uniform(-0.1, 0.1)
        return round(max(0.0, min(1.0, base_score + variance)), 3)

    def get_battle_statistics(self) -> dict[str, Any]:
        """Get statistics from all battles."""
        if not self.battle_history:
            return {}

        team_wins: dict[str, int] = {}
        total_duration = 0.0

        for battle in self.battle_history:
            if battle.winner != "draw":
                team_wins[battle.winner] = team_wins.get(battle.winner, 0) + 1
            total_duration += battle.duration_s

        return {
            "total_battles": len(self.battle_history),
            "team_wins": team_wins,
            "average_duration_s": round(total_duration / len(self.battle_history), 2),
        }


def example_2v2_setup() -> tuple[SwarmTeam, SwarmTeam]:
    """Example setup for a 2v2 swarm battle."""
    # Team A: Qwen-Coder (writes code) + Phi-4 (writes tests)
    team_a_config = {
        "qwen-coder:latest": AgentRole.CODER,
        "phi-4:latest": AgentRole.TESTER,
    }

    # Team B: Llama-3.3 (writes code) + Mistral (writes tests)
    team_b_config = {
        "llama-3.3:latest": AgentRole.CODER,
        "mistral:latest": AgentRole.TESTER,
    }

    return team_a_config, team_b_config


def example_3v3_setup() -> tuple[SwarmTeam, SwarmTeam]:
    """Example setup for a 3v3 swarm battle."""
    # Team A: Coder + Tester + Reviewer
    team_a_config = {
        "qwen-coder:latest": AgentRole.CODER,
        "phi-4:latest": AgentRole.TESTER,
        "deepseek-coder:latest": AgentRole.REVIEWER,
    }

    # Team B: Coder + Tester + Planner
    team_b_config = {
        "llama-3.3:latest": AgentRole.CODER,
        "mistral:latest": AgentRole.TESTER,
        "codellama:latest": AgentRole.PLANNER,
    }

    return team_a_config, team_b_config
