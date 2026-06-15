"""
Quickstart example — run your first ELO match.
Make sure Ollama is running: ollama serve
"""
from ollama_arena import Arena

# Create arena (stores ELO in arena.db)
arena = Arena()

# Check available models
models = arena.client.list_models()
print(f"Available models: {models[:5]}")

if len(models) < 2:
    print("Pull at least 2 models: ollama pull llama3.2 && ollama pull qwen2.5:7b")
    exit(1)

model_a, model_b = models[0], models[1]
print(f"\nRunning: {model_a} vs {model_b} — 5 coding tasks\n")

# Run match
result = arena.run_match(model_a, model_b, category="coding", n=5)

print(f"\n{'='*50}")
print(f"Results: {model_a} {result.a_wins}W vs {result.b_wins}W {model_b}")
print(f"ELO: {result.elo_a_after:.0f} vs {result.elo_b_after:.0f}")
print(f"Duration: {result.duration_s:.0f}s")

# Leaderboard
print(f"\n{'='*50}")
print("Leaderboard:")
for entry in arena.leaderboard():
    print(f"  #{entry['rank']} {entry['model']:30s}  ELO={entry['elo']:.0f}  {entry['wins']}W/{entry['losses']}L")
