"""Additional tests for cli/agents.py to cover missing lines."""
from __future__ import annotations
import json
import unittest.mock as mock
import pytest


class TestAnonymize:
    def test_replaces_model_names(self):
        from ollama_arena.cli.agents import _anonymize
        mapping = {"llama3:8b": "Councilor A", "phi3:mini": "Councilor B"}
        text = "llama3:8b said that phi3:mini was wrong"
        result = _anonymize(text, mapping)
        assert "Councilor A" in result
        assert "Councilor B" in result
        assert "llama3:8b" not in result
        assert "phi3:mini" not in result

    def test_empty_mapping(self):
        from ollama_arena.cli.agents import _anonymize
        result = _anonymize("original text", {})
        assert result == "original text"

    def test_no_match(self):
        from ollama_arena.cli.agents import _anonymize
        result = _anonymize("hello world", {"other": "Councilor X"})
        assert result == "hello world"

    def test_prefix_name_does_not_corrupt_longer_name(self):
        """Regression test: when one model name is a prefix of another
        (llama3 / llama3.1), replacing shorter names first used to leave
        mangled fragments like 'Councilor A.1' in the output, which both
        breaks de-anonymization in blind scoring and leaks the relationship
        between the two anonymized entities."""
        from ollama_arena.cli.agents import _anonymize
        mapping = {"llama3": "Councilor A", "llama3.1": "Councilor B"}
        text = "I think llama3.1 is better than llama3 at coding."
        result = _anonymize(text, mapping)
        assert result == "I think Councilor B is better than Councilor A at coding."
        assert "llama3" not in result
        assert ".1" not in result


class TestCmdCouncil:
    def _make_args(self, models="model_a,model_b", topic="Test topic", rounds=1, blind=False):
        args = mock.MagicMock()
        args.models = models
        args.topic = topic
        args.rounds = rounds
        args.blind = blind
        args.ollama = "http://localhost:11434"
        args.db = ":memory:"
        args.backend = None
        args.api_key = None
        return args

    def _make_gen_result(self, text="Opinion"):
        from ollama_arena.backends.base import GenResult
        return GenResult(text=text, model="m", tps=5.0, latency_s=0.5)

    def _mock_console(self):
        mock_c = mock.MagicMock()
        mock_c.status.return_value.__enter__ = mock.MagicMock(return_value=None)
        mock_c.status.return_value.__exit__ = mock.MagicMock(return_value=False)
        return mock_c

    def test_single_model_exits(self):
        from ollama_arena.cli.agents import cmd_council
        args = self._make_args(models="only_one")
        mock_c = self._mock_console()
        with mock.patch("ollama_arena.cli.agents._console", return_value=mock_c), \
             mock.patch.dict("sys.modules", {
                 "rich.panel": mock.MagicMock(),
                 "rich.markdown": mock.MagicMock(),
                 "rich.rule": mock.MagicMock(),
             }), pytest.raises(SystemExit):
            cmd_council(args)

    def test_backend_not_alive_exits(self):
        from ollama_arena.cli.agents import cmd_council
        args = self._make_args()
        mock_c = self._mock_console()
        mock_arena = mock.MagicMock()
        mock_arena.client.is_alive.return_value = False
        with mock.patch("ollama_arena.cli.agents._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agents._make_arena", return_value=mock_arena), \
             mock.patch.dict("sys.modules", {
                 "rich.panel": mock.MagicMock(),
                 "rich.markdown": mock.MagicMock(),
                 "rich.rule": mock.MagicMock(),
             }), pytest.raises(SystemExit):
            cmd_council(args)

    def test_basic_council_one_round(self):
        from ollama_arena.cli.agents import cmd_council
        args = self._make_args(models="a,b", rounds=1)
        mock_c = self._mock_console()
        mock_arena = mock.MagicMock()
        mock_arena.client.is_alive.return_value = True
        mock_arena.client.generate.return_value = self._make_gen_result("Analysis")
        with mock.patch("ollama_arena.cli.agents._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agents._make_arena", return_value=mock_arena), \
             mock.patch.dict("sys.modules", {
                 "rich.panel": mock.MagicMock(),
                 "rich.markdown": mock.MagicMock(),
                 "rich.rule": mock.MagicMock(),
             }):
            cmd_council(args)
        assert mock_arena.client.generate.call_count == 2  # 1 round × 2 models

    def test_council_two_rounds(self):
        from ollama_arena.cli.agents import cmd_council
        args = self._make_args(models="a,b", rounds=2)
        mock_c = self._mock_console()
        mock_arena = mock.MagicMock()
        mock_arena.client.is_alive.return_value = True
        mock_arena.client.generate.return_value = self._make_gen_result()
        with mock.patch("ollama_arena.cli.agents._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agents._make_arena", return_value=mock_arena), \
             mock.patch.dict("sys.modules", {
                 "rich.panel": mock.MagicMock(),
                 "rich.markdown": mock.MagicMock(),
                 "rich.rule": mock.MagicMock(),
             }):
            cmd_council(args)
        # 2 models × 2 rounds = 4 generate calls
        assert mock_arena.client.generate.call_count == 4

    def test_council_blind_mode_two_rounds(self):
        from ollama_arena.cli.agents import cmd_council
        args = self._make_args(models="a,b", rounds=2, blind=True)
        mock_c = self._mock_console()
        mock_arena = mock.MagicMock()
        mock_arena.client.is_alive.return_value = True

        # On round 2, the review prompt will ask for JSON scores
        score_json = json.dumps({"scores": {"Councilor A": 7, "Councilor B": 5}})
        responses = ["Opinion A", "Opinion B", score_json, score_json]
        call_idx = [0]

        def gen_side(*a, **kw):
            from ollama_arena.backends.base import GenResult
            text = responses[min(call_idx[0], len(responses)-1)]
            call_idx[0] += 1
            return GenResult(text=text, model="m", tps=5.0)

        mock_arena.client.generate.side_effect = gen_side

        with mock.patch("ollama_arena.cli.agents._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agents._make_arena", return_value=mock_arena), \
             mock.patch.dict("sys.modules", {
                 "rich.panel": mock.MagicMock(),
                 "rich.markdown": mock.MagicMock(),
                 "rich.rule": mock.MagicMock(),
             }):
            cmd_council(args)
        assert mock_arena.client.generate.call_count > 0

    def test_council_blind_bad_json_no_crash(self):
        from ollama_arena.cli.agents import cmd_council
        args = self._make_args(models="a,b", rounds=2, blind=True)
        mock_c = self._mock_console()
        mock_arena = mock.MagicMock()
        mock_arena.client.is_alive.return_value = True

        def gen_side(*a, **kw):
            from ollama_arena.backends.base import GenResult
            return GenResult(text="not json at all", model="m", tps=5.0)

        mock_arena.client.generate.side_effect = gen_side
        with mock.patch("ollama_arena.cli.agents._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.agents._make_arena", return_value=mock_arena), \
             mock.patch.dict("sys.modules", {
                 "rich.panel": mock.MagicMock(),
                 "rich.markdown": mock.MagicMock(),
                 "rich.rule": mock.MagicMock(),
             }):
            cmd_council(args)  # Should not raise even with bad JSON
