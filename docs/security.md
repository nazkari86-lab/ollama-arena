# Security

## Code execution

Isolation hierarchy in `sandboxes/runner.py`:

1. **Docker** (default for `code_interpreter`) — network none, seccomp, read-only rootfs
2. **WASM** (`pip install 'ollama-arena[wasm]'`) — fallback when Docker missing
3. **Subprocess** — AST/pattern deny-list + timeout (dev only)

## MCP security gate

Dangerous tools require TTY approval or `ARENA_AUTO_APPROVE=1`.

## Workspace path containment

`ls`, `read_file`, `write_file`, and `ast_parse` resolve paths under
`~/arena_workspace` and reject traversal (`../`).

## Web hardening

- CORS allowlist via `ARENA_ALLOWED_ORIGINS`
- Rate limits via `slowapi` (`ARENA_RL_*` env vars)
- CSP, `X-Frame-Options: DENY`, DOMPurify on model output

See `tests/test_mcp_security.py` and `tests/test_web_security.py`.
