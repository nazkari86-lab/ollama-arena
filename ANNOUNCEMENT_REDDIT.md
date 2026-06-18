# Ollama Arena v2.5.0 - Local LLM Benchmarking with MCP Tools & Battle Royale 🏆

Hey r/LocalLLaMA! I'm excited to share the latest release of Ollama Arena, a local LLM benchmarking platform that runs entirely on your hardware.

## 🎯 What is Ollama Arena?
Ollama Arena lets you compare LLMs from different backends (Ollama, vLLM, LM Studio, llama.cpp, OpenAI-compatible) using auto-scored battles, ELO ratings, and comprehensive evaluation across 286 built-in tasks.

## 🚀 What's New in v2.5.0

### Major Features
- **Battle Royale Mode**: N-way simultaneous model battles - test 3+ models at once
- **MCP Tool Integration**: Native support for Model Context Protocol tools
- **Docker Sandboxes**: Secure code execution with Docker, WASM, and subprocess fallbacks
- **Enhanced Security**: Multi-layered sandbox validation with pattern detection
- **Performance**: 50x faster code extraction, 3-5x faster database operations

### Technical Improvements
- **Modular MCP Architecture**: Pluggable transport layer (stdio, HTTP, in-memory)
- **Connection Pooling**: Thread-safe SQLite connection management
- **Comprehensive Testing**: 300+ tests with 100% pass rate
- **Performance Tracking**: Per-tool latency monitoring
- **Vision Benchmarks**: Multimodal model testing capabilities

### Battle Modes
- **Head-to-Head**: Direct model comparison
- **Tournament**: Round-robin competition
- **Battle Royale**: N-way simultaneous battles
- **LLM Council**: Multi-agent debate on specific topics

## 💻 Getting Started
```bash
pip install ollama-arena

# Quick benchmark
ollama-arena benchmark --models llama3:8b,mistral:7b

# Battle royale with 3 models
ollama-arena royale --models llama3:8b,mistral:7b,gemma:7b --category coding -n 5

# Multi-agent council debate
ollama-arena council --models llama3:8b,mistral:7b --topic "AI safety concerns"
```

## 📊 Categories
- Coding (Python, JavaScript, multilingual)
- Reasoning & Logic
- Security Analysis
- Planning & Strategy
- Math & Problem Solving
- Knowledge & QA
- Creative Writing
- JSON Format Compliance
- Tool Use
- Vision (multimodal)

## 🔧 Supported Backends
- **Ollama**: Local models
- **vLLM**: High-performance inference
- **LM Studio**: User-friendly interface
- **llama.cpp**: Efficient quantization
- **OpenAI-compatible**: Groq, Together, OpenRouter, etc.

## 🛡️ Privacy & Security
- Everything runs locally
- Multi-layered sandbox validation
- AST-based code validation
- Pattern detection for dangerous operations
- Configurable security gates

## 📈 Roadmap
We're actively working on:
- Browser automation (Playwright MCP)
- Distributed architecture for multi-node execution
- Advanced configuration system
- Community leaderboard
- Vision benchmark expansion (15+ tasks)
- SSO integration for enterprise use

## 🤝 Feedback
I'd love to hear your feedback! Try it out and let me know:
- Which features would you like to see?
- Any issues or suggestions?
- Benchmark results you'd like to share?

## 📚 Resources
- GitHub: [your-repo-url]
- Documentation: [your-docs-url]
- PyPI: `pip install ollama-arena`

Let me know what you think! Looking forward to your feedback and suggestions. 🚀