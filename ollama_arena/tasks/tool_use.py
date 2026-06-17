"""MCP Tool-Use evaluation tasks."""

TASKS = [
    {
        "id": "tool_001",
        "category": "tool_use",
        "instruction": "List all users in the database.",
        "expected_tool": "sqlite_query",
        "difficulty": "easy"
    },
    {
        "id": "tool_002",
        "category": "tool_use",
        "instruction": "Open google.com and search for 'latest AI news'.",
        "expected_tool": "browser_navigate",
        "difficulty": "medium"
    },
    {
        "id": "tool_003",
        "category": "tool_use",
        "instruction": "Search for the documentation on how to use Docker in Context7.",
        "expected_tool": "search_docs",
        "difficulty": "medium"
    },
    {
        "id": "tool_004",
        "category": "tool_use",
        "instruction": "Commit the current changes with a message 'feat: security audit'.",
        "expected_tool": "git_commit",
        "difficulty": "hard"
    },
    {
        "id": "tool_005",
        "category": "tool_use",
        "instruction": (
            "Query the database for all users, then open google.com to look up their company."
        ),
        "expected_tools": ["sqlite_query", "browser_navigate"],
        "difficulty": "hard",
    },
    {
        "id": "tool_006",
        "category": "tool_use",
        "instruction": (
            "Search Context7 for Docker documentation, then commit notes with "
            "message 'docs: docker setup'."
        ),
        "expected_tools": ["search_docs", "git_commit"],
        "difficulty": "hard",
    },
]

def get_tool_tasks():
    return TASKS
