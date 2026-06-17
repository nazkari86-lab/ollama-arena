# Ollama Arena Project Briefing

**To the AI (Claude Opus 4.6 / Antigravity CLI):** Read this document carefully. It contains the entire architectural context, current state, and future roadmap for the `ollama-arena` project.

## 1. Project Overview
**Name:** Ollama Arena (v5.0.0)
**Purpose:** A highly advanced, local-first pair-wise ELO evaluation arena for LLMs. It has evolved from a static prompt-response benchmark into a **Stateful Agentic Evaluation Platform**.
**Tech Stack:** Python 3.10+, FastAPI (Web Dashboard), SQLite (WAL mode, migrations), Docker (Sandboxing), MCP (Model Context Protocol).

## 2. Core Architecture
The project is built around a "Zero Trust" execution model and advanced memory management.

*   **`arena.py` (The Orchestrator):** Manages matches between models. Now features an Agent Loop (`run_agent_sync`) for multi-turn tool-use evaluation.
*   **`memory_scheduler.py` (The Breakthrough):** A 3-tier memory engine (CONCURRENT, HOT_SWAP, PIPELINE) that allows running massive models (e.g., 26B parameters) on limited hardware (16GB RAM) by hot-swapping or pipelining task execution.
*   **`mcp_client.py`:** Integrates Model Context Protocol servers (Playwright, SQLite, SearXNG, Git). The Arena acts as an MCP client, providing tools to the models during matches.
*   **`sandboxes/` (Zero Trust Execution):**
    *   `security.py`: An AST (Abstract Syntax Tree) validator that blocks Python introspection (`__subclasses__`), obfuscation, and dangerous imports *before* execution.
    *   `runner.py`: Enforces mandatory Docker execution with Seccomp syscall filtering, dropped capabilities, and strict resource quotas.
*   **`elo.py` & `migrations.py`:** Handles ELO rating calculations and database interactions. Employs a forward-only migration system to ensure DB integrity across updates.
*   **`backends/`:** Supports native Ollama, speculative decoding (`spec.py`), and an `OpenAICompatBackend` with extensive cloud presets (DeepSeek, Anthropic, X.AI) and full Tool Calling (`tool_calls`) support.

## 3. Web UI & Evaluation
*   **Web Dashboard (`web.py`, `index.html`):** A FastAPI backend serving a Jinja2 template. Hardened with DOMPurify (XSS protection), SlowAPI (Rate Limiting), and strict CORS. Features a visual diffing tool (`jsdiff`) and GSAP 3 animations.
*   **Evaluator (`evaluator.py`):** Scores models across 9 categories. The crown jewel is `eval_tool_use`, which performs trajectory evaluation (scoring based on the subsequence of expected tools called).
*   **LLM Judge (`judge.py`):** Uses a strong model to grade creative tasks. Hardened against Prompt Injections (e.g., ignoring instructions within the generated text).

## 4. Current State (v5.0.0 - Phase 1 Complete)
We have just completed Phase 1 of the Stateful Agentic Evaluation upgrade:
*   The Agent Loop is functional.
*   MCP mock tools (like `sqlite_query`) return JSON arrays.
*   Trajectory testing awards partial scores for tool usage.
*   138/138 tests are passing.

## 5. What Needs to be Done (The Roadmap)
Your goal is to assist in developing Phase 2 and transitioning towards v6.0.

### High Priority (Immediate Next Steps)
1.  **Web UI Agent Trace Integration:** The `/api/playground/vote` endpoint in `web.py` currently only saves the final text response. It needs to be updated to handle and display the `agent_trace` (the step-by-step tool calls and results) in the UI. `save_task_detail` in `elo.py` already supports `tool_call_a/b` columns; the frontend needs to utilize them.
2.  **Real MCP Integration:** Replace the mocked tools in `mcp_client.py` with actual `mcp` SDK connections (stdio/SSE) to real servers (e.g., `@modelcontextprotocol/server-sqlite`).
3.  **Battle Royale Mode:** Implement an N-way match system (4 or 8 models) using the `royale_log` and `royale_entries` tables prepared in Migration 4.

### Medium Priority (Enhancements)
1.  **Distributed Nodes:** Allow the Arena to dispatch tasks to external IPs running Ollama, enabling load balancing across multiple machines.
2.  **Blind Voting Arena:** Update the web UI to hide model names during manual voting to prevent bias.
3.  **Smart Cache Optimization:** Hash the prompt + model + temperature. Skip generation if an exact match exists in the DB.

## 6. Operating Rules
*   **Use Your Skills:** You have access to over 370 skills in your `~/.gemini/skills/` directory. Use `systematic-debugging` for bugs, `writing-plans` before major refactors, and `python-testing` for all new code.
*   **No Placeholders:** Write complete code.
*   **Zero Trust:** Maintain the strict security posture established in `sandboxes/`.

**End of Briefing.**
