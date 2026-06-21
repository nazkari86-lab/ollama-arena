"""Extended tests for genome/scanner.py to reach >60% coverage."""
from __future__ import annotations
import subprocess
import unittest.mock as mock
import pytest

from ollama_arena.genome.scanner import (
    OllamaScanner, LocalModelInfo, extract_quant, parse_modelfile,
    _parse_size, _size_bytes_to_gb,
)


# ─── extract_quant ───────────────────────────────────────────────────────────

class TestExtractQuant:
    def test_empty_string(self):
        assert extract_quant("") == ""

    def test_q4_k_m(self):
        assert extract_quant("llama3.1:8b-q4_K_M") == "q4_K_M"

    def test_fp16(self):
        result = extract_quant("model:fp16")
        assert result.lower() == "fp16"

    def test_f16(self):
        result = extract_quant("model:f16")
        assert result.lower() == "f16"

    def test_no_quant(self):
        result = extract_quant("llama3.1:8b-instruct")
        assert result == ""

    def test_q8_0(self):
        result = extract_quant("phi3:q8_0")
        assert "q8" in result.lower()

    def test_q2_k(self):
        result = extract_quant("mistral:q2_K")
        assert "q2" in result.lower()

    def test_int4(self):
        result = extract_quant("model:int4")
        assert result.lower() in ("int4", "")

    def test_colon_separator(self):
        result = extract_quant("llama3:8b-q4_K_S")
        assert "q4" in result.lower()


# ─── parse_modelfile ─────────────────────────────────────────────────────────

class TestParseModelfile:
    def test_empty(self):
        r = parse_modelfile("")
        assert r["from"] is None
        assert r["parameters"] == {}

    def test_comment_ignored(self):
        r = parse_modelfile("# This is a comment\nFROM base:model\n")
        assert r["from"] == "base:model"

    def test_blank_line_ignored(self):
        r = parse_modelfile("\n\nFROM base\n")
        assert r["from"] == "base"

    def test_parameter_lower_key(self):
        r = parse_modelfile("PARAMETER Temperature 0.7\n")
        assert "temperature" in r["parameters"]
        assert r["parameters"]["temperature"] == "0.7"

    def test_multiple_parameters(self):
        content = "FROM base\nPARAMETER num_ctx 4096\nPARAMETER temperature 0.5\n"
        r = parse_modelfile(content)
        assert r["parameters"]["num_ctx"] == "4096"
        assert r["parameters"]["temperature"] == "0.5"

    def test_parameter_with_spaces_in_value(self):
        r = parse_modelfile("PARAMETER stop <|end|> <|user|>\n")
        assert "stop" in r["parameters"]
        assert "<|end|>" in r["parameters"]["stop"]

    def test_from_only_one_part(self):
        r = parse_modelfile("FROM\n")
        assert r["from"] is None

    def test_parameter_only_two_parts(self):
        r = parse_modelfile("PARAMETER temperature\n")
        assert r["parameters"] == {}

    def test_unknown_directive_ignored(self):
        r = parse_modelfile("SYSTEM You are helpful\nFROM base\n")
        assert r["from"] == "base"


# ─── _parse_size ─────────────────────────────────────────────────────────────

class TestParseSize:
    def test_gb(self):
        assert _parse_size("4.7 GB") == pytest.approx(4.7)

    def test_mb(self):
        assert _parse_size("512 MB") == pytest.approx(0.5)

    def test_kb(self):
        val = _parse_size("1048576 KB")  # 1 GB in KB
        assert val == pytest.approx(1.0)

    def test_invalid(self):
        assert _parse_size("unknown") == 0.0

    def test_lowercase(self):
        assert _parse_size("2.0 gb") == pytest.approx(2.0)

    def test_no_space(self):
        assert _parse_size("3.0GB") == pytest.approx(3.0)


# ─── _size_bytes_to_gb ───────────────────────────────────────────────────────

class TestSizeBytesToGb:
    def test_zero(self):
        assert _size_bytes_to_gb(0) == 0.0

    def test_none_like(self):
        assert _size_bytes_to_gb(0) == 0.0

    def test_one_gb(self):
        assert _size_bytes_to_gb(1024 ** 3) == pytest.approx(1.0)

    def test_two_gb(self):
        assert _size_bytes_to_gb(2 * 1024 ** 3) == pytest.approx(2.0)


# ─── OllamaScanner._get_list_api ─────────────────────────────────────────────

class TestGetListApi:
    def test_success(self):
        scanner = OllamaScanner()
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "llama3:8b"}, {"name": "phi3:mini"}]}
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.get", return_value=mock_resp):
            names = scanner._get_list_api()
        assert "llama3:8b" in names
        assert "phi3:mini" in names

    def test_empty_models(self):
        scanner = OllamaScanner()
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"models": []}
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.get", return_value=mock_resp):
            names = scanner._get_list_api()
        assert names == []

    def test_exception_returns_empty(self):
        scanner = OllamaScanner()
        with mock.patch("requests.get", side_effect=Exception("conn refused")):
            names = scanner._get_list_api()
        assert names == []

    def test_http_error_returns_empty(self):
        scanner = OllamaScanner()
        import requests as req_mod
        mock_resp = mock.MagicMock()
        mock_resp.raise_for_status.side_effect = req_mod.HTTPError("404")
        with mock.patch("requests.get", return_value=mock_resp):
            names = scanner._get_list_api()
        assert names == []


# ─── OllamaScanner._get_list_cli ─────────────────────────────────────────────

class TestGetListCli:
    def test_success(self):
        scanner = OllamaScanner()
        mock_proc = mock.MagicMock()
        mock_proc.stdout = (
            "NAME                    ID              SIZE    MODIFIED\n"
            "llama3:8b               abc123          4.7 GB  1 week ago\n"
        )
        with mock.patch("subprocess.run", return_value=mock_proc):
            names = scanner._get_list_cli()
        assert "llama3:8b" in names

    def test_file_not_found(self):
        scanner = OllamaScanner()
        with mock.patch("subprocess.run", side_effect=FileNotFoundError()):
            names = scanner._get_list_cli()
        assert names == []

    def test_timeout(self):
        scanner = OllamaScanner()
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ollama", 10)):
            names = scanner._get_list_cli()
        assert names == []


# ─── OllamaScanner._get_list ─────────────────────────────────────────────────

class TestGetList:
    def test_api_returns_names_skips_cli(self):
        scanner = OllamaScanner()
        scanner._get_list_api = mock.MagicMock(return_value=["m1", "m2"])
        scanner._get_list_cli = mock.MagicMock(return_value=["cli_model"])
        names = scanner._get_list()
        assert names == ["m1", "m2"]
        scanner._get_list_cli.assert_not_called()

    def test_api_empty_localhost_uses_cli(self):
        scanner = OllamaScanner("http://localhost:11434")
        scanner._get_list_api = mock.MagicMock(return_value=[])
        scanner._get_list_cli = mock.MagicMock(return_value=["cli_model"])
        names = scanner._get_list()
        assert "cli_model" in names

    def test_api_empty_127_uses_cli(self):
        scanner = OllamaScanner("http://127.0.0.1:11434")
        scanner._get_list_api = mock.MagicMock(return_value=[])
        scanner._get_list_cli = mock.MagicMock(return_value=["local"])
        names = scanner._get_list()
        assert "local" in names

    def test_api_empty_remote_no_cli(self):
        scanner = OllamaScanner("http://remote-host:11434")
        scanner._get_list_api = mock.MagicMock(return_value=[])
        scanner._get_list_cli = mock.MagicMock(return_value=["cli"])
        names = scanner._get_list()
        assert names == []
        scanner._get_list_cli.assert_not_called()


# ─── OllamaScanner._get_modelfile_api ────────────────────────────────────────

class TestGetModelfileApi:
    def test_success(self):
        scanner = OllamaScanner()
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {
            "modelfile": "FROM base\nPARAMETER temperature 0.7\n",
            "size": 5_000_000_000,
        }
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.post", return_value=mock_resp):
            content, size_gb = scanner._get_modelfile_api("llama3:8b")
        assert "FROM base" in content
        assert size_gb > 0

    def test_no_modelfile_key(self):
        scanner = OllamaScanner()
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"size": 0}
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.post", return_value=mock_resp):
            content, size_gb = scanner._get_modelfile_api("model")
        assert content == ""

    def test_exception(self):
        scanner = OllamaScanner()
        with mock.patch("requests.post", side_effect=Exception("no")):
            content, size_gb = scanner._get_modelfile_api("model")
        assert content == ""
        assert size_gb == 0.0

    def test_size_none(self):
        scanner = OllamaScanner()
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"modelfile": "FROM x", "size": None}
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.post", return_value=mock_resp):
            content, size_gb = scanner._get_modelfile_api("m")
        assert size_gb == 0.0


# ─── OllamaScanner._get_modelfile_cli ────────────────────────────────────────

class TestGetModelfileCli:
    def test_success(self):
        scanner = OllamaScanner()
        mock_show = mock.MagicMock()
        mock_show.stdout = "FROM base\n"
        mock_list = mock.MagicMock()
        mock_list.stdout = (
            "NAME                    ID   SIZE    MODIFIED\n"
            "mymodel:latest          abc  4.7 GB  1 week\n"
        )
        with mock.patch("subprocess.run", side_effect=[mock_show, mock_list]):
            content, size_gb = scanner._get_modelfile_cli("mymodel:latest")
        assert "FROM base" in content
        assert size_gb == pytest.approx(4.7)

    def test_show_file_not_found(self):
        scanner = OllamaScanner()
        with mock.patch("subprocess.run", side_effect=[
            FileNotFoundError(), FileNotFoundError()
        ]):
            content, size_gb = scanner._get_modelfile_cli("model")
        assert content == ""

    def test_show_timeout(self):
        scanner = OllamaScanner()
        with mock.patch("subprocess.run", side_effect=[
            subprocess.TimeoutExpired("ollama", 15),
            subprocess.TimeoutExpired("ollama", 5),
        ]):
            content, size_gb = scanner._get_modelfile_cli("model")
        assert content == ""

    def test_list_exception_size_zero(self):
        scanner = OllamaScanner()
        mock_show = mock.MagicMock()
        mock_show.stdout = "FROM base\n"
        with mock.patch("subprocess.run", side_effect=[
            mock_show,
            Exception("list failed"),
        ]):
            content, size_gb = scanner._get_modelfile_cli("model")
        assert "FROM base" in content
        assert size_gb == 0.0

    def test_list_no_matching_line(self):
        scanner = OllamaScanner()
        mock_show = mock.MagicMock()
        mock_show.stdout = "FROM x\n"
        mock_list = mock.MagicMock()
        mock_list.stdout = "NAME ID SIZE\nother:model abc 1.0 GB\n"
        with mock.patch("subprocess.run", side_effect=[mock_show, mock_list]):
            content, size_gb = scanner._get_modelfile_cli("mymodel")
        assert size_gb == 0.0


# ─── OllamaScanner._get_modelfile ────────────────────────────────────────────

class TestGetModelfile:
    def test_api_has_content_skips_cli(self):
        scanner = OllamaScanner()
        scanner._get_modelfile_api = mock.MagicMock(return_value=("FROM x", 1.0))
        scanner._get_modelfile_cli = mock.MagicMock(return_value=("FROM y", 2.0))
        content, size_gb = scanner._get_modelfile("m")
        assert content == "FROM x"
        scanner._get_modelfile_cli.assert_not_called()

    def test_api_empty_localhost_uses_cli(self):
        scanner = OllamaScanner("http://localhost:11434")
        scanner._get_modelfile_api = mock.MagicMock(return_value=("", 0.0))
        scanner._get_modelfile_cli = mock.MagicMock(return_value=("FROM y", 2.0))
        content, size_gb = scanner._get_modelfile("m")
        assert content == "FROM y"

    def test_api_empty_remote_returns_empty(self):
        scanner = OllamaScanner("http://remote:11434")
        scanner._get_modelfile_api = mock.MagicMock(return_value=("", 0.0))
        scanner._get_modelfile_cli = mock.MagicMock(return_value=("FROM y", 2.0))
        content, size_gb = scanner._get_modelfile("m")
        assert content == ""
        scanner._get_modelfile_cli.assert_not_called()

    def test_api_has_size_only(self):
        scanner = OllamaScanner()
        scanner._get_modelfile_api = mock.MagicMock(return_value=("", 3.0))
        scanner._get_modelfile_cli = mock.MagicMock(return_value=("FROM y", 2.0))
        content, size_gb = scanner._get_modelfile("m")
        assert size_gb == 3.0
        scanner._get_modelfile_cli.assert_not_called()


# ─── OllamaScanner.scan_local ────────────────────────────────────────────────

class TestScanLocal:
    def test_empty_models(self):
        scanner = OllamaScanner()
        scanner._get_list = mock.MagicMock(return_value=[])
        result = scanner.scan_local()
        assert result == []

    def test_single_model(self):
        scanner = OllamaScanner()
        scanner._get_list = mock.MagicMock(return_value=["llama3:8b-q4_K_M"])
        scanner._get_modelfile = mock.MagicMock(return_value=("FROM base\nPARAMETER temperature 0.7\n", 4.7))
        result = scanner.scan_local()
        assert len(result) == 1
        m = result[0]
        assert m.name == "llama3:8b-q4_K_M"
        assert m.size_gb == pytest.approx(4.7)
        assert m.from_model == "base"
        assert m.parameters["temperature"] == "0.7"
        assert "q4" in m.quant.lower()

    def test_multiple_models(self):
        scanner = OllamaScanner()
        scanner._get_list = mock.MagicMock(return_value=["m1", "m2", "m3"])
        scanner._get_modelfile = mock.MagicMock(return_value=("", 0.0))
        result = scanner.scan_local()
        assert len(result) == 3

    def test_on_progress_called(self):
        scanner = OllamaScanner()
        scanner._get_list = mock.MagicMock(return_value=["m1", "m2"])
        scanner._get_modelfile = mock.MagicMock(return_value=("", 0.0))
        calls = []
        scanner.scan_local(on_progress=lambda cur, tot, name: calls.append((cur, tot, name)))
        assert len(calls) == 2
        assert calls[0] == (1, 2, "m1")
        assert calls[1] == (2, 2, "m2")

    def test_no_on_progress(self):
        scanner = OllamaScanner()
        scanner._get_list = mock.MagicMock(return_value=["m1"])
        scanner._get_modelfile = mock.MagicMock(return_value=("", 0.0))
        result = scanner.scan_local()  # no on_progress, should not raise
        assert len(result) == 1

    def test_modelfile_empty_no_from(self):
        scanner = OllamaScanner()
        scanner._get_list = mock.MagicMock(return_value=["plain:model"])
        scanner._get_modelfile = mock.MagicMock(return_value=("", 0.0))
        result = scanner.scan_local()
        assert result[0].from_model is None
        assert result[0].parameters == {}

    def test_local_model_info_dataclass(self):
        info = LocalModelInfo(name="test", size_gb=1.0, quant="q4_K_M")
        assert info.name == "test"
        assert info.from_model is None
        assert info.parameters == {}
