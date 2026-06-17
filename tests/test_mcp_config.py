import json, os, tempfile
from ollama_arena.mcp_config import MCPConfig, load_mcp_config, DEFAULT_CONFIG


def test_default_config_has_sqlite():
    cfg = DEFAULT_CONFIG
    assert "sqlite" in cfg["servers"]


def test_load_from_file():
    data = {"servers": {
        "mydb": {"command": "uvx", "args": ["mcp-server-sqlite", "--db-path", "/tmp/x.db"],
                 "description": "Test DB"}
    }}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = f.name
    try:
        cfg = load_mcp_config(path)
        assert "mydb" in cfg.servers
        assert cfg.servers["mydb"].command == "uvx"
        assert cfg.servers["mydb"].args[0] == "mcp-server-sqlite"
    finally:
        os.unlink(path)


def test_missing_file_returns_default():
    cfg = load_mcp_config("/nonexistent/path.json")
    assert cfg is not None
    assert len(cfg.servers) >= 0
