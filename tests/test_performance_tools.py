"""Per-tool latency tracking in PerfTracker."""
import tempfile

from ollama_arena.performance import PerfTracker


def test_record_tool_and_export():
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/perf.db"
        p = PerfTracker(db)
        p.record("m1", "ollama", 10, 20, 1.0, 20.0, 0.1, category="coding")
        p.record_tool("ddg_search", "m1", 0.42, category="tool_use")
        p.record_tool("ddg_search", "m1", 0.58, category="tool_use")
        summary = p.export_summary()
        assert summary["tools"]
        assert summary["tools"][0]["tool"] == "ddg_search"
        assert summary["tools"][0]["n_calls"] == 2
        assert summary["models"][0]["tools"][0]["latency_mean_s"] > 0
