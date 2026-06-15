"""Run a first match against whatever Ollama has pulled."""
from ollama_arena import Arena

arena = Arena()
models = arena.client.list_models()
if len(models) < 2:
    raise SystemExit("Pull at least two models first: ollama pull llama3.2")

a, b = models[:2]
result = arena.run_match(a, b, category="coding", n=5)

print(f"{a} vs {b}")
print(f"  wins:  {result.a_wins} vs {result.b_wins}  ({result.duration_s:.0f}s)")
print(f"  elo:   {result.elo_a_after:.0f} vs {result.elo_b_after:.0f}")

print("\nleaderboard")
for e in arena.leaderboard():
    print(f"  {e['rank']:>2}  {e['model']:30s}  elo {e['elo']:.0f}  ({e['wins']}W/{e['losses']}L)")
