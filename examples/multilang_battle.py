"""
Multi-language coding battle — same problems across Python, JS, Rust, Go, TS, C++.
Shows which models can write idiomatic code in each language.

Requires runtimes installed locally:
  node, rustc, go, g++, tsx (or ts-node)
"""
from ollama_arena import Arena
from ollama_arena.sandboxes import available_languages
from ollama_arena.tasks import get_tasks

print("Available language runtimes:", available_languages())

arena = Arena()

for lang in ["python", "javascript", "rust", "go"]:
    tasks = get_tasks(category="coding", language=lang, limit=3)
    if not tasks:
        continue
    print(f"\n=== {lang.upper()} ({len(tasks)} tasks) ===")
    # Filter tasks dynamically by injecting them into the extra pool
    arena._extra_tasks["coding_lang"] = tasks
    r = arena.run_match("llama3.2:3b", "qwen2.5-coder:7b",
                        category="coding_lang", n=len(tasks))
    print(f"  {r.model_a}: {r.a_wins}W   {r.model_b}: {r.b_wins}W")
