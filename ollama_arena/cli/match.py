"""Command-line match.py commands. See `ollama-arena --help`."""
from __future__ import annotations

import sys
from itertools import combinations

from .data import cmd_leaderboard

from .common import (
    _console, _make_arena, _outcome_icon, _trunc, _wrap,
    _print_task_detail,
)


_BENCHMARK_TASKS_PER_CAT = 6  # 6 tasks × 5 categories = 30 total

def cmd_match(args):
    console = _console()
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.rule import Rule

    verbose = getattr(args, "verbose", False)
    models = [m.strip() for m in args.models.split(",")]
    if len(models) < 2:
        console.print("[red]--models needs at least 2 entries[/red]"); sys.exit(1)

    arena = _make_arena(args)
    if not arena.client.is_alive():
        console.print("[red]✗ Backend not reachable.[/red]"); sys.exit(1)

    if args.dataset:
        for d in args.dataset.split(","):
            n = arena.load_hf_dataset(d.strip(), limit=args.dataset_limit)
            console.print(f"  loaded [cyan]{d}[/cyan]: {n} tasks")

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

    def on_task(tid, sa, sb, outcome, instruction, resp_a, resp_b, expected):
        icon = _outcome_icon(outcome)
        task_log.append((tid, sa, sb, outcome, instruction, resp_a, resp_b, expected))
        # always print one-liner
        console.print(
            f"  {icon}  [dim]{tid}[/dim]  "
            f"[cyan]{sa:.2f}[/cyan] vs [magenta]{sb:.2f}[/magenta]  "
            f"[dim]{_trunc(instruction, 60)}[/dim]"
        )
        if verbose:
            _print_task_detail(console, tid, sa, sb, outcome,
                               instruction, resp_a, resp_b, expected, "", "")

    arena._on_task_done = on_task

    for i, (ma, mb) in enumerate(pairs, 1):
        console.print(Rule(
            f"[bold]Match {i}/{len(pairs)}: [cyan]{ma}[/cyan] vs [magenta]{mb}[/magenta][/bold]"
        ))
        task_log.clear()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=True) as prog:
            tid = prog.add_task(f"Generating…", total=None)
            r = arena.run_match(ma, mb, category=category, n=n,
                                difficulty=args.difficulty,
                                use_tools=getattr(args, "tools", False))
            prog.remove_task(tid)

        winner = ma if r.a_wins > r.b_wins else mb if r.b_wins > r.a_wins else "draw"
        da = r.elo_a_after - r.elo_a_before
        db_ = r.elo_b_after - r.elo_b_before
        s = Table(show_header=False, box=None, padding=(0, 2))
        s.add_column("", style="dim"); s.add_column("A", style="cyan", justify="right")
        s.add_column("B", style="magenta", justify="right")
        s.add_row("model",  ma, mb)
        s.add_row("wins",   str(r.a_wins), str(r.b_wins))
        s.add_row("win%",   f"{r.a_win_rate:.0%}", f"{r.b_win_rate:.0%}")
        s.add_row("elo",    f"{r.elo_a_after:.0f} ({da:+.0f})",
                            f"{r.elo_b_after:.0f} ({db_:+.0f})")
        console.print(s)
        console.print(f"  winner: [bold]{winner}[/bold]  ({r.duration_s:.0f}s)  "
                      f"match #{r.match_id}")
        if not verbose and task_log:
            console.print(
                f"\n  [dim]Run with [bold]--verbose[/bold] to see all prompts & responses, "
                f"or: [bold]ollama-arena results --match {r.match_id}[/bold][/dim]"
            )

    console.print()
    cmd_leaderboard(args)

    if getattr(args, "share", False):
        _print_share_table(console, arena, models, pairs)

def _print_share_table(console, arena, models, pairs):
    from rich.rule import Rule
    board = {e["model"]: e for e in arena.leaderboard()}
    cats = sorted({r["category"] for r in arena.elo.match_history(limit=500)
                   if r["model_a"] in models or r["model_b"] in models})
    if not cats:
        cats = ["overall"]

    lines = []
    lines.append("")
    lines.append("---")
    lines.append("")
    if len(models) == 2:
        lines.append(f"## Benchmark results: {models[0]} vs {models[1]}")
    else:
        lines.append(f"## Benchmark results: {', '.join(models)}")
    lines.append("")

    header = "| Category |" + "".join(f" {m} |" for m in models)
    sep    = "|----------|" + "".join(" --------- |" for _ in models)
    lines.append(header)
    lines.append(sep)

    for cat in cats:
        cat_stats = {m: arena.elo.category_stats(m) for m in models}
        row = f"| {cat} |"
        best_wr = max(
            (next((s["win_rate"] for s in cat_stats[m] if s["category"] == cat), 0.0)
             for m in models), default=0.0
        )
        for m in models:
            wr = next((s["win_rate"] for s in cat_stats[m] if s["category"] == cat), None)
            if wr is None:
                row += " — |"
            elif wr == best_wr and best_wr > 0:
                row += f" **{wr:.0%}** ✓ |"
            else:
                row += f" {wr:.0%} |"
        lines.append(row)

    elo_row = "| ELO |"
    best_elo = max((board.get(m, {}).get("elo", 1200) for m in models), default=1200)
    for m in models:
        elo = board.get(m, {}).get("elo", 1200)
        if elo == best_elo:
            elo_row += f" **{elo:.0f}** ✓ |"
        else:
            elo_row += f" {elo:.0f} |"
    lines.append(elo_row)
    lines.append("")
    lines.append("*Generated by [ollama-arena](https://github.com/nazkari86-lab/ollama-arena)*")
    lines.append("")
    lines.append("---")

    output = "\n".join(lines)
    console.print()
    console.print(Rule("[bold]Shareable Markdown[/bold]"))
    console.print(output)
    console.print(Rule())
    console.print("[dim]Copy the block above and paste into GitHub, HN, or Reddit.[/dim]")


# ── benchmark ────────────────────────────────────────────────────────────────
_BENCHMARK_TASKS_PER_CAT = 6  # 6 tasks × 5 categories = 30 total

def cmd_benchmark(args):
    """Run a standardized 30-task benchmark and return a 0–100 Score."""
    console = _console()
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.rule import Rule
    from ..tasks import get_tasks, list_categories

    models = [m.strip() for m in args.models.split(",")]
    arena = _make_arena(args)
    if not arena.client.is_alive():
        console.print("[red]✗ Backend not reachable.[/red]"); sys.exit(1)

    categories = ["coding", "reasoning", "math", "knowledge", "security", "planning", "inspection"]
    n_per_cat = _BENCHMARK_TASKS_PER_CAT

    console.print(Panel(
        f"Running standardized benchmark  ({len(categories)} categories × {n_per_cat} tasks = "
        f"{len(categories) * n_per_cat} tasks total)\n"
        f"Models: [cyan]{', '.join(models)}[/cyan]",
        title="ollama-arena benchmark"))

    if not arena.judge and ("creative" in categories or "all" in categories):
        console.print("[yellow]⚠ Warning: 'creative' category included but no judge model is provided.[/yellow]")
        console.print("[dim]Creative tasks will be skipped as they require an LLM judge for scoring.[/dim]\n")

    results: dict[str, dict[str, list[float]]] = {m: {} for m in models}

    total_tasks = len(models) * len(categories) * n_per_cat
    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  BarColumn(), TaskProgressColumn(),
                  console=console) as prog:
        task_bar = prog.add_task("Benchmarking…", total=total_tasks)

        for cat in categories:
            tasks = list(get_tasks(category=cat))[:n_per_cat]
            for model in models:
                scores = []
                for task in tasks:
                    res = arena.client.generate(model, task["instruction"])
                    from ..evaluator import evaluate
                    score = evaluate(task, res.text) if res.ok else 0.0
                    
                    if score is not None:
                        scores.append(score)
                    prog.advance(task_bar)
                results[model][cat] = scores

    console.print()

    # Build score table
    t = Table(title="Benchmark Results", show_lines=True)
    t.add_column("Model", style="bold cyan", min_width=22)
    for cat in categories:
        t.add_column(cat.capitalize(), justify="right")
    t.add_column("SCORE", style="bold green", justify="right")

    scores_summary = {}
    for model in models:
        cat_scores = {}
        for cat in categories:
            cat_results = results[model][cat]
            cat_scores[cat] = round(sum(cat_results) / len(cat_results) * 100, 1) if cat_results else 0.0
        total_score = round(sum(cat_scores.values()) / len(cat_scores), 1) if cat_scores else 0.0
        scores_summary[model] = {"by_category": cat_scores, "total": total_score}

        row = [model] + [f"{cat_scores[c]:.0f}" for c in categories] + [f"{total_score:.1f}"]
        t.add_row(*row)

    console.print(t)

    # Save to DB
    for model in models:
        arena.elo.save_benchmark(
            model=model,
            score=scores_summary[model]["total"],
            scores_by_category=scores_summary[model]["by_category"],
            n_tasks=len(categories) * n_per_cat,
        )

    # Print score cards
    console.print()
    for model in models:
        s = scores_summary[model]
        cat_str = "  ".join(f"{c[:4]}:{v:.0f}" for c, v in s["by_category"].items())
        console.print(
            f"  [bold cyan]{model}[/bold cyan]  "
            f"[bold green]Score: {s['total']:.1f} / 100[/bold green]  "
            f"[dim]({cat_str})[/dim]"
        )

    if args.compare and len(models) == 2:
        a, b = models
        diff = scores_summary[a]["total"] - scores_summary[b]["total"]
        winner = a if diff > 0 else b
        console.print(f"\n  Winner: [bold]{winner}[/bold]  (margin: {abs(diff):.1f} pts)")

    # --fail-below
    if args.fail_below is not None:
        for model in models:
            if scores_summary[model]["total"] < args.fail_below:
                console.print(
                    f"\n[red]✗ {model} scored {scores_summary[model]['total']:.1f} "
                    f"< threshold {args.fail_below}[/red]"
                )
                sys.exit(1)
        console.print(f"\n[green]✓ All models above threshold {args.fail_below}[/green]")


# ── tournament ────────────────────────────────────────────────────────────────

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


# ── royale ───────────────────────────────────────────────────────────────────

def cmd_royale(args):
    """N-way Battle Royale: all models fight on the same tasks simultaneously."""
    console = _console()
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.rule import Rule

    models = [m.strip() for m in args.models.split(",")]
    if len(models) < 3:
        console.print("[red]Battle Royale requires at least 3 models (found {len(models)})[/red]")
        sys.exit(1)

    arena = _make_arena(args)
    if not arena.client.is_alive():
        console.print("[red]✗ Backend not reachable.[/red]"); sys.exit(1)

    n = args.n
    category = args.category

    console.print(Panel(
        f"Battle Royale (N-way Match)\n"
        f"Models  : {', '.join(models)}\n"
        f"Category: [yellow]{category}[/yellow]   Tasks: [yellow]{n}[/yellow]",
        title="ollama-arena royale"))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as prog:
        prog.add_task(f"Generating responses for all {len(models)} models…", total=None)
        r = arena.run_royale(models, category=category, n=n, difficulty=args.difficulty)

    console.print(Rule(f"[bold]Final Rankings: {category}[/bold]"))
    
    t = Table(show_lines=True)
    t.add_column("Rank", style="bold yellow", width=6)
    t.add_column("Model", style="bold cyan", min_width=22)
    t.add_column("Score", justify="right")
    t.add_column("ELO", style="bold green", justify="right")
    
    for entry in r.rankings:
        t.add_row(
            str(entry["rank"]),
            entry["model"],
            f"{entry['total_score']:.2f}",
            f"{entry['elo_after']:.0f}"
        )
    
    console.print(t)
    console.print(f"\n  Winner: [bold green]🏆 {r.winner}[/bold green]  ({r.duration_s:.0f}s)  royale #{r.royale_id}")
    console.print(f"  Strategy: [dim]{r.strategy}[/dim]")
    
    # Auto-export royale report
    from ..visualize import export_royale_report
    # We need to fetch the entries we just saved
    entries = arena.elo.royale_entries(r.royale_id)
    if entries:
        out = export_royale_report(r.royale_id, category, models, entries)
        console.print(f"  [green]✓ Royale report exported to: [bold]{out}[/bold][/green]")
    
    console.print()
    cmd_leaderboard(args)


# ── council ──────────────────────────────────────────────────────────────────
