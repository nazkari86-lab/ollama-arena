import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ollama_arena.cli.agents import (
    cmd_council,
    cmd_optimize_prompt,
    cmd_resolve_issue,
    cmd_review_pr,
    _findings_to_sarif,
    _parse_review_findings,
    _build_blind_mapping,
)
from ollama_arena.genome.scanner import extract_quant


def test_extract_quant_from_model_name():
    assert extract_quant("llama3.1:8b-instruct-q4_K_M") == "q4_K_M"
    assert extract_quant("qwen2.5:7b-instruct-fp16") == "fp16"


def test_blind_mapping_anonymizes_models():
    mapping = _build_blind_mapping(["alpha:7b", "beta:7b", "gamma:7b"])
    assert mapping["alpha:7b"] == "Councilor A"
    assert mapping["beta:7b"] == "Councilor B"


def test_parse_review_findings_detects_severity():
    text = "- critical: SQL injection in login\n- minor style nit\n- bug in loop"
    findings = _parse_review_findings(text, "test-model")
    levels = {f["level"] for f in findings}
    assert "error" in levels
    assert "warning" in levels


def test_findings_to_sarif_schema():
    findings = [{"ruleId": "r1", "level": "warning", "message": {"text": "issue"}}]
    sarif = _findings_to_sarif(findings, "arena-test")
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["level"] == "warning"


def test_resolve_issue_writes_json_report(tmp_path):
    args = argparse.Namespace(
        model="test-model",
        issue="Fix the bug in foo.py",
        max_steps=2,
        report=str(tmp_path / "report.json"),
        ollama="http://localhost:11434",
        backend=None,
        api_key=None,
        db="arena.db",
    )
    fake_res = MagicMock()
    fake_res.finish_reason = "stop"
    fake_res.text = "Fixed foo.py"
    fake_res.agent_trace = [{"step": 1, "tool_calls": [{"function": {"name": "read_file"}}]}]

    fake_arena = MagicMock()
    fake_arena.client.is_alive.return_value = True
    fake_arena.mcp.use_mock = True

    with patch("ollama_arena.cli.agents._make_arena", return_value=fake_arena), \
         patch("ollama_arena.agent_loop.run_agent_sync", return_value=fake_res), \
         patch("ollama_arena.cli.agents._console") as mock_console:
        mock_console.return_value.print = MagicMock()
        mock_console.return_value.status.return_value.__enter__ = MagicMock(return_value=None)
        mock_console.return_value.status.return_value.__exit__ = MagicMock(return_value=None)
        cmd_resolve_issue(args)

    report = json.loads(Path(args.report).read_text())
    assert report["model"] == "test-model"
    assert report["result"] == "Fixed foo.py"
    assert report["tool_steps"][0]["tools"] == ["read_file"]


def test_review_pr_sarif_output(tmp_path):
    args = argparse.Namespace(
        models="reviewer:7b",
        sarif=str(tmp_path / "out.sarif"),
        files=None,
        ollama="http://localhost:11434",
        backend=None,
        api_key=None,
        db="arena.db",
    )
    fake_arena = MagicMock()
    fake_res = MagicMock()
    fake_res.text = "- critical security flaw in auth\n- warning: missing test"
    fake_arena.client.generate.return_value = fake_res

    with patch("ollama_arena.cli.agents.subprocess.run") as mock_run, \
         patch("ollama_arena.cli.agents._make_arena", return_value=fake_arena), \
         patch("ollama_arena.cli.agents._console") as mock_console:
        mock_run.return_value.stdout = "diff line"
        mock_console.return_value.print = MagicMock()
        mock_console.return_value.status.return_value.__enter__ = MagicMock(return_value=None)
        mock_console.return_value.status.return_value.__exit__ = MagicMock(return_value=None)
        cmd_review_pr(args)

    sarif = json.loads(Path(args.sarif).read_text())
    assert len(sarif["runs"][0]["results"]) >= 2


def test_optimize_prompt_uses_genome_and_failures():
    args = argparse.Namespace(
        model="llama3.1:8b-instruct",
        category="coding",
        ollama="http://localhost:11434",
        backend=None,
        api_key=None,
        db="arena.db",
    )
    fake_arena = MagicMock()
    fake_arena.client.is_alive.return_value = True
    fake_arena.client.generate.return_value = MagicMock(ok=True, text="Optimized prompt")

    with patch("ollama_arena.cli.agents._make_arena", return_value=fake_arena), \
         patch("ollama_arena.finetune.analyzer.analyze_task_failures", return_value=[]), \
         patch("ollama_arena.cli.agents._console") as mock_console:
        mock_console.return_value.print = MagicMock()
        cmd_optimize_prompt(args)
        assert fake_arena.client.generate.called
