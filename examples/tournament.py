"""Round-robin tournament between every locally pulled model."""
from ollama_arena import Arena

arena = Arena()
models = arena.client.list_models()[:5]
print(f"tournament: {len(models)} models, coding category")

board = arena.run_tournament(models, category="coding", n_per_match=5)
for e in board:
    print(f"  {e['rank']:>2}  {e['model']:32s}  elo {e['elo']:.0f}"
          f"   {e['wins']}W/{e['losses']}L  ({e['win_rate']:.0%})")
