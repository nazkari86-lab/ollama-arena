"""
HuggingFace dataset example — run HumanEval / GSM8K / MMLU on your models.

Requires:  pip install 'ollama-arena[datasets]'
"""
from ollama_arena import Arena

arena = Arena()  # auto-detects Ollama on :11434

# Pull HumanEval (164 Python tasks) — cached on first run
arena.load_hf_dataset("humaneval", limit=20)

# Pull GSM8K math problems
arena.load_hf_dataset("gsm8k", limit=20)

# Run match: HumanEval (coding) — language is auto-detected per task
print("=== HumanEval ===")
r = arena.run_match("llama3.2:3b", "qwen2.5:7b", category="coding", n=10)
print(f"  {r.model_a}: {r.a_wins}W   {r.model_b}: {r.b_wins}W")

# Run match: GSM8K (math)
print("\n=== GSM8K ===")
r = arena.run_match("llama3.2:3b", "qwen2.5:7b", category="math", n=10)
print(f"  {r.model_a}: {r.a_wins}W   {r.model_b}: {r.b_wins}W")

print("\n=== Final Leaderboard ===")
for e in arena.leaderboard():
    print(f"  #{e['rank']} {e['model']:30s} ELO={e['elo']:.0f}")
