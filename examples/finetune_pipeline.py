"""End-to-end fine-tune loop. Needs CUDA and `pip install 'ollama-arena[finetune]'`."""
from ollama_arena import Arena
from ollama_arena.finetune import (
    analyze_weaknesses, build_training_dataset, save_jsonl,
    unsloth_train, UnslothConfig,
    build_modelfile, install_to_ollama,
)

arena = Arena()

# Baseline so analyze_weaknesses has something to chew on.
arena.run_tournament(
    ["llama3.2:3b", "qwen2.5-coder:7b"],
    category="coding", n_per_match=10,
)

weak = analyze_weaknesses("arena.db")
if not weak:
    raise SystemExit("No weak (model, category) pairs found.")

target = weak[0]
student, cat = target["model"], target["category"]

records = build_training_dataset(student, cat, db_path="arena.db", n_tasks=30)
jsonl = save_jsonl(records, f"train_{student.replace(':', '_')}.jsonl")
print(f"wrote {len(records)} pairs -> {jsonl}")

artifacts = unsloth_train(jsonl, UnslothConfig(
    base_model="unsloth/llama-3.2-3b-instruct-bnb-4bit",
    epochs=2, save_gguf=True, quant_method="q4_k_m",
))

new_name = f"{student}-tuned"
if install_to_ollama(build_modelfile(artifacts["gguf_path"], "Modelfile.tuned"), new_name):
    arena.run_match(new_name, "qwen2.5-coder:7b", category=cat, n=10)
    for e in arena.leaderboard():
        print(f"  {e['rank']:>2}  {e['model']:30s}  elo {e['elo']:.0f}")
