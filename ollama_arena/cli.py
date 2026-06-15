"""Command-line entry point. See `ollama-arena --help`."""
from __future__ import annotations
import argparse, sys
from pathlib import Path


def _console():
    try:
        from rich.console import Console
        return Console()
    except ImportError:
        print("Install rich first: pip install rich")
        sys.exit(1)


def _make_arena(args):
    from .arena import Arena
    return Arena(
        ollama_url = getattr(args, "ollama", "http://localhost:11434"),
        db_path    = args.db,
        backend    = getattr(args, "backend", None),
        api_key    = getattr(args, "api_key", None),
    )


# list
def cmd_list(args):
    console = _console()
    from rich.table import Table
    from .backends.auto import auto_backend
    backend = auto_backend(args.backend or args.ollama, api_key=args.api_key)

    if not backend.is_alive():
        console.print(f"[red]✗ Backend not reachable.[/red]")
        sys.exit(1)
    models = backend.list_models()
    if not models:
        console.print("[yellow]No models found.[/yellow]")
        return
    t = Table(title=f"Models on {backend.name}", show_lines=False)
    t.add_column("#", style="dim", width=4)
    t.add_column("Model", style="bold cyan")
    for i, m in enumerate(models, 1):
        t.add_row(str(i), m)
    console.print(t)


# leaderboard
def cmd_leaderboard(args):
    console = _console()
    from rich.table import Table
    from .elo import EloStore
    board = EloStore(db_path=args.db).leaderboard()
    if not board:
        console.print("[yellow]No matches yet.[/yellow]"); return
    t = Table(title="ELO Leaderboard", show_lines=False)
    t.add_column("rank",  style="bold yellow", width=6)
    t.add_column("model", style="bold cyan",   min_width=22)
    t.add_column("elo",   style="bold green",  justify="right")
    t.add_column("W",     style="green",       justify="right")
    t.add_column("L",     style="red",         justify="right")
    t.add_column("D",     style="dim",         justify="right")
    t.add_column("matches", justify="right")
    t.add_column("win%",    justify="right")
    for e in board:
        t.add_row(str(e["rank"]), e["model"], f"{e['elo']:.0f}",
                  str(e["wins"]), str(e["losses"]), str(e["draws"]),
                  str(e["matches"]), f"{e['win_rate']:.0%}")
    console.print(t)


# match
def cmd_match(args):
    console = _console()
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    models = [m.strip() for m in args.models.split(",")]
    if len(models) < 2:
        console.print("[red]--models needs at least 2 entries[/red]"); sys.exit(1)

    arena = _make_arena(args)
    if not arena.client.is_alive():
        console.print(f"[red]Backend not reachable.[/red]"); sys.exit(1)

    if args.dataset:
        for d in args.dataset.split(","):
            n = arena.load_hf_dataset(d.strip(), limit=args.dataset_limit)
            console.print(f"  loaded HF dataset '{d}': {n} tasks")

    from itertools import combinations
    pairs = list(combinations(models, 2))
    n = args.n
    category = args.category

    console.print(Panel(
        f"Backend : [yellow]{arena.client.name}[/yellow]\n"
        f"Models  : {', '.join(models)}\n"
        f"Category: [yellow]{category}[/yellow]   "
        f"Tasks/match: [yellow]{n}[/yellow]   DB: {args.db}",
        title="ollama-arena"))

    task_log = []
    def on_task(tid, sa, sb, outcome):
        marker = {"a_wins":"[green]A[/green]","b_wins":"[red]B[/red]","draw":"[dim]=[/dim]"}[outcome]
        task_log.append(f"  {marker}  {tid}: {sa:.2f} vs {sb:.2f}")
    arena._on_task_done = on_task

    for i, (ma, mb) in enumerate(pairs, 1):
        console.print(f"\n[bold]Match {i}/{len(pairs)}: [cyan]{ma}[/cyan] vs [magenta]{mb}[/magenta][/bold]")
        task_log.clear()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=True) as prog:
            tid = prog.add_task(f"Running {n} tasks...", total=None)
            r = arena.run_match(ma, mb, category=category, n=n,
                                difficulty=args.difficulty)
            prog.remove_task(tid)
        for ln in task_log:
            console.print(ln)
        winner = ma if r.a_wins > r.b_wins else mb if r.b_wins > r.a_wins else "draw"
        da = r.elo_a_after - r.elo_a_before
        db = r.elo_b_after - r.elo_b_before
        s = Table(show_header=False, box=None, padding=(0,2))
        s.add_column("", style="dim"); s.add_column("A", style="cyan", justify="right")
        s.add_column("B", style="magenta", justify="right")
        s.add_row("model", ma, mb)
        s.add_row("wins", str(r.a_wins), str(r.b_wins))
        s.add_row("win%", f"{r.a_win_rate:.0%}", f"{r.b_win_rate:.0%}")
        s.add_row("elo", f"{r.elo_a_after:.0f} ({da:+.0f})", f"{r.elo_b_after:.0f} ({db:+.0f})")
        console.print(s)
        console.print(f"  winner: [bold]{winner}[/bold]  ({r.duration_s:.0f}s)")

    console.print()
    cmd_leaderboard(args)


# tournament
def cmd_tournament(args):
    console = _console()
    models = [m.strip() for m in args.models.split(",")]
    if len(models) < 2:
        console.print("[red]--models needs at least 2 entries[/red]"); sys.exit(1)
    arena = _make_arena(args)
    if args.dataset:
        for d in args.dataset.split(","):
            arena.load_hf_dataset(d.strip(), limit=args.dataset_limit)
    console.print(f"Tournament: {len(models)} models, "
                  f"{args.n} tasks/match, category={args.category}")
    arena.run_tournament(models, category=args.category, n_per_match=args.n)
    cmd_leaderboard(args)


# tasks
def cmd_tasks(args):
    console = _console()
    from rich.table import Table
    from .tasks import task_stats, get_tasks, list_languages
    stats = task_stats()
    t = Table(title="Built-in benchmarks", show_lines=False)
    t.add_column("Category", style="bold cyan")
    t.add_column("Tasks", justify="right")
    t.add_column("Easy", justify="right", style="green")
    t.add_column("Medium", justify="right", style="yellow")
    t.add_column("Hard", justify="right", style="red")
    for cat, count in stats.items():
        tasks = get_tasks(category=cat)
        easy   = sum(1 for x in tasks if x.get("difficulty")=="easy")
        medium = sum(1 for x in tasks if x.get("difficulty")=="medium")
        hard   = sum(1 for x in tasks if x.get("difficulty")=="hard")
        t.add_row(cat, str(count), str(easy), str(medium), str(hard))
    t.add_section()
    t.add_row("[bold]Total[/bold]", f"[bold]{sum(stats.values())}[/bold]", "", "", "")
    console.print(t)
    console.print(f"\nLanguages covered: [cyan]{', '.join(list_languages())}[/cyan]")


# datasets
def cmd_datasets(args):
    console = _console()
    from rich.table import Table
    from .datasets import available_datasets, load_dataset, refresh_dataset

    if args.refresh:
        for name in args.refresh.split(","):
            n = refresh_dataset(name.strip(), limit=args.limit)
            console.print(f"  refreshed [cyan]{name}[/cyan]: {n} tasks")
        return

    if args.pull:
        for name in args.pull.split(","):
            tasks = load_dataset(name.strip(), limit=args.limit)
            console.print(f"  cached [cyan]{name}[/cyan]: {len(tasks)} tasks")
        return

    t = Table(title="HuggingFace benchmark datasets", show_lines=False)
    t.add_column("name", style="bold cyan")
    t.add_column("hf id", style="dim")
    t.add_column("category")
    t.add_column("cached", justify="right")
    t.add_column("license", style="dim")
    for d in available_datasets():
        cached = "yes" if d["cached"] else "—"
        t.add_row(d["name"], d["hf_id"], d["category"], cached, d["license"])
    console.print(t)
    console.print("\nPull:  [cyan]ollama-arena datasets --pull humaneval[/cyan]")


# finetune
def cmd_finetune(args):
    console = _console()
    from .finetune import (
        analyze_weaknesses, weakness_report,
        build_training_dataset, save_jsonl,
    )

    if args.analyze:
        rpt = weakness_report(args.db)
        console.print(rpt); return

    if args.generate:
        if not (args.model and args.category):
            console.print("[red]--model and --category required for --generate[/red]"); sys.exit(1)
        from .backends.auto import auto_backend
        backend = auto_backend(args.backend or args.ollama, api_key=args.api_key)
        ds = build_training_dataset(
            weak_model=args.model, category=args.category, db_path=args.db,
            teacher_model=args.teacher, backend=backend, n_tasks=args.n_tasks,
        )
        out = save_jsonl(ds, args.out or f"train_{args.model.replace(':','_')}.jsonl")
        console.print(f"  wrote {len(ds)} pairs → [cyan]{out}[/cyan]")
        return

    if args.train:
        from .finetune.unsloth_runner import unsloth_train, UnslothConfig
        cfg = UnslothConfig(base_model=args.base_model or "unsloth/llama-3.2-3b-instruct-bnb-4bit",
                            epochs=args.epochs, output_dir=args.out_dir or "outputs/lora")
        out = unsloth_train(args.train, cfg)
        console.print(f"  training done: {out}")
        return

    console.print("Pass one of: --analyze | --generate | --train")


# perf
def cmd_perf(args):
    console = _console()
    from rich.table import Table
    from .performance import PerfTracker
    stats = PerfTracker(args.db).stats()
    if not stats:
        console.print("[yellow]No performance data yet.[/yellow]"); return
    t = Table(title="Performance (per model)", show_lines=False)
    t.add_column("Model", style="bold cyan")
    t.add_column("Samples", justify="right")
    t.add_column("TPS mean", style="green", justify="right")
    t.add_column("TPS p95", style="green", justify="right")
    t.add_column("Latency mean (s)", style="yellow", justify="right")
    t.add_column("Latency p95 (s)", style="yellow", justify="right")
    t.add_column("TTFT (s)", style="dim", justify="right")
    for s in stats:
        t.add_row(s["model"], str(s["n_samples"]),
                  f"{s['tps_mean']:.1f}", f"{s['tps_p95']:.1f}",
                  f"{s['latency_mean_s']:.2f}", f"{s['latency_p95_s']:.2f}",
                  f"{s['ttft_mean_s']:.2f}")
    console.print(t)


# export
def cmd_export(args):
    console = _console()
    from .elo import EloStore
    from .performance import PerfTracker
    from .visualize import export_dashboard
    from .tasks import list_categories

    store = EloStore(args.db)
    leaderboard = store.leaderboard()
    matches = store.match_history(limit=1000)
    perf = PerfTracker(args.db).stats()

    out = export_dashboard(
        args.out, leaderboard=leaderboard, matches=matches,
        categories=list_categories(), performance=perf,
    )
    console.print(f"  dashboard exported → [cyan]{out}[/cyan]")
    console.print(f"     open file://{Path(out).absolute()}")


# web
def cmd_web(args):
    from .web import run_web
    run_web(host=args.host, port=args.port,
            ollama_url=args.ollama, db_path=args.db,
            backend=args.backend, api_key=args.api_key)


# main
def main():
    p = argparse.ArgumentParser(
        prog="ollama-arena",
        description="Local LLM ELO Arena — benchmark Ollama / vLLM / LM Studio / "
                    "llama.cpp / OpenAI-compat with auto-scored battles.",
    )
    p.add_argument("--ollama", default="http://localhost:11434", metavar="URL")
    p.add_argument("--backend", default=None, metavar="URL|PRESET",
                   help="vllm, lmstudio, llamacpp, openai, groq, together, openrouter,"
                        " or any URL with /v1/chat/completions")
    p.add_argument("--api-key", default=None, metavar="KEY")
    p.add_argument("--db",      default="arena.db", metavar="PATH")
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    def add_common(parser):
        parser.add_argument("--dataset", default=None,
                            help="HF datasets to load (comma-sep): humaneval,mbpp,gsm8k,mmlu,...")
        parser.add_argument("--dataset-limit", type=int, default=None)

    pm = sub.add_parser("match", help="Head-to-head battle(s)")
    pm.add_argument("--models", required=True, metavar="A,B[,C...]")
    pm.add_argument("--category", default="coding",
                    choices=["coding","reasoning","security","planning",
                              "inspection","math","knowledge","all"])
    pm.add_argument("--difficulty", default=None,
                    choices=["easy","medium","hard"])
    pm.add_argument("-n", type=int, default=10)
    add_common(pm)
    pm.set_defaults(func=cmd_match)

    pt = sub.add_parser("tournament", help="Round-robin tournament")
    pt.add_argument("--models", required=True)
    pt.add_argument("--category", default="coding")
    pt.add_argument("-n", type=int, default=5)
    add_common(pt)
    pt.set_defaults(func=cmd_tournament)

    sub.add_parser("leaderboard", aliases=["lb"]).set_defaults(func=cmd_leaderboard)
    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("tasks").set_defaults(func=cmd_tasks)

    pd = sub.add_parser("datasets", help="HF dataset cache (pull / refresh)")
    pd.add_argument("--pull",    default=None, help="Comma-sep names to download")
    pd.add_argument("--refresh", default=None, help="Comma-sep names to re-download")
    pd.add_argument("--limit",   type=int, default=None)
    pd.set_defaults(func=cmd_datasets)

    pft = sub.add_parser("finetune", help="Unsloth pipeline (analyze/generate/train)")
    pft.add_argument("--analyze",  action="store_true")
    pft.add_argument("--generate", action="store_true")
    pft.add_argument("--train",    default=None, metavar="JSONL_PATH")
    pft.add_argument("--model",    default=None, help="Weak model name (student)")
    pft.add_argument("--teacher",  default=None, help="Strong model name (teacher)")
    pft.add_argument("--category", default="coding")
    pft.add_argument("--out",      default=None)
    pft.add_argument("--out-dir",  default=None)
    pft.add_argument("--n-tasks",  type=int, default=50)
    pft.add_argument("--base-model", default=None)
    pft.add_argument("--epochs",   type=int, default=2)
    pft.set_defaults(func=cmd_finetune)

    sub.add_parser("perf", help="Performance stats").set_defaults(func=cmd_perf)

    pex = sub.add_parser("export", help="Export shareable HTML dashboard")
    pex.add_argument("--out", default="arena_dashboard.html")
    pex.set_defaults(func=cmd_export)

    pw = sub.add_parser("web", help="Launch web dashboard")
    pw.add_argument("--host", default="0.0.0.0")
    pw.add_argument("--port", type=int, default=7860)
    pw.set_defaults(func=cmd_web)

    args = p.parse_args()
    if not args.cmd:
        from . import __version__
        from ._banner import print_banner
        print_banner(__version__)
        p.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
