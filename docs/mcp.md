# MCP Tools

Built-in MCP-style tools are registered in `ollama_arena/mcp/` and exposed through
`MCPOrchestrator.get_all_tools()`.

## Modes

| Mode | Env | Behaviour |
|------|-----|-----------|
| Real | `ARENA_MCP_MOCK=0` | Live handlers (network, filesystem, docker) |
| Auto-approve | `ARENA_AUTO_APPROVE=1` | Skip security gate (CI) |
| Deny | non-TTY, no auto-approve | Dangerous tools blocked |

## Dangerous tools

`code_interpreter`, `write_file`, `computer_click`, `computer_type`, `git_commit`,
`browser_use`, `codebase_search`, `ui_tars_action`

## Available Tool Categories

### Network Tools
- `ip_info` — Public IP, location, ISP information
- `ping` — Network latency diagnostics
- `system_info` — CPU, RAM, OS information
- `get_datetime` — Current local date and time

### Data & Math Tools
- `math_solver` — Safe mathematical expression evaluation
- `crypto_price` — Live cryptocurrency prices from CoinGecko

### Git Tools
- `git_status` — Git status in arena workspace
- `git_commit` — Stage all changes and commit

### Browser Tools (requires `[mcp-browser]` extra)
- `browser_use` — Playwright browser automation (navigate, click, scrape)
- `browser_navigate` — Mock browser navigation for benchmarks

### Web Tools
- `google_web_search` / `ddg_search` — Web search via DuckDuckGo
- `web_fetch` — URL fetch with HTML stripping
- `wikipedia_search` — Wikipedia API queries

### Workspace Tools
- `ls` — List workspace directory
- `read_file` — Read file contents
- `write_file` — Write file contents

### Developer Tools
- `code_interpreter` — Execute code in sandbox
- `codebase_search` — Regex/grep search across workspace
- `ast_parse` — AST structure analysis of Python files
- `consult_expert` — Senior engineering guidelines
- `algo_docs` — Algorithm and system design documentation

### Computer Tools
- `computer_screenshot` — Take screenshot (macOS)
- `computer_click` — Mouse click (macOS)
- `computer_type` — Keyboard input (macOS)

## Adding a tool

See `examples/mcp_custom_tool.py` — register a handler on `MCPOrchestrator`.
