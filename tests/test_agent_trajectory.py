"""Evaluator tests for agent trajectory scoring."""
from ollama_arena.evaluator import eval_agent_trajectory, evaluate


def test_eval_agent_trajectory_ordered_tools():
    task = {"expected_tools": ["sqlite_query", "browser_navigate"]}
    trace = [
        {
            "step": 1,
            "tool_calls": [
                {"function": {"name": "sqlite_query", "arguments": "{}"}},
            ],
            "tool_results": [],
        },
        {
            "step": 2,
            "tool_calls": [
                {"function": {"name": "browser_navigate", "arguments": "{}"}},
            ],
            "tool_results": [],
        },
    ]
    assert eval_agent_trajectory(task, trace) == 1.0


def test_eval_agent_trajectory_partial_order():
    task = {"expected_tools": ["sqlite_query", "browser_navigate"]}
    trace = [
        {
            "step": 1,
            "tool_calls": [
                {"function": {"name": "sqlite_query", "arguments": "{}"}},
            ],
            "tool_results": [],
        },
    ]
    assert eval_agent_trajectory(task, trace) == 0.5


def test_evaluate_tool_use_with_trace():
    task = {
        "id": "tool_005",
        "category": "tool_use",
        "expected_tools": ["sqlite_query", "browser_navigate"],
    }
    trace = [
        {
            "step": 1,
            "tool_calls": [{"function": {"name": "sqlite_query"}}],
            "tool_results": [],
        },
        {
            "step": 2,
            "tool_calls": [{"function": {"name": "browser_navigate"}}],
            "tool_results": [],
        },
    ]
    score = evaluate(task, "", trace=trace)
    assert score >= 0.9
