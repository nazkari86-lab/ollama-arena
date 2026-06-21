"""Tests for cli/agentic.py."""
from __future__ import annotations
import json
import sys
import unittest.mock as mock
import pytest


def _mc():
    c = mock.MagicMock()
    c.status.return_value.__enter__ = mock.MagicMock(return_value=None)
    c.status.return_value.__exit__ = mock.MagicMock(return_value=False)
    return c


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.db = ":memory:"
    args.ollama = "http://localhost:11434"
    args.backend = None
    args.api_key = None
    args.output = None
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def _make_arena_mock(is_alive=True):
    arena = mock.MagicMock()
    arena.client.is_alive.return_value = is_alive
    arena.client.name = "ollama"
    return arena


class TestCmdSandbox:
    def _make_sandbox_args(self, action="create", **kwargs):
        args = _make_args()
        args.sandbox_action = action
        args.sandbox_id = "test_sandbox"
        args.cpu_limit = 1.0
        args.memory = "256m"
        args.timeout = 30
        args.no_network_isolation = False
        args.task = "echo hello"
        args.backend = "docker"
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def test_create_success(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("create")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_instance = mock.MagicMock()
        mock_instance.status.value = "running"
        mock_manager = mock.MagicMock()
        mock_manager.create_sandbox.return_value = mock_instance

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"):
            cmd_sandbox(args)

        mock_manager.create_sandbox.assert_called_once()
        mock_c.print.assert_called()

    def test_create_failure(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("create")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_instance = mock.MagicMock()
        mock_instance.status.value = "failed"
        mock_instance.metadata = {"error": "Docker not found"}
        mock_manager = mock.MagicMock()
        mock_manager.create_sandbox.return_value = mock_instance

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"), \
             pytest.raises(SystemExit):
            cmd_sandbox(args)

    def test_execute_success(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("execute")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_result = mock.MagicMock()
        mock_result.success = True
        mock_result.output = "Hello, World!"
        mock_manager = mock.MagicMock()
        mock_manager.execute_task.return_value = mock_result

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"):
            cmd_sandbox(args)

        mock_manager.execute_task.assert_called_once()

    def test_execute_failure(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("execute")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_result = mock.MagicMock()
        mock_result.success = False
        mock_result.error = "Command failed"
        mock_manager = mock.MagicMock()
        mock_manager.execute_task.return_value = mock_result

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"), \
             pytest.raises(SystemExit):
            cmd_sandbox(args)

    def test_stop_success(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("stop")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_manager = mock.MagicMock()
        mock_manager.stop_sandbox.return_value = True

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"):
            cmd_sandbox(args)

        mock_manager.stop_sandbox.assert_called_once()

    def test_stop_failure(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("stop")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_manager = mock.MagicMock()
        mock_manager.stop_sandbox.return_value = False

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"), \
             pytest.raises(SystemExit):
            cmd_sandbox(args)

    def test_list_sandboxes(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("list")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_status = mock.MagicMock()
        mock_status.value = "running"
        mock_manager = mock.MagicMock()
        mock_manager.list_sandboxes.return_value = ["sb1", "sb2"]
        mock_manager.get_sandbox_status.return_value = mock_status

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"):
            cmd_sandbox(args)

    def test_cleanup_specific(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("cleanup", sandbox_id="sb1")
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_manager = mock.MagicMock()
        mock_manager.cleanup_sandbox.return_value = True

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"):
            cmd_sandbox(args)

        mock_manager.cleanup_sandbox.assert_called_once_with("sb1")

    def test_cleanup_all(self):
        from ollama_arena.cli.agentic import cmd_sandbox
        args = self._make_sandbox_args("cleanup")
        args.sandbox_id = None  # No specific sandbox
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_manager = mock.MagicMock()

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxManager", return_value=mock_manager), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxConfig"), \
             mock.patch("ollama_arena.agentic.sandbox.SandboxBackend"):
            cmd_sandbox(args)

        mock_manager.cleanup_all.assert_called_once()


class TestCmdSwarm:
    def _make_swarm_args(self, mode="2v2", **kwargs):
        args = _make_args()
        args.mode = mode
        args.task = "solve this problem"
        args.rounds = 3
        args.max_steps = 10
        args.team_a = None
        args.team_b = None
        args.output = None
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def _make_swarm_result(self):
        r = mock.MagicMock()
        r.winner = "Team A"
        r.team_a_name = "Team A"
        r.team_b_name = "Team B"
        r.team_a_score = 2
        r.team_b_score = 1
        r.duration_s = 5.0
        r.rounds_completed = 3
        r.collaboration_metrics = {}
        r.team_a_details = {}
        r.team_b_details = {}
        return r

    def test_backend_not_alive_exits(self):
        from ollama_arena.cli.agentic import cmd_swarm
        args = self._make_swarm_args()
        mock_c = _mc()
        arena = _make_arena_mock(is_alive=False)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}), \
             pytest.raises(SystemExit):
            cmd_swarm(args)

    def test_invalid_mode_exits(self):
        from ollama_arena.cli.agentic import cmd_swarm
        args = self._make_swarm_args(mode="invalid")
        mock_c = _mc()
        arena = _make_arena_mock()

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.swarm.SwarmBattle"), \
             mock.patch("ollama_arena.agentic.swarm.SwarmTeam"), \
             mock.patch("ollama_arena.agentic.swarm.example_2v2_setup", return_value=({}, {})), \
             mock.patch("ollama_arena.agentic.swarm.example_3v3_setup", return_value=({}, {})), \
             mock.patch("ollama_arena.agentic.swarm.AgentRole"), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}), \
             pytest.raises(SystemExit):
            cmd_swarm(args)

    def test_team_a_malformed_spec_exits_cleanly(self):
        """--team-a with no colon separator must produce a clean CLI error and
        exit 1, not an uncaught ValueError from dict(item.split(':') ...)."""
        from ollama_arena.cli.agentic import cmd_swarm
        args = self._make_swarm_args(mode="2v2", team_a="model_with_no_role")
        mock_c = _mc()
        arena = _make_arena_mock()

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.swarm.example_2v2_setup", return_value=({}, {})), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}), \
             pytest.raises(SystemExit) as exc_info:
            cmd_swarm(args)

        assert exc_info.value.code == 1
        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "Invalid team config" in printed

    def test_team_a_invalid_role_exits_cleanly(self):
        """--team-a with a role string that isn't a real AgentRole must produce
        a clean CLI error and exit 1, not an uncaught ValueError."""
        from ollama_arena.cli.agentic import cmd_swarm
        args = self._make_swarm_args(mode="2v2", team_a="llama3:not_a_real_role")
        mock_c = _mc()
        arena = _make_arena_mock()

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.swarm.example_2v2_setup", return_value=({}, {})), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}), \
             pytest.raises(SystemExit) as exc_info:
            cmd_swarm(args)

        assert exc_info.value.code == 1
        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "Invalid role" in printed

    def test_team_a_model_name_with_colon_parses_role_correctly(self):
        """Model names like 'llama3.1:8b' contain a colon themselves; the role
        parser must split on the *last* colon only (maxsplit) so the model id
        survives intact and only the trailing role token is interpreted."""
        from ollama_arena.cli.agentic import cmd_swarm
        from ollama_arena.agentic.swarm import AgentRole
        args = self._make_swarm_args(mode="2v2", team_a="llama3.1:8b:coder")
        mock_c = _mc()
        arena = _make_arena_mock()
        swarm_result = self._make_swarm_result()

        mock_battle = mock.MagicMock()
        mock_battle.run_battle.return_value = swarm_result
        mock_SwarmBattle = mock.MagicMock(return_value=mock_battle)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.swarm.SwarmBattle", mock_SwarmBattle), \
             mock.patch("ollama_arena.agentic.swarm.SwarmTeam"), \
             mock.patch("ollama_arena.agentic.swarm.example_2v2_setup", return_value=({}, {})), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}):
            cmd_swarm(args)

        team_a_cfg = mock_battle.create_team.call_args_list[0][0][1]
        assert team_a_cfg == {"llama3.1:8b": AgentRole.CODER}

    def test_2v2_mode(self):
        from ollama_arena.cli.agentic import cmd_swarm
        args = self._make_swarm_args(mode="2v2")
        mock_c = _mc()
        arena = _make_arena_mock()
        swarm_result = self._make_swarm_result()

        team_a_cfg = {"llama3:8b": "attacker", "phi3:mini": "defender"}
        team_b_cfg = {"mistral:7b": "attacker", "gemma:2b": "defender"}

        mock_battle = mock.MagicMock()
        mock_battle.run_battle.return_value = swarm_result
        mock_SwarmBattle = mock.MagicMock(return_value=mock_battle)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.swarm.SwarmBattle", mock_SwarmBattle), \
             mock.patch("ollama_arena.agentic.swarm.SwarmTeam"), \
             mock.patch("ollama_arena.agentic.swarm.example_2v2_setup", return_value=(team_a_cfg, team_b_cfg)), \
             mock.patch("ollama_arena.agentic.swarm.example_3v3_setup", return_value=(team_a_cfg, team_b_cfg)), \
             mock.patch("ollama_arena.agentic.swarm.AgentRole"), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}):
            cmd_swarm(args)

        mock_battle.run_battle.assert_called_once()

    def test_3v3_mode(self):
        from ollama_arena.cli.agentic import cmd_swarm
        args = self._make_swarm_args(mode="3v3")
        mock_c = _mc()
        arena = _make_arena_mock()
        swarm_result = self._make_swarm_result()

        team_cfg = {"m1": "a", "m2": "b", "m3": "c"}
        mock_battle = mock.MagicMock()
        mock_battle.run_battle.return_value = swarm_result
        mock_SwarmBattle = mock.MagicMock(return_value=mock_battle)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.swarm.SwarmBattle", mock_SwarmBattle), \
             mock.patch("ollama_arena.agentic.swarm.SwarmTeam"), \
             mock.patch("ollama_arena.agentic.swarm.example_2v2_setup", return_value=(team_cfg, team_cfg)), \
             mock.patch("ollama_arena.agentic.swarm.example_3v3_setup", return_value=(team_cfg, team_cfg)), \
             mock.patch("ollama_arena.agentic.swarm.AgentRole"), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}):
            cmd_swarm(args)

    def test_swarm_with_output_file(self, tmp_path):
        from ollama_arena.cli.agentic import cmd_swarm
        args = self._make_swarm_args(mode="2v2", output=str(tmp_path / "result.json"))
        mock_c = _mc()
        arena = _make_arena_mock()
        swarm_result = self._make_swarm_result()

        team_cfg = {"m1": "a", "m2": "b"}
        mock_battle = mock.MagicMock()
        mock_battle.run_battle.return_value = swarm_result
        mock_SwarmBattle = mock.MagicMock(return_value=mock_battle)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.swarm.SwarmBattle", mock_SwarmBattle), \
             mock.patch("ollama_arena.agentic.swarm.SwarmTeam"), \
             mock.patch("ollama_arena.agentic.swarm.example_2v2_setup", return_value=(team_cfg, team_cfg)), \
             mock.patch("ollama_arena.agentic.swarm.example_3v3_setup", return_value=(team_cfg, team_cfg)), \
             mock.patch("ollama_arena.agentic.swarm.AgentRole"), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}):
            cmd_swarm(args)

        assert (tmp_path / "result.json").exists()


class TestCmdRedteam:
    def _make_redteam_args(self, **kwargs):
        args = _make_args()
        args.attacker = "llama3:8b"
        args.defender = "phi3:mini"
        args.context = "AI safety evaluation"
        args.rounds = 3
        args.severity = "low,medium,high"
        args.no_adaptive = False
        args.timeout = 30
        args.output = None
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def _make_redteam_result(self):
        r = mock.MagicMock()
        r.overall_winner = "defender"
        r.attacker_score = 0.3
        r.defender_score = 0.7
        r.attacker_wins = 1
        r.defender_wins = 2
        r.total_rounds = 3
        r.duration_s = 8.0
        r.attacker_model = "llama3:8b"
        r.defender_model = "phi3:mini"
        r.attack_breakdown = {}
        r.defense_metrics = {
            "detection_rate": 0.8, "blocked": 2, "detected": 1, "failed": 0, "vulnerable": 0
        }
        return r

    def test_backend_not_alive_exits(self):
        from ollama_arena.cli.agentic import cmd_redteam
        args = self._make_redteam_args()
        mock_c = _mc()
        arena = _make_arena_mock(is_alive=False)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}), \
             pytest.raises(SystemExit):
            cmd_redteam(args)

    def test_basic_redteam(self):
        from ollama_arena.cli.agentic import cmd_redteam
        args = self._make_redteam_args()
        mock_c = _mc()
        arena = _make_arena_mock()
        redteam_result = self._make_redteam_result()

        mock_arena_session = mock.MagicMock()
        mock_arena_session.run_arena.return_value = redteam_result
        mock_RedTeamArena = mock.MagicMock(return_value=mock_arena_session)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.redteam.RedTeamArena", mock_RedTeamArena), \
             mock.patch("ollama_arena.agentic.redteam.RedTeamConfig"), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}):
            cmd_redteam(args)

        mock_arena_session.run_arena.assert_called_once()
        mock_c.print.assert_called()

    def test_redteam_with_output(self, tmp_path):
        from ollama_arena.cli.agentic import cmd_redteam
        args = self._make_redteam_args(output=str(tmp_path / "redteam.json"))
        mock_c = _mc()
        arena = _make_arena_mock()
        redteam_result = self._make_redteam_result()

        mock_arena_session = mock.MagicMock()
        mock_arena_session.run_arena.return_value = redteam_result
        mock_RedTeamArena = mock.MagicMock(return_value=mock_arena_session)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agentic._make_arena", return_value=arena), \
             mock.patch("ollama_arena.agentic.redteam.RedTeamArena", mock_RedTeamArena), \
             mock.patch("ollama_arena.agentic.redteam.RedTeamConfig"), \
             mock.patch.dict("sys.modules", {"rich.panel": mock.MagicMock()}):
            cmd_redteam(args)

        assert (tmp_path / "redteam.json").exists()


class TestCmdLongHorizon:
    def _make_lh_args(self, action="list", task_id=None, **kwargs):
        args = _make_args()
        args.lh_action = action
        args.task_id = task_id
        args.checkpoint_dir = "/tmp/checkpoints"
        args.progress = 50.0
        args.step_description = "Step 1"
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def _make_task_def(self):
        return {
            "id": "task_001", "role": "developer", "difficulty": "medium",
            "estimated_hours": 2, "checkpoints": ["checkpoint_1", "checkpoint_2"],
        }

    def test_list_tasks(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        args = self._make_lh_args("list")
        mock_c = _mc()
        task_def = self._make_task_def()

        mock_manager = mock.MagicMock()
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", [task_def]), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator", mock.MagicMock()):
            cmd_long_horizon(args)

        mock_c.print.assert_called()

    def test_start_task_not_found(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        args = self._make_lh_args("start", task_id="nonexistent")
        mock_c = _mc()

        mock_manager = mock.MagicMock()
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", [self._make_task_def()]), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator"), \
             pytest.raises(SystemExit):
            cmd_long_horizon(args)

    def test_start_task_found(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        task_def = self._make_task_def()
        args = self._make_lh_args("start", task_id="task_001")
        mock_c = _mc()

        mock_task = mock.MagicMock()
        mock_task.id = "task_001"
        mock_task.estimated_duration_hours = 2
        mock_manager = mock.MagicMock()
        mock_manager.create_task.return_value = mock_task
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", [task_def]), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator"):
            cmd_long_horizon(args)

        mock_manager.create_task.assert_called_once()
        mock_manager.start_task.assert_called_once_with("task_001")

    def test_pause_task_success(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        args = self._make_lh_args("pause", task_id="task_001")
        mock_c = _mc()

        mock_manager = mock.MagicMock()
        mock_manager.pause_task.return_value = True
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", []), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator"):
            cmd_long_horizon(args)

    def test_pause_task_failure(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        args = self._make_lh_args("pause", task_id="task_001")
        mock_c = _mc()

        mock_manager = mock.MagicMock()
        mock_manager.pause_task.return_value = False
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", []), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator"), \
             pytest.raises(SystemExit):
            cmd_long_horizon(args)

    def test_resume_task(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        args = self._make_lh_args("resume", task_id="task_001")
        mock_c = _mc()

        mock_manager = mock.MagicMock()
        mock_manager.resume_task.return_value = True
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", []), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator"):
            cmd_long_horizon(args)

    def test_status_task_not_found(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        args = self._make_lh_args("status", task_id="task_999")
        mock_c = _mc()

        mock_manager = mock.MagicMock()
        mock_manager.get_task.return_value = None
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", []), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator"), \
             pytest.raises(SystemExit):
            cmd_long_horizon(args)

    def test_status_task_found(self):
        from ollama_arena.cli.agentic import cmd_long_horizon
        args = self._make_lh_args("status", task_id="task_001")
        mock_c = _mc()

        mock_task = mock.MagicMock()
        mock_task.id = "task_001"
        mock_task.status.value = "running"
        mock_task.current_progress = 0.5
        mock_task.checkpoints = ["cp1"]
        mock_task.intermediate_results = []
        mock_task.started_at = None
        mock_manager = mock.MagicMock()
        mock_manager.get_task.return_value = mock_task
        mock_LHManager = mock.MagicMock(return_value=mock_manager)

        with mock.patch("ollama_arena.cli.agentic._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.long_horizon.LongHorizonTaskManager", mock_LHManager), \
             mock.patch("ollama_arena.tasks.long_horizon.LONG_HORIZON_TASKS", []), \
             mock.patch("ollama_arena.tasks.long_horizon.default_task_evaluator"):
            cmd_long_horizon(args)

        mock_c.print.assert_called()
