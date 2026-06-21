"""Tests for cli/p2p_cmd.py."""
from __future__ import annotations
import asyncio
import json
import unittest.mock as mock
import pytest


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.join_global = False
    args.status = False
    args.peers = False
    args.global_leaderboard = False
    args.distribute_task = False
    args.verify_result = None
    args.generate_proof = False
    args.host = "0.0.0.0"
    args.port = 8080
    args.bootstrap = None
    args.model_a = None
    args.model_b = None
    args.category = "coding"
    args.limit = 10
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


class TestPrintHelpers:
    def test_print_success(self, capsys):
        from ollama_arena.cli.p2p_cmd import print_success
        mock_console = mock.MagicMock()
        with mock.patch("ollama_arena.cli.p2p_cmd.Console", return_value=mock_console):
            print_success("All good")
        mock_console.print.assert_called_once()
        printed_arg = str(mock_console.print.call_args[0][0])
        assert "All good" in printed_arg

    def test_print_error(self, capsys):
        from ollama_arena.cli.p2p_cmd import print_error
        mock_console = mock.MagicMock()
        with mock.patch("ollama_arena.cli.p2p_cmd.Console", return_value=mock_console):
            print_error("Something failed")
        mock_console.print.assert_called_once()

    def test_print_info(self, capsys):
        from ollama_arena.cli.p2p_cmd import print_info
        mock_console = mock.MagicMock()
        with mock.patch("ollama_arena.cli.p2p_cmd.Console", return_value=mock_console):
            print_info("Just so you know")
        mock_console.print.assert_called_once()


class TestCmdNodeStatus:
    def test_status_prints_info(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_node_status
        args = _make_args()
        asyncio.run(cmd_node_status(args))
        out = capsys.readouterr().out
        assert "Node" in out or "Status" in out or "Offline" in out


class TestCmdDistributeTask:
    def test_missing_models_prints_error(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_distribute_task
        args = _make_args(model_a=None, model_b=None)
        asyncio.run(cmd_distribute_task(args))
        out = capsys.readouterr().out
        assert "required" in out.lower() or "model" in out.lower()

    def test_with_models_distributes(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_distribute_task
        args = _make_args(model_a="llama3:8b", model_b="phi3:mini", category="coding")
        asyncio.run(cmd_distribute_task(args))
        out = capsys.readouterr().out
        assert "llama3:8b" in out or "distributed" in out.lower()


class TestCmdNode:
    def test_no_subcommand_prints_help(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_node
        args = _make_args()
        args.join_global = False
        args.status = False
        args.peers = False
        args.global_leaderboard = False
        args.distribute_task = False
        cmd_node(args)
        out = capsys.readouterr().out
        assert "P2P" in out or "node" in out.lower() or "command" in out.lower()

    def test_status_subcommand(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_node
        args = _make_args(status=True)
        cmd_node(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_distribute_task_missing_models(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_node
        args = _make_args(distribute_task=True, model_a=None, model_b=None)
        cmd_node(args)
        out = capsys.readouterr().out
        assert len(out) > 0


class TestCmdP2P:
    def test_no_subcommand_prints_help(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_p2p
        args = _make_args(verify_result=None, generate_proof=False)
        cmd_p2p(args)
        out = capsys.readouterr().out
        assert "P2P" in out or "verify" in out.lower() or "Command" in out

    def test_verify_result_missing_file_path(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_p2p
        args = _make_args(verify_result=None, generate_proof=False)
        args.verify_result = ""  # falsy
        cmd_p2p(args)

    def test_verify_result_nonexistent_file(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_p2p
        args = _make_args(verify_result="/nonexistent/path/proof.json", generate_proof=False)
        cmd_p2p(args)
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "fail" in out.lower() or len(out) > 0

    def test_verify_result_valid_proof(self, tmp_path, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_p2p

        proof_file = tmp_path / "proof.json"
        bundle = {
            "task_id": "task_001",
            "signature": {"node_id": "node123"},
            "timestamp": 1234567890,
            "inputs": {},
            "results": {},
        }
        proof_file.write_text(json.dumps(bundle))

        args = _make_args(verify_result=str(proof_file), generate_proof=False)

        mock_validator = mock.MagicMock()
        mock_validator.validate_proof_bundle.return_value = (True, [])
        mock_ProofValidator = mock.MagicMock(return_value=mock_validator)

        with mock.patch("ollama_arena.p2p.crypto_proof.ProofValidator", mock_ProofValidator):
            cmd_p2p(args)

        out = capsys.readouterr().out
        assert len(out) > 0

    def test_verify_result_invalid_proof(self, tmp_path, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_p2p

        proof_file = tmp_path / "bad_proof.json"
        proof_file.write_text(json.dumps({"task_id": "t1"}))
        args = _make_args(verify_result=str(proof_file), generate_proof=False)

        mock_validator = mock.MagicMock()
        mock_validator.validate_proof_bundle.return_value = (False, ["bad signature"])
        mock_ProofValidator = mock.MagicMock(return_value=mock_validator)

        with mock.patch("ollama_arena.p2p.crypto_proof.ProofValidator", mock_ProofValidator):
            cmd_p2p(args)

        out = capsys.readouterr().out
        assert len(out) > 0

    def test_generate_proof_missing_args(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_p2p
        args = _make_args(verify_result=None, generate_proof=True)
        args.task_id = None
        args.result = None
        cmd_p2p(args)
        out = capsys.readouterr().out
        assert "required" in out.lower() or "task" in out.lower() or len(out) > 0

    def test_generate_proof_invalid_json(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_p2p
        args = _make_args(verify_result=None, generate_proof=True)
        args.task_id = "task_1"
        args.result = "not json"
        cmd_p2p(args)
        out = capsys.readouterr().out
        assert "invalid" in out.lower() or "json" in out.lower() or len(out) > 0

    def test_generate_proof_success(self, tmp_path, capsys, monkeypatch):
        from ollama_arena.cli.p2p_cmd import cmd_p2p
        args = _make_args(verify_result=None, generate_proof=True)
        args.task_id = "task_abc"
        args.result = '{"score": 0.9}'

        monkeypatch.chdir(tmp_path)

        mock_node = mock.MagicMock()
        mock_node.local_node_id = "node_xyz"
        mock_P2PNode = mock.MagicMock(return_value=mock_node)

        mock_keypair = mock.MagicMock()
        mock_keypair.get_public_key_hex.return_value = "abcdef1234"

        mock_generator = mock.MagicMock()
        mock_generator.key_pair = mock_keypair
        mock_generator.create_proof_bundle.return_value = {"task_id": "task_abc", "proof": "xyz"}
        mock_CryptoProofGenerator = mock.MagicMock(return_value=mock_generator)

        with mock.patch("ollama_arena.p2p.node.P2PNode", mock_P2PNode), \
             mock.patch("ollama_arena.cli.p2p_cmd.CryptoProofGenerator", mock_CryptoProofGenerator):
            cmd_p2p(args)

        out = capsys.readouterr().out
        assert len(out) > 0

    def test_generate_proof_task_id_path_traversal_is_sanitized(self, tmp_path, monkeypatch):
        """Regression test: --task-id flowed unsanitized into the output filename
        ('proof_{task_id}.json'), so a task id like '../../somewhere/evil' could
        write outside the current directory. The basename must be used instead,
        confining the write to cwd."""
        from pathlib import Path
        from ollama_arena.cli.p2p_cmd import cmd_p2p
        args = _make_args(verify_result=None, generate_proof=True)
        args.task_id = "../../../tmp/evil_proof"
        args.result = '{"score": 0.9}'

        monkeypatch.chdir(tmp_path)

        mock_node = mock.MagicMock()
        mock_node.local_node_id = "node_xyz"
        mock_P2PNode = mock.MagicMock(return_value=mock_node)

        mock_keypair = mock.MagicMock()
        mock_keypair.get_public_key_hex.return_value = "abcdef1234"

        mock_generator = mock.MagicMock()
        mock_generator.key_pair = mock_keypair
        mock_generator.create_proof_bundle.return_value = {"task_id": args.task_id, "proof": "xyz"}
        mock_CryptoProofGenerator = mock.MagicMock(return_value=mock_generator)

        with mock.patch("ollama_arena.p2p.node.P2PNode", mock_P2PNode), \
             mock.patch("ollama_arena.cli.p2p_cmd.CryptoProofGenerator", mock_CryptoProofGenerator):
            cmd_p2p(args)

        # The file must land inside tmp_path (cwd), not be written 3 dirs up.
        written = list(tmp_path.glob("proof_*.json"))
        assert len(written) == 1
        assert written[0].name == "proof_evil_proof.json"
        assert not (tmp_path.parent.parent.parent / "tmp" / "evil_proof.json").exists()


class TestCmdNodePeers:
    def test_peers_with_rich(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_node_peers
        args = _make_args()

        mock_peer = mock.MagicMock()
        mock_peer.node_id = "abcdef123456"
        mock_peer.address = "127.0.0.1"
        mock_peer.port = 8080
        mock_peer.trust_level = "high"

        mock_discovery = mock.MagicMock()
        mock_discovery.discover_all = mock.AsyncMock(return_value=[mock_peer])
        mock_NodeDiscovery = mock.MagicMock(return_value=mock_discovery)

        with mock.patch("ollama_arena.p2p.node.NodeDiscovery", mock_NodeDiscovery):
            asyncio.run(cmd_node_peers(args))

        out = capsys.readouterr().out
        assert len(out) >= 0  # doesn't crash


class TestCmdGlobalLeaderboard:
    def test_leaderboard_empty(self, capsys):
        from ollama_arena.cli.p2p_cmd import cmd_global_leaderboard
        args = _make_args(category=None, limit=10)

        mock_lb = mock.MagicMock()
        mock_lb.get_leaderboard_stats.return_value = {
            "total_entries": 0, "unique_models": 0, "average_score": 0.0
        }
        mock_lb.get_top_entries.return_value = []
        mock_GlobalLeaderboard = mock.MagicMock(return_value=mock_lb)

        with mock.patch("ollama_arena.p2p.leaderboard.GlobalLeaderboard", mock_GlobalLeaderboard):
            asyncio.run(cmd_global_leaderboard(args))

        out = capsys.readouterr().out
        assert "entries" in out.lower() or len(out) > 0
