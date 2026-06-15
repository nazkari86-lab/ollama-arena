"""
Tournament example — round-robin between many local models.
"""
from ollama_arena import Arena

arena = Arena()

# Get top 5 by name
models = arena.client.list_models()[:5]
print(f"Tournament: {models}")

# Round-robin: every model fights every other
board = arena.run_tournament(models, category="coding", n_per_match=5)

print("\nFinal standings:")
for e in board:
    print(f"  #{e['rank']:2d}  {e['model']:32s}  ELO={e['elo']:.0f}  "
          f"{e['wins']}W/{e['losses']}L  ({e['win_rate']:.0%})")
