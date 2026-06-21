import pytest
from unittest.mock import patch, MagicMock
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


def test_extract_quant_from_name():
    from ollama_arena.genome.scanner import extract_quant
    assert extract_quant("llama3.1:8b-instruct-q4_K_M") == "q4_K_M"


def test_scanner_offline_fallback():
    """When ollama CLI unavailable, scan_local returns empty list."""
    scanner = OllamaScanner(ollama_url="http://localhost:99999")
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        result = scanner.scan_local()
    assert result == []


def test_get_modelfile_cli_does_not_prefix_match_size():
    """Regression test: size lookup previously used line.startswith(name),
    which matches the wrong model when one name is a prefix of another
    (e.g. 'llama3:8b' is a prefix of 'llama3:8b-instruct'). It must match
    on the exact first column instead.
    """
    scanner = OllamaScanner()
    mock_show = MagicMock()
    mock_show.stdout = "FROM base\n"
    mock_list = MagicMock()
    mock_list.stdout = (
        "NAME                    ID   SIZE    MODIFIED\n"
        "llama3:8b-instruct      abc  9.0 GB  1 week\n"
        "llama3:8b               def  4.7 GB  1 week\n"
    )
    with patch("subprocess.run", side_effect=[mock_show, mock_list]):
        content, size_gb = scanner._get_modelfile_cli("llama3:8b")
    assert size_gb == pytest.approx(4.7)


def test_get_list_api_skips_malformed_entry_keeps_rest():
    """Regression test: a single malformed model entry (missing 'name') in
    the Ollama API response previously raised inside the list comprehension
    and the broad except discarded the entire result, including valid
    entries alongside the bad one.
    """
    scanner = OllamaScanner()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "models": [{"notname": "x"}, {"name": "good:model"}]
    }
    mock_resp.raise_for_status = MagicMock()
    with patch("requests.get", return_value=mock_resp):
        names = scanner._get_list_api()
    assert names == ["good:model"]
