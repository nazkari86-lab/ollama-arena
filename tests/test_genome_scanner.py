import pytest
from unittest.mock import patch
from ollama_arena.genome.scanner import OllamaScanner, parse_modelfile


def test_parse_modelfile_from_line():
    mf = "FROM llama3.1:8b-instruct\nPARAMETER num_ctx 4096\n"
    result = parse_modelfile(mf)
    assert result["from"] == "llama3.1:8b-instruct"
    assert result["parameters"]["num_ctx"] == "4096"


def test_parse_modelfile_no_from():
    result = parse_modelfile("PARAMETER temperature 0.7\n")
    assert result["from"] is None


def test_scanner_parse_list_output():
    raw = (
        "NAME                    ID              SIZE    MODIFIED\n"
        "llama3.1:8b             365c0bd3c000    4.7 GB  2 weeks ago\n"
        "qwen2.5:7b-instruct     845dbda0ea48    4.4 GB  3 weeks ago\n"
    )
    scanner = OllamaScanner()
    names = scanner._parse_list_output(raw)
    assert "llama3.1:8b" in names
    assert "qwen2.5:7b-instruct" in names


def test_scanner_offline_fallback():
    """When ollama CLI unavailable, scan_local returns empty list."""
    scanner = OllamaScanner(ollama_url="http://localhost:99999")
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        result = scanner.scan_local()
    assert result == []
