"""Finetune pipeline CLI commands."""
from __future__ import annotations

import sys
from pathlib import Path

from .common import _console


def cmd_finetune(args):
    console = _console()
    from ..finetune import (
        analyze_weaknesses,
        weakness_report,
        task_failure_report,
        build_training_dataset,
        build_dpo_dataset,
        save_jsonl,
        unsloth_train,
        UnslothConfig,
        build_modelfile,
        install_to_ollama,
    )

    if getattr(args, "run", False):
        if not (args.model and args.category):
            console.print("[red]--run requires --model and --category[/red]")
            sys.exit(1)
        console.print(f"[bold]Finetune pipeline[/bold] model={args.model} category={args.category}")
        console.print(task_failure_report(args.db, model=args.model, category=args.category))
        weak = analyze_weaknesses(args.db)
        cat_weak = [w for w in weak if w["model"] == args.model and w["category"] == args.category]
        if cat_weak:
            console.print(
                f"  match-level win rate: {cat_weak[0]['win_rate']:.0%} "
                f"({cat_weak[0]['samples']} samples)"
            )

        from ..backends.auto import auto_backend
        backend = auto_backend(args.backend or args.ollama, api_key=args.api_key)

        fmt = getattr(args, "format", "sft")
        if fmt == "dpo":
            ds = build_dpo_dataset(
                weak_model=args.model, category=args.category, db_path=args.db,
                teacher_model=args.teacher, backend=backend, n_tasks=args.n_tasks,
            )
            jsonl = save_jsonl(ds, args.out or f"dpo_{args.model.replace(':', '_')}.jsonl")
        else:
            ds = build_training_dataset(
                weak_model=args.model, category=args.category, db_path=args.db,
                teacher_model=args.teacher, backend=backend, n_tasks=args.n_tasks,
            )
            jsonl = save_jsonl(ds, args.out or f"train_{args.model.replace(':', '_')}.jsonl")
        console.print(f"  generated {len(ds)} records → [cyan]{jsonl}[/cyan]")

        if getattr(args, "skip_train", False):
            return

        cfg = UnslothConfig(
            base_model=args.base_model or "unsloth/llama-3.2-3b-instruct-bnb-4bit",
            epochs=args.epochs,
            output_dir=args.out_dir or "outputs/lora",
        )
        artifacts = unsloth_train(jsonl, cfg)
        console.print(f"  training done: {artifacts}")

        if getattr(args, "skip_export", False):
            return

        gguf = artifacts.get("gguf_path")
        if gguf and Path(gguf).exists():
            mf = build_modelfile(gguf, out_path=str(Path(args.out_dir or "outputs/lora") / "Modelfile"))
            ollama_name = args.ollama_name or f"{args.model}-finetuned"
            if install_to_ollama(mf, ollama_name):
                console.print(f"  exported to Ollama model [green]{ollama_name}[/green]")
        return

    if args.analyze:
        console.print(weakness_report(args.db))
        if args.model:
            console.print()
            console.print(task_failure_report(args.db, model=args.model, category=args.category))
        return

    if args.generate:
        if not (args.model and args.category):
            console.print("[red]--model and --category required for --generate[/red]")
            sys.exit(1)
        from ..backends.auto import auto_backend
        backend = auto_backend(args.backend or args.ollama, api_key=args.api_key)
        if getattr(args, "format", "sft") == "dpo":
            ds = build_dpo_dataset(
                weak_model=args.model, category=args.category, db_path=args.db,
                teacher_model=args.teacher, backend=backend, n_tasks=args.n_tasks,
            )
            out = save_jsonl(ds, args.out or f"dpo_{args.model.replace(':', '_')}.jsonl")
        else:
            ds = build_training_dataset(
                weak_model=args.model, category=args.category, db_path=args.db,
                teacher_model=args.teacher, backend=backend, n_tasks=args.n_tasks,
            )
            out = save_jsonl(ds, args.out or f"train_{args.model.replace(':', '_')}.jsonl")
        console.print(f"  wrote {len(ds)} pairs → [cyan]{out}[/cyan]")
        return

    if args.train:
        cfg = UnslothConfig(
            base_model=args.base_model or "unsloth/llama-3.2-3b-instruct-bnb-4bit",
            epochs=args.epochs,
            output_dir=args.out_dir or "outputs/lora",
        )
        out = unsloth_train(args.train, cfg)
        console.print(f"  training done: {out}")
        return

    console.print("Pass one of: --run | --analyze | --generate | --train")
