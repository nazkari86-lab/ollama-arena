# Changelog

## [3.0.0] - 2026-06-18
### Added
- **Deep Agentic Evaluation:** From single prompts to complex, multi-hour engineering tasks
  - Stateful VM Sandboxes with KubeVirt/Firecracker integration for isolated, persistent workspaces
  - Swarm Battles (2v2/3v3) for evaluating collaborative AI teamwork with message passing protocols
  - Chaos Engineering / Red Teaming Arena for adversarial survival scenarios
  - Long-horizon task category with checkpoint/resume functionality for 1-8 hour tasks
- **Continuous Auto-Finetuning:** Closed-loop self-improvement system
  - Loss-driven RLHF/DPO pipeline that automatically collects preference pairs from match results
  - Auto-Unsloth integration for automatic LoRA fine-tuning after configurable loss thresholds
  - Adversarial dataset generation that uses AI to create harder tasks based on model weaknesses
  - Finetuning orchestration with GPU resource queuing and job management
- **Global P2P Grid:** Decentralized, cryptographically verified arena
  - Arena@Home P2P network allowing users to contribute GPU cycles like Folding@Home
  - P2P task distribution with gossip protocol and Byzantine fault-tolerant consensus
  - Blockchain/cryptographic proof of eval with Zero-Knowledge Proofs for result verification
  - Global cryptographically verified leaderboard with fraud detection and vendor protection
- **Deep Hardware & Energy Telemetry:** Hardware-level cost and performance profiling
  - Energy metrics (Tokens-per-Watt) with NVIDIA NVML, AMD ROCm, and Apple MPS integration
  - Hardware telemetry base with unified platform-agnostic collection interface
  - Optimal quantization discovery that automatically tests and recommends best model formats
  - Memory bandwidth profiling with eBPF for TTFT impact analysis
  - Telemetry dashboard with hardware comparison, cost analysis, and efficiency rankings
- **"God-Mode" 3D Command Center:** Immersive visualization and seamless integration
  - WebGL/Three.js 3D neural map with real-time token probability visualization
  - First-class IDE extensions for VS Code and Cursor with "Send to Arena" functionality
  - CI/CD quality gates AI integration for GitHub Actions with automated PR evaluation
  - Enhanced real-time battle visualization with multi-agent collaboration views

### Changed
- **Architecture:** Transformed from evaluation tool to continuous AI evolution factory
- **Model Lifecycle:** Models now self-improve through automatic fine-tuning based on arena performance
- **Evaluation Scope:** Extended from single-turn responses to complex, multi-step agentic tasks
- **Trust Model:** Cryptographic verification prevents result manipulation and ensures leaderboard integrity

### Security
- Zero-Knowledge Proofs protect both model prompts and proprietary benchmarks during verification
- VM sandbox isolation with KubeVirt/Firecracker for secure code execution
- Cryptographic result signing prevents vendor fraud and ensures immutability
- P2P network with anti-sybil mechanisms and reputation-based consensus

### Performance
- Energy efficiency optimization through tokens-per-watt metrics and cost analysis
- Optimal quantization recommendations reduce VRAM usage while minimizing ELO degradation
- Memory bandwidth profiling identifies bottlenecks and improves TTFT performance
- P2P distributed computing enables linear scaling with contributed GPU resources

### Breaking Changes
- Python 3.11+ required for eBPF and async/await improvements
- Some advanced features require GPU with NVML/ROCm/MPS support
- P2P features require additional dependencies (libp2p, cryptography libraries)

## [2.5.0] - 2026-06-17
### Added
- **Distributed Architecture:** Multi-node execution support with horizontal scaling
  - Node pool management with health checking and registration
  - Load balancing with five strategies: round-robin, least-loaded, random, affinity, weighted
  - Distributed task executor with parallel execution and fault tolerance
  - Model-aware node selection for optimal resource utilization
- **CSP Security Improvements:** Nonce-based Content Security Policy
  - Removed 'unsafe-inline' from CSP headers for enhanced security
  - Cryptographically secure nonce generation for script and style execution
  - CSP nonce manager and policy builder for flexible security configuration
  - Integration with Jinja templates for automatic nonce injection
- **Architecture Decision Records:** Comprehensive ADR documentation
  - ADR 005: Distributed Architecture for Multi-Node Execution
  - ADR 006: CSP Security Improvements with Nonce-Based Policies
- **Comprehensive Test Coverage:** Added test suites for new features
  - CSP nonce generation and validation tests (18 test cases)
  - Distributed node management tests (25 test cases)
  - Node pool and health checking tests (22 test cases)
  - Load balancing strategy tests (18 test cases)

### Changed
- **Web Security Middleware:** Updated to use nonce-based CSP policies
- **Template Rendering:** Custom CSP-aware Jinja environment for nonce injection

### Security
- Eliminated 'unsafe-inline' CSP directive vulnerability
- Implemented OWASP-compliant nonce-based CSP
- Enhanced XSS protection through strict CSP policies

### Performance
- Linear scalability with distributed node architecture
- Reduced evaluation time through parallel task execution
- Efficient load balancing minimizes resource idle time

## [1.0.0-rc1] - 2026-06-17
### Added
- **Initial Public Release:** A comprehensive Stateful Agentic Evaluation platform.
- **Battle Royale Mode:** N-way simultaneous matches (3-8 models) with pairwise ELO updates.
- **MAPT Scheduler:** Memory-Adaptive Pipeline Tournament for running large models on small RAM.
- **Zero-Trust Sandbox:** AST-validated code execution in Seccomp-hardened Docker.
- **MCP Orchestration:** Multi-step agent loops with real-world tool injection.
- **Hallucination Detection:** Integrated logic auditing and Anti-Leaderboard.
- **Interactive Dashboard:** GSAP/Three.js-powered web UI with Deep Packet Inspection.
- **Match Export:** Detailed HTML/JSON reporting for all matches.
