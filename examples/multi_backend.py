"""Compare models across Ollama, vLLM, and a cloud backend in one ELO table.

Run:
    ollama serve
    vllm serve mistralai/Mistral-7B-Instruct-v0.3 --port 8000
"""
import os

from ollama_arena import Arena
from ollama_arena.backends import OllamaBackend, OpenAICompatBackend

DB = "arena.db"

local  = Arena(backend=OllamaBackend(),                                 db_path=DB)
vllm   = Arena(backend=OpenAICompatBackend("http://localhost:8000/v1"), db_path=DB)
groq   = Arena(backend="groq", api_key=os.environ.get("GROQ_API_KEY"),  db_path=DB)

print("local:", local.client.list_models()[:5])
print("vllm:",  vllm.client.list_models()[:5])

# All three Arenas share arena.db so ELO is unified.
local.run_match("llama3.2:3b", "qwen2.5:7b", category="coding", n=5)

for e in local.leaderboard():
    print(f"  {e['rank']:>2}  {e['model']:30s}  elo {e['elo']:.0f}")
