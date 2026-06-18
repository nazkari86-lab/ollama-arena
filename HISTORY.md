# Project History

The development of Ollama Arena followed a structured architectural evolution, moving from basic memory management to full agentic autonomy. While the project was released as a single cohesive system (v1.0.0-rc1), it was designed through four distinct phases:

### Phase 1: Memory-Adaptive Infrastructure (The MAPT Layer)
*Logic found in `memory_scheduler.py`*
Designed to solve the "Out of Memory" problem on local machines. Implemented the 3-tier scheduler (CONCURRENT, HOT_SWAP, PIPELINE) allowing 26B+ parameter models to run on 16GB RAM devices.

### Phase 2: Zero-Trust Security (The Sandbox Layer)
*Logic found in `sandboxes/`*
Ensured that model-generated code cannot escape to the host system. Built AST-based static analysis to block obfuscated Python escapes and enforced mandatory Docker execution with Seccomp syscall filtering.

### Phase 3: Stateful Agentic Evaluation (The Loop Layer)
*Logic found in `agent_loop.py` and `mcp_client.py`*
Transitioned from static text benchmarking to autonomous agent evaluation. Created the Model Context Protocol (MCP) orchestrator to inject real-world tools into matches and implemented trajectory scoring.

### Phase 4: Competitive Scale (The Royale Layer)
*Logic found in `arena.py` and `visualize/`*
Expanded from 1-vs-1 duels to N-way Battle Royale matches. Added hallucination detection, match report exports, and the comprehensive web dashboard.
