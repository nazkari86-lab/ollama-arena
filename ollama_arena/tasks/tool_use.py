"""MCP Tool-Use evaluation tasks."""

TASKS = [
    {
        "id": "tool_001",
        "category": "tool_use",
        "instruction": "Search the web for the latest AI news headlines.",
        "expected_tool": "ddg_search",
        "expected_args": {"query": r"latest.*AI.*news"},
        "difficulty": "easy",
    },
    {
        "id": "tool_002",
        "category": "tool_use",
        "instruction": "Use the browser to open google.com and search for 'latest AI news'.",
        "expected_tool": "browser_use",
        "expected_args": {"url": r"google\.com"},
        "difficulty": "medium",
    },
    {
        "id": "tool_003",
        "instruction": "Look up Docker on Wikipedia and summarize the article.",
        "category": "tool_use",
        "expected_tool": "wikipedia_search",
        "expected_args": {"query": r"docker"},
        "difficulty": "medium",
    },
    {
        "id": "tool_004",
        "category": "tool_use",
        "instruction": "Commit the current changes with a message 'feat: security audit'.",
        "expected_tool": "git_commit",
        "expected_args": {"message": r"feat: security audit"},
        "difficulty": "hard",
    },
    {
        "id": "tool_005",
        "category": "tool_use",
        "instruction": (
            "Search the web for user database design patterns, then fetch a relevant page."
        ),
        "expected_tools": ["ddg_search", "web_fetch"],
        "expected_args": {
            "ddg_search": {"query": r"user.*database"},
            "web_fetch": {"url": r"https?://"},
        },
        "difficulty": "hard",
    },
    {
        "id": "tool_006",
        "category": "tool_use",
        "instruction": (
            "Search Wikipedia for Docker documentation, then commit notes with "
            "message 'docs: docker setup'."
        ),
        "expected_tools": ["wikipedia_search", "git_commit"],
        "expected_args": {
            "wikipedia_search": {"query": r"docker"},
            "git_commit": {"message": r"docs: docker setup"},
        },
        "difficulty": "hard",
    },
    {
        "id": "tool_007",
        "category": "tool_use",
        "instruction": "Run a SQL query to list all tables in the database.",
        "expected_tool": "sqlite_query",
        "expected_args": {"query": r"(?i)(select|show|list|tables)"},
        "difficulty": "easy",
    },
    {
        "id": "tool_008",
        "category": "tool_use",
        "instruction": "Search documentation for 'rate limiting middleware'.",
        "expected_tool": "search_docs",
        "expected_args": {"query": r"rate.*limit"},
        "difficulty": "medium",
    },
    {
        "id": "tool_009",
        "category": "tool_use",
        "instruction": "Navigate to https://example.com and report the page title.",
        "expected_tool": "browser_navigate",
        "expected_args": {"url": r"example\.com"},
        "difficulty": "easy",
    },
    {
        "id": "tool_010",
        "category": "tool_use",
        "instruction": "Fetch the contents of https://httpbin.org/get for inspection.",
        "expected_tool": "web_fetch",
        "expected_args": {"url": r"httpbin\.org"},
        "difficulty": "easy",
    },
    {
        "id": "tool_011",
        "category": "tool_use",
        "instruction": "Search the web for Python asyncio best practices.",
        "expected_tool": "ddg_search",
        "expected_args": {"query": r"asyncio"},
        "difficulty": "easy",
    },
    {
        "id": "tool_012",
        "category": "tool_use",
        "instruction": "Look up 'FastAPI' on Wikipedia.",
        "expected_tool": "wikipedia_search",
        "expected_args": {"query": r"fastapi"},
        "difficulty": "easy",
    },
    {
        "id": "tool_013",
        "category": "tool_use",
        "instruction": "Commit staged changes with message 'fix: handle timeout errors'.",
        "expected_tool": "git_commit",
        "expected_args": {"message": r"fix:.*timeout"},
        "difficulty": "medium",
    },
    {
        "id": "tool_014",
        "category": "tool_use",
        "instruction": "Query the users table for accounts created in the last 7 days.",
        "expected_tool": "sqlite_query",
        "expected_args": {"query": r"(?i)users"},
        "difficulty": "medium",
    },
    {
        "id": "tool_015",
        "category": "tool_use",
        "instruction": "Search docs for JWT authentication setup, then open the top result in the browser.",
        "expected_tools": ["search_docs", "browser_navigate"],
        "expected_args": {
            "search_docs": {"query": r"jwt|auth"},
            "browser_navigate": {"url": r"https?://"},
        },
        "difficulty": "hard",
    },
    {
        "id": "tool_016",
        "category": "tool_use",
        "instruction": "Search for 'kubernetes helm chart' and fetch the first relevant URL.",
        "expected_tools": ["ddg_search", "web_fetch"],
        "expected_args": {
            "ddg_search": {"query": r"helm|kubernetes"},
            "web_fetch": {"url": r"https?://"},
        },
        "difficulty": "medium",
    },
    {
        "id": "tool_017",
        "category": "tool_use",
        "instruction": "Use the browser to visit github.com and search for 'ollama arena'.",
        "expected_tool": "browser_use",
        "expected_args": {"url": r"github"},
        "difficulty": "medium",
    },
    {
        "id": "tool_018",
        "category": "tool_use",
        "instruction": "Find Wikipedia article on PostgreSQL, summarize it, and commit notes as 'docs: postgres'.",
        "expected_tools": ["wikipedia_search", "git_commit"],
        "expected_args": {
            "wikipedia_search": {"query": r"postgres"},
            "git_commit": {"message": r"docs:.*postgres"},
        },
        "difficulty": "hard",
    },
    {
        "id": "tool_019",
        "category": "tool_use",
        "instruction": "Run a SQL count query on the orders table.",
        "expected_tool": "sqlite_query",
        "expected_args": {"query": r"(?i)(count|orders)"},
        "difficulty": "easy",
    },
    {
        "id": "tool_020",
        "category": "tool_use",
        "instruction": "Search documentation for CORS configuration examples.",
        "expected_tool": "search_docs",
        "expected_args": {"query": r"cors"},
        "difficulty": "easy",
    },
    {
        "id": "tool_021",
        "category": "tool_use",
        "instruction": (
            "Search the web for REST API versioning strategies, fetch one article, "
            "and commit a summary with message 'docs: api versioning'."
        ),
        "expected_tools": ["ddg_search", "web_fetch", "git_commit"],
        "expected_args": {
            "ddg_search": {"query": r"api.*version"},
            "web_fetch": {"url": r"https?://"},
            "git_commit": {"message": r"docs:.*version"},
        },
        "difficulty": "hard",
    },
    {
        "id": "tool_022",
        "category": "tool_use",
        "instruction": "Query sqlite for schema of the products table, then search docs for migration patterns.",
        "expected_tools": ["sqlite_query", "search_docs"],
        "expected_args": {
            "sqlite_query": {"query": r"(?i)products|schema"},
            "search_docs": {"query": r"migration"},
        },
        "difficulty": "hard",
    },
]


def get_tool_tasks():
    return TASKS
