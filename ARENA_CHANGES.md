# Ollama Arena — Change Log vs Roadmap

This document tracks what is **implemented** in the codebase versus what remains **planned**.

## Implemented

### MCP Tools (builtin handlers)
| Tool | Status |
|------|--------|
| `google_web_search`, `ddg_search` | ✅ DuckDuckGo HTML scrape |
| `web_fetch` | ✅ URL fetch + strip HTML |
| `wikipedia_search` | ✅ Wikipedia API |
| `get_datetime`, `system_info` | ✅ |
| `code_interpreter` | ✅ Docker default, WASM/subprocess fallback |
| `codebase_search`, `ast_parse`, `consult_expert` | ✅ |
| `ls`, `read_file`, `write_file` | ✅ Path containment |
| `computer_screenshot`, `computer_click`, `computer_type` | ✅ macOS only |
| Security gate (dangerous tools) | ✅ Deny non-TTY unless `ARENA_AUTO_APPROVE=1` |

### Agent & CLI
| Feature | Status |
|---------|--------|
| `resolve-issue`, `council`, `optimize-prompt`, `review-pr` | ✅ In CLI |
| Multi-step agent loop with trace | ✅ |
| Vision payloads (`images` in Ollama chat) | ✅ |

### Infrastructure
| Feature | Status |
|---------|--------|
| Memory scheduler (CONCURRENT/HOT_SWAP/PIPELINE) | ✅ + quant/VRAM estimates |
| Per-tool latency in `PerfTracker` | ✅ |
| Web static mount + modular frontend | ✅ |
| 286 built-in tasks | ✅ |
| Pre-commit + CI template with pytest/ruff | ✅ |

## Planned (not yet implemented)

| Item | Notes |
|------|-------|
| `browser_use` (Playwright MCP) | Optional `[mcp-browser]` extra |
| `git_status`, `git_commit` handlers | Gate exists, handlers pending |
| `ip_info`, `ping`, `crypto_price`, `math_solver` | Documented in early brief, not in registry |
| Modular `mcp/` package split | Monolithic `mcp_client.py` for now |
| CLI package split (`ollama_arena/cli/`) | Single `cli.py` |
| Repository storage layer | SQLite still inline in `elo.py` |
| Genome lineage auto-seed | Partial — see Phase 4 roadmap |
| Vision benchmark tasks (15+) | Category not yet populated |
| CSP nonce-based scripts | Still allows `'unsafe-inline'` |

## Version

Current release: **v1.1.0** (`pyproject.toml` and `ollama_arena.__version__`).
