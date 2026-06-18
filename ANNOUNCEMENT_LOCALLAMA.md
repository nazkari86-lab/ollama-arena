# ollama-arena v2.5.0 Released - Automatic Lineage Detection & Enhanced Genome Explorer

Hey r/LocalLLaMA! I just released v2.5.0 of ollama-arena with some major upgrades to the genome/lineage system.

## 🧬 What's New in v2.5.0

### Automatic Lineage Inference
The biggest feature is **automatic lineage detection** - it can now infer model relationships (fine-tuning, distillation, merging) based on:
- Naming pattern analysis (e.g., `*-instruct`, `*-distill`, `*-coder`)
- Architecture similarity matching (layers, hidden size, context length)
- Parameter size relationships (distillation detection)
- Family/org clustering

```bash
$ ollama-arena genome auto-seed --min-confidence 0.5 --dry-run

Lineage Hypotheses (12 found)
Child                   | Parent                | Relation       | Confidence
------------------------|-----------------------|----------------|------------
llama3.2:3b             | llama3.1:8b-instruct  | distilled_from | 0.72
qwen2.5-coder:7b        | qwen2.5:7b            | fine_tuned_from| 0.85
deepseek-r1:7b          | deepseek-r1:base       | distilled_from | 0.68
gemma2:9b-it            | gemma2:9b              | fine_tuned_from| 0.91
```

### Expanded Model Registry
Added 40+ canonical models with complete lineage chains:
- **Meta**: Llama 2, Llama 3, Llama 3.1, Llama 3.2, Code Llama
- **Alibaba**: Qwen 2, Qwen 2.5, Qwen 3, Qwen Coder series
- **Google**: Gemma 2, Gemma 3, BERT
- **Microsoft**: Phi 3, Phi 3.5, Phi 4
- **Mistral AI**: Mistral, Mixtral, Codestral
- **DeepSeek**: DeepSeek Coder, DeepSeek R1
- **And more**: NousResearch, 01.AI, Nomic AI, IBM

### Enhanced Genome Commands
- `ollama-arena genome scan` - Better local model identification
- `ollama-arena genome tree` - Improved lineage visualization
- `ollama-arena genome show <model>` - Detailed model cards
- `ollama-arena genome auto-seed` - **NEW** automatic lineage inference

## 🎯 Core Features (Recap)

### Quick Model Comparison
```bash
$ ollama-arena benchmark llama3.2:3b,qwen2.5-coder:7b --compare

  llama3.2:3b         Score: 61.3 / 100   (coding:58  reasoning:65  security:70 ...)
  qwen2.5-coder:7b    Score: 74.8 / 100   (coding:82  reasoning:71  security:68 ...)
  Winner: qwen2.5-coder:7b  (margin: 13.5 pts)
```

### Head-to-Head Battles with ELO
```bash
$ ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10

  ✓ A  code_001  1.00 vs 0.00  [easy][python]  Write a sieve of Eratosthenes…
  ✓ B  code_002  0.00 vs 1.00  [medium][python] Implement an LRU cache…
  = =  code_003  1.00 vs 1.00  [hard][python]   Write a consistent hash ring…
  ...

  rank  model                elo    W   L   D   win%
  1     qwen2.5-coder:7b    1271    7   1   2   70%
  2     llama3.2:3b         1129    1   7   2   10%
```

### Multi-Backend Support
Works with any Ollama-compatible backend:
- Ollama (default)
- vLLM (`--backend vllm`)
- LM Studio (`--backend lmstudio`)
- llama.cpp (`--backend llamacpp`)
- OpenAI-compatible APIs (`--backend openai --api-key ...`)

### Built-in Task Pool
286 hand-written tasks across:
- Coding (Python, JS/TS, Rust, Go, C++)
- Reasoning
- Security
- Planning
- Inspection

Plus HuggingFace integration for serious benchmarks (HumanEval, GSM8K, MMLU, MBPP, etc.)

## 🔧 Technical Details

### Lineage Inference Algorithm
The auto-seed feature uses multiple heuristics:

1. **Pattern Matching** (0.3-0.4 confidence)
   - Suffix patterns: `-instruct`, `-chat`, `-distill`, `-coder`
   - Prefix patterns: family names

2. **Architecture Similarity** (0.2-0.7 confidence)
   - Hidden size similarity (<10% diff)
   - Context length comparisons
   - Layer count analysis
   - Vocab size matching

3. **Parameter Relationships** (0.3-0.6 confidence)
   - Distillation: child << parent size
   - Fine-tuning: similar size
   - MoE detection

4. **Metadata Clustering** (0.1-0.3 confidence)
   - Same family
   - Same organization

Confidence scores are combined and hypotheses are only applied above the threshold (default 0.5).

### Database Schema
Separate SQLite database (`genome.db`) for lineage data:
```sql
canonical_models - Canonical model registry
local_models - Your local model inventory
genome_lineage - Inferred/declared relationships
```

### Memory Scheduler
New in v2.5.0: Run large models on small RAM
- `--memory-mode hot_swap` - Load/unload models between tasks
- `--memory-mode pipeline` - Staged execution for 70B+ models
- Automatic VRAM/quantization estimation

## 📊 Use Cases

### For Model Developers
- Track fine-tuning impact across versions
- Compare distillation quality
- Validate merge results

### For Model Users
- Choose the best model for your hardware
- Understand model trade-offs
- Build custom model families

### For Researchers
- Rapid prototyping of model comparisons
- Lineage analysis of model ecosystems
- Reproducible local benchmarks

## 🚀 Installation

```bash
pip install ollama-arena

# Optional extras
pip install 'ollama-arena[all]'  # web dashboard, charts, HF datasets
pip install 'ollama-arena[wasm]'  # WASM sandbox fallback
```

## 💡 Example Workflows

### Compare coding models
```bash
ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b,codestral:22b \
    --category coding -n 20 --share
```

### Explore model lineage
```bash
ollama-arena genome scan
ollama-arena genome auto-seed
ollama-arena genome tree --model llama3.1
```

### Benchmark with HF datasets
```bash
ollama-arena datasets --pull humaneval,gsm8k
ollama-arena match --dataset humaneval --models A,B -n 50
```

### Battle Royale (3+ models)
```bash
ollama-arena royale --models A,B,C,D --category reasoning -n 10
```

## 🤝 Contributing

The project is open-source (MIT) and welcomes contributions:
- Add models to the registry
- Improve lineage heuristics
- Add task categories
- Fix bugs and add features

GitHub: https://github.com/your-org/ollama-arena

## 📈 What's Next?

Planned features:
- Vision benchmarks (15+ tasks)
- Git integration handlers
- Browser automation (Playwright MCP)
- Enhanced web dashboard
- Model quantization guidance

---

**TL;DR**: ollama-arena v2.5.0 adds automatic lineage detection to help you understand model relationships, plus an expanded model registry with 40+ models. Try it with `pip install ollama-arena`!

Let me know what you think, especially:
- What models should be added to the registry?
- How can we improve lineage accuracy?
- What task categories are most useful?
