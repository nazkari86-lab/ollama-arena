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

`code_interpreter`, `write_file`, `computer_click`, `computer_type`, `git_commit`

## Adding a tool

See `examples/mcp_custom_tool.py` — register a handler on `MCPOrchestrator`.
