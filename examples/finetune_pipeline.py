"""
Closed-loop fine-tune pipeline.

  1. Run benchmark to find weak (model, category) pairs
  2. Generate teacher solutions for failed tasks
  3. Fine-tune student with Unsloth LoRA
  4. Re-install adapter into Ollama
  5. Re-benchmark — verify ELO improved

Requires:  pip install 'ollama-arena[finetune]'
Hardware:  CUDA GPU recommended (Unsloth)
"""
from ollama_arena import Arena
from ollama_arena.finetune import (
    analyze_weaknesses, build_training_dataset, save_jsonl,
    unsloth_train, UnslothConfig,
    build_modelfile, install_to_ollama,
)

# 0. Baseline benchmark
arena = Arena()
arena.run_tournament(
    models=["llama3.2:3b", "qwen2.5:7b"],
    category="coding", n_per_match=10,
)

# 1. Find weakest spots
weak = analyze_weaknesses("arena.db")
print("Weak spots:", weak[:5])

# 2. Pick worst case and build a teacher dataset
if not weak:
    print("No weak spots found — every model already wins ≥50%.")
    exit(0)

target  = weak[0]
student = target["model"]
weak_cat = target["category"]

dataset = build_training_dataset(
    weak_model=student, category=weak_cat,
    db_path="arena.db", n_tasks=30,
)
jsonl = save_jsonl(dataset, f"train_{student.replace(':','_')}.jsonl")
print(f"Built {len(dataset)} training pairs → {jsonl}")

# 3. Fine-tune via Unsloth LoRA
art = unsloth_train(jsonl, UnslothConfig(
    base_model="unsloth/llama-3.2-3b-instruct-bnb-4bit",
    epochs=2, save_gguf=True, quant_method="q4_k_m",
))
print("Artifacts:", art)

# 4. Install into Ollama
mf = build_modelfile(art["gguf_path"], "Modelfile.tuned")
new_name = f"{student}-tuned"
ok = install_to_ollama(mf, new_name)

# 5. Re-benchmark
if ok:
    print(f"\nRe-benchmarking {new_name}...")
    arena.run_match(new_name, "qwen2.5:7b", category=weak_cat, n=10)
    print("\nNew leaderboard:")
    for e in arena.leaderboard():
        print(f"  #{e['rank']} {e['model']:30s} ELO={e['elo']:.0f}")
