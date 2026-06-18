# Ollama Arena: The Complete Project Manifest

## 1. What is Ollama Arena?
**Ollama Arena** is a local-first, privacy-centric ELO evaluation platform for Large Language Models (LLMs). Unlike standard benchmarks that test static text, Ollama Arena evaluates models as **Autonomous Agents** capable of using tools and reasoning through multi-turn interactions.

---

## 2. Core Functional Pillars (v1.0.0-rc1)

### A. Stateful Agentic Evaluation
The project uses an **Agent Loop** and **MCP Orchestrator** to inject real-world tools into conversations. Models are scored on their **Trajectory**—the specific sequence of tools invoked.

### B. Memory-Adaptive Pipeline Tournament (MAPT)
A scheduling system that allows running massive models (26B+) on limited hardware (16GB RAM) via **CONCURRENT**, **HOT SWAP**, or **PIPELINE** modes.

### C. Combat Modes
- **Duels (1-vs-1):** Direct head-to-head.
- **Battle Royale (N-Way):** 3-8 models fighting simultaneously.
- **Grand Tournament:** Automated round-robin brackets.
- **Experimental Blind Mode (UI):** Frontend-level anonymization to reduce brand bias (LMSYS-style).

### D. Hallucination Detection & Anti-Leaderboard
Integrated **LLM Judge** audits responses for factual errors, populating the **Anti-Leaderboard**.

---

## 3. Roadmap (v1.1+)
- **Server-Side Blind Arena:** Cryptographically secure masking to prevent latency-based de-anonymization.
- **Distributed Nodes:** Cluster orchestration for dispatching tasks to multiple Ollama servers.
- **LLM Genome Explorer (v6.0.0):** Comprehensive model genealogy and architectural indexing.

---

## 4. Complete Project Structure & File Map

### Core Logic (`/ollama_arena/`)
- `arena.py`: **The Orchestrator.** Manages matches, scoring, and the high-level battle logic.
- `agent_loop.py`: **Agentic Engine.** Handles multi-turn tool-use loops between models and MCP.
- `mcp_client.py`: **Tool Gateway.** Connects to Model Context Protocol servers (SQLite, Browser, etc.).
- `memory_scheduler.py`: **RAM Optimizer.** Manages model loading/unloading to prevent OOM errors.
- `elo.py`: **Ranking Engine.** Calculates ELO ratings and manages the ratings database.
- `evaluator.py`: **Scoring Logic.** Per-category deterministic and heuristic scorers.
- `judge.py`: **LLM-as-a-Judge.** Uses strong models to grade creative tasks and detect hallucinations.
- `performance.py`: **Telemetry.** Tracks TPS (Tokens Per Second), Latency, and TTFT.
- `migrations.py`: **DB Schema.** Forward-only SQLite migration system.
- `web.py`: **Backend API.** FastAPI implementation for the web dashboard.
- `webui_bridge.py`: **Sync Tool.** Links Arena ELO ratings with Open WebUI.
- `_banner.py`: **CLI Branding.** ANSI art and startup information.
- `utils.py`: Shared helper functions (code extraction, text cleaning).

### Sandboxing & Security (`/ollama_arena/sandboxes/`)
- `runner.py`: **Safe Executor.** Manages Docker container lifecycle for code tasks.
- `security.py`: **Code Auditor.** AST-based scanner that blocks dangerous Python patterns.
- `seccomp.json`: **Kernel Filter.** System call whitelist for Docker containers.
- `base.py`: Abstract base classes for language sandboxes.

### Benchmark Tasks (`/ollama_arena/tasks/`)
- `coding.py`: Unit-test based programming challenges.
- `tool_use.py`: Agentic tasks requiring specific tool calls and arguments.
- `reasoning.py`: Multi-step logic and chain-of-thought problems.
- `math.py`: GSM8K-style quantitative problems.
- `security.py`: Vulnerability detection and exploit writing (safe).
- `structured_json.py`: Schema conformance and JSON extraction tests.
- `creative.py` / `knowledge.py` / `planning.py`: High-level cognitive tests.

### Model Backends (`/ollama_arena/backends/`)
- `ollama.py`: Native integration with the Ollama API.
- `openai_compat.py`: Support for vLLM, LM Studio, Groq, and Cloud providers.
- `spec.py`: **Speculative Decoding.** Logic for small-model draft verification.
- `transformers_backend.py`: In-process generation via the HuggingFace library.
- `auto.py`: Automatic backend detection based on URL or string tags.

### Visualization & Reporting (`/ollama_arena/visualize/`)
- `charts.py`: Plotly-based ELO timelines, radar charts, and heatmaps.
- `reports.py`: Export logic for HTML/JSON match and royale reports.

### Fine-tuning Pipeline (`/ollama_arena/finetune/`)
- `unsloth_runner.py`: High-speed training using the Unsloth library.
- `generator.py`: Synthetic dataset generation from Arena match logs.
- `ollama_export.py`: Converting fine-tuned weights back into Ollama GGUFs.

### Frontend & Assets
- `/templates/index.html`: **The Dashboard.** Single-page GSAP/Three.js web interface.
- `/static/arena3d.js`: Three.js engine for the real-time battle visualizer.

### Documentation & Research
- `README.md`: Quick start and installation guide.
- `CHANGELOG.md`: Version history and milestone tracking.
- `GEMINI.md`: AI-specific instructions and architecture mandates.
- `docs/PROJECT_MANIFEST.md`: This file (The "Big Picture").
- `docs/GENOME_EXPLORER_ARCHITECTURE.md`: Technical blueprint for v6.0.0.
- `docs/antigravity_briefing.md`: Deep architectural dive for AI agents.

### Project Meta
- `pyproject.toml`: Dependency management and build configuration.
- `Makefile`: Commands for testing, building, and publishing.
- `tests/`: Full coverage suite (138 validation cases across 71 unit tests).

---

## 5. Philosophical Pillar
**"Ollama shows what you have. The Arena proves how it performs. The Genome explains why it exists."**
