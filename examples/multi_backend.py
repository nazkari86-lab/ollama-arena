"""
Multi-backend example — pit Ollama models against vLLM models.

Make sure both backends are running:
  Ollama  → ollama serve
  vLLM    → vllm serve mistralai/Mistral-7B-Instruct-v0.3 --port 8000
"""
from ollama_arena import Arena
from ollama_arena.backends import OllamaBackend, OpenAICompatBackend

# Battle 1: Ollama internal
arena_ollama = Arena(backend=OllamaBackend("http://localhost:11434"),
                     db_path="arena.db")
print("Ollama models:", arena_ollama.client.list_models()[:5])

# Battle 2: vLLM (OpenAI-compatible)
arena_vllm = Arena(backend=OpenAICompatBackend("http://localhost:8000/v1",
                                                api_key="EMPTY"),
                   db_path="arena.db")
print("vLLM models:", arena_vllm.client.list_models()[:5])

# Battle 3: Cross-backend round-robin (note: db is shared so ELO is unified)
print("\nRound-robin between Ollama and Cloud Groq:")
arena_groq = Arena(backend="groq", api_key="gsk_...", db_path="arena.db")
# arena_groq.run_match("llama-3.1-70b-versatile", "llama-3.1-8b-instant",
#                      category="reasoning", n=5)

# Show unified leaderboard
print("\nUnified leaderboard:")
for e in arena_ollama.leaderboard():
    print(f"  #{e['rank']} {e['model']:30s} ELO={e['elo']:.0f}")
