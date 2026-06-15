# ⚔️ Ollama Arena

**ELO-rated head-to-head benchmarking for your local LLM models.**

Stop guessing which model is better. Let them fight.

```
ollama-arena match --models llama3.2:3b,qwen2.5:7b,gemma2:2b --category coding -n 10
```

```
⚔️  OLLAMA ARENA
Models: llama3.2:3b, qwen2.5:7b, gemma2:2b
Category: coding  |  Tasks per match: 10

Match 1/3: llama3.2:3b vs qwen2.5:7b
  ✅ code_001: 1.00 vs 1.00
  ✅ code_005: 1.00 vs 1.00
  ❌ code_015: 0.00 vs 1.00
  ...

🏆 ELO Leaderboard
╔══════╦══════════════════════╦════════╦═════╦═════╦═══════╦══════╗
║ Rank ║ Model                ║  ELO   ║  W  ║  L  ║  Mtch ║ Win% ║
╠══════╬══════════════════════╬════════╬═════╬═════╬═══════╬══════╣
║  🥇  ║ qwen2.5:7b           ║ 1263.4 ║ 17  ║  3  ║   20  ║  85% ║
║  🥈  ║ llama3.2:3b          ║ 1198.1 ║  9  ║ 11  ║   20  ║  45% ║
║  🥉  ║ gemma2:2b            ║ 1138.5 ║  4  ║ 16  ║   20  ║  20% ║
╚══════╩══════════════════════╩════════╩═════╩═════╩═══════╩══════╝
```

---

## Why?

Every Ollama user has 5–20 models installed. Nobody knows which is actually better for **their** tasks. [Chatbot Arena (LMSYS)](https://chat.lmsys.org) only covers cloud models.

**Ollama Arena** gives you a private, offline, automatically scored leaderboard for all your local models.

- ✅ **Zero config** — works out of the box with `ollama serve`
- ✅ **95+ built-in tasks** across 5 categories
- ✅ **Auto-scoring** — coding tasks run and assert-test generated code
- ✅ **ELO ratings** — persistent SQLite, every match counts
- ✅ **Beautiful terminal UI** using Rich
- ✅ **Web dashboard** — optional FastAPI UI at localhost:7860
- ✅ **Works with any model** Ollama can run

---

## Install

```bash
pip install ollama-arena
```

Or from source:
```bash
git clone https://github.com/nazkari86-lab/ollama-arena
cd ollama-arena
pip install -e .
```

**Requirements:**
- Python 3.9+
- [Ollama](https://ollama.ai) running locally (`ollama serve`)
- At least 2 models pulled (`ollama pull llama3.2 && ollama pull qwen2.5:7b`)

---

## Quick Start

```bash
# 1. Start Ollama
ollama serve

# 2. Pull some models
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
ollama pull gemma2:2b

# 3. See your models
ollama-arena list

# 4. Fight!
ollama-arena match --models llama3.2:3b,qwen2.5:7b --category coding -n 10

# 5. View leaderboard
ollama-arena leaderboard
```

---

## Commands

```
ollama-arena match     --models A,B[,C...]   Run battle(s)
               --category coding|reasoning|security|planning|inspection
               -n 10                         Tasks per match (default: 10)

ollama-arena leaderboard                     Show ELO table
ollama-arena list                            List available Ollama models
ollama-arena tasks                           Show benchmark statistics
ollama-arena web                             Launch web dashboard (port 7860)

Global flags:
  --ollama URL     Ollama base URL (default: http://localhost:11434)
  --db PATH        SQLite database (default: arena.db)
```

---

## Benchmark Categories

| Category    | Tasks | Scoring method |
|-------------|------:|----------------|
| **coding**  |   30  | Execute + assert tests (pass=1.0, fail=0.0) |
| **reasoning** | 15  | Exact/numeric answer matching |
| **security** | 15  | CVE/vulnerability detection rate |
| **planning** | 15  | Key component coverage + length heuristic |
| **inspection** | 20 | Bug detection precision/recall |
| **Total**   | **95** | |

Tasks range from Easy → Medium → Hard. Example:

```python
# coding — easy
"Write a Python function `fibonacci(n)` that returns the nth Fibonacci number."
# auto-tests: assert fibonacci(0)==0; assert fibonacci(10)==55

# security — hard  
"Find all SQL injection vulnerabilities in this authentication code."
# scored by: detection of CWE-89, severity, fix suggestion
```

---

## Web Dashboard

```bash
pip install 'ollama-arena[web]'
ollama-arena web
```

Opens at `http://localhost:7860`:
- Live ELO leaderboard
- Start matches from browser
- Real-time task-by-task results
- Match history

---

## Python API

```python
from ollama_arena import Arena

arena = Arena()  # uses arena.db by default

# Single match
result = arena.run_match("llama3.2:3b", "qwen2.5:7b", category="coding", n=10)
print(f"Winner ELO: {result.elo_a_after:.0f} vs {result.elo_b_after:.0f}")

# Round-robin tournament
leaderboard = arena.run_tournament(
    models=["llama3.2:3b", "qwen2.5:7b", "gemma2:2b"],
    category="reasoning",
    n_per_match=5,
)
for entry in leaderboard:
    print(f"#{entry['rank']} {entry['model']} — ELO {entry['elo']}")

# Add callback for live updates
def on_task(task_id, score_a, score_b, outcome):
    print(f"  {task_id}: {score_a:.2f} vs {score_b:.2f} → {outcome}")

arena._on_task_done = on_task
arena.run_match("phi3:mini", "tinyllama", category="reasoning", n=5)
```

---

## How ELO Works

- Each model starts at **ELO 1200**
- After every task: winner gains points, loser loses points (K=32)
- The stronger model gains less from winning, loses more from losing
- **ELO updates after every single task** — not just at match end
- Ratings persist in `arena.db` (SQLite) across sessions

---

## Custom Tasks

Add your own benchmark tasks to any category:

```python
# my_tasks.py
from ollama_arena.tasks import ALL_TASKS

ALL_TASKS["coding"].append({
    "id": "code_custom_001",
    "difficulty": "medium",
    "instruction": "Write a function `is_prime(n)` that checks primality efficiently.",
    "test_code": "assert is_prime(7)==True\nassert is_prime(9)==False\nassert is_prime(97)==True",
})
```

---

## Remote Ollama

```bash
# Point to a remote server
ollama-arena match --models llama3.2,qwen2.5:7b \
  --ollama http://my-server:11434 \
  --db /shared/arena.db
```

---

## Roadmap

- [ ] OpenAI-compatible API support (LM Studio, Jan, etc.)
- [ ] Export results to CSV/JSON
- [ ] Shareable leaderboard HTML
- [ ] More task categories: math, translation, summarization
- [ ] Difficulty filtering: `--difficulty hard`
- [ ] `ollama-arena watch` — auto-run as new models are pulled

---

## Contributing

```bash
git clone https://github.com/nazkari86-lab/ollama-arena
cd ollama-arena
pip install -e ".[dev]"

# Add tasks to ollama_arena/tasks/
# Run tests
pytest
```

PRs welcome — especially new benchmark tasks!

---

## License

MIT — use freely, attribution appreciated.

---

*Built with ❤️ for the Ollama community.*
