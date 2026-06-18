# Agent Commands

Autonomous workflows built on `agent_loop.py` and MCP tools.

```bash
ollama-arena resolve-issue --model qwen2.5-coder:7b --issue "Fix parser bug" --max-steps 50
ollama-arena council --models A,B,C --topic "Architecture debate" --rounds 2
ollama-arena optimize-prompt --model llama3.2:3b
ollama-arena review-pr --models A,B
```

Each command forces real MCP mode and records an agent trace (tool calls, latencies,
security gate events) in `arena.db`.

See `examples/agent_resolve.py` for a minimal Python integration.
