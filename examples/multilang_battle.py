"""Per-language coding matches. Needs node/rustc/go/g++/tsx on PATH."""
from ollama_arena import Arena
from ollama_arena.sandboxes import available_languages
from ollama_arena.tasks import get_tasks

print("runtimes available:", available_languages())

arena = Arena()
A, B = "llama3.2:3b", "qwen2.5-coder:7b"

for lang in ["python", "javascript", "rust", "go"]:
    tasks = get_tasks(category="coding", language=lang, limit=3)
    if not tasks:
        continue
    arena._extra_tasks["coding_lang"] = tasks
    r = arena.run_match(A, B, category="coding_lang", n=len(tasks))
    print(f"  {lang:11s}  {A}: {r.a_wins}W  {B}: {r.b_wins}W")
