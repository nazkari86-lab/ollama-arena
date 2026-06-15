"""Pull HumanEval and GSM8K from HuggingFace and run two models on each.

Requires `pip install 'ollama-arena[datasets]'`.
"""
from ollama_arena import Arena

arena = Arena()
arena.load_hf_dataset("humaneval", limit=20)
arena.load_hf_dataset("gsm8k",     limit=20)

a, b = "llama3.2:3b", "qwen2.5:7b"

print("humaneval")
r = arena.run_match(a, b, category="coding", n=10)
print(f"  {a}: {r.a_wins}W   {b}: {r.b_wins}W\n")

print("gsm8k")
r = arena.run_match(a, b, category="math", n=10)
print(f"  {a}: {r.a_wins}W   {b}: {r.b_wins}W\n")

for e in arena.leaderboard():
    print(f"  {e['rank']:>2}  {e['model']:30s}  elo {e['elo']:.0f}")
