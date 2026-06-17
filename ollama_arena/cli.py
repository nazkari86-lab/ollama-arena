"""Command-line entry point. See `ollama-arena --help`."""
from __future__ import annotations
import argparse, sys, textwrap, time
from datetime import datetime
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


def _outcome_icon(outcome: str) -> str:
    return {"a_wins": "[green]✓ A[/green]",
            "b_wins": "[red]✓ B[/red]",
            "draw":   "[dim]  =[/dim]"}[outcome]


def _wrap(text: str, width: int = 90) -> str:
    if not text:
        return "[dim](empty)[/dim]"
    lines = text.strip().splitlines()
    out = []
    for ln in lines[:6]:
        out.append(textwrap.shorten(ln, width=width, placeholder="…"))
    if len(lines) > 6:
        out.append(f"[dim]… ({len(lines)-6} more lines)[/dim]")
    return "\n".join(out)


def _trunc(text: str, n: int = 120) -> str:
    text = text.strip()
    return text[:n] + "…" if len(text) > n else text


# ── list ─────────────────────────────────────────────────────────────────────
def cmd_list(args):
    console = _console()
    from rich.table import Table
    from .backends.auto import auto_backend
    backend = auto_backend(args.backend or args.ollama, api_key=args.api_key)

    if not backend.is_alive():
        console.print("[red]✗ Backend not reachable.[/red]")
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


# ── leaderboard ──────────────────────────────────────────────────────────────
def cmd_leaderboard(args):
    console = _console()
    from rich.table import Table
    from .elo import EloStore
    board = EloStore(db_path=args.db).leaderboard()
    if not board:
        console.print("[yellow]No matches yet.[/yellow]"); return
    t = Table(title="ELO Leaderboard", show_lines=False)
    t.add_column("rank",    style="bold yellow", width=6)
    t.add_column("model",   style="bold cyan",   min_width=22)
    t.add_column("elo",     style="bold green",  justify="right")
    t.add_column("W",       style="green",       justify="right")
    t.add_column("L",       style="red",         justify="right")
    t.add_column("D",       style="dim",         justify="right")
    t.add_column("matches", justify="right")
    t.add_column("win%",    justify="right")
    for e in board:
        t.add_row(str(e["rank"]), e["model"], f"{e['elo']:.0f}",
                  str(e["wins"]), str(e["losses"]), str(e["draws"]),
                  str(e["matches"]), f"{e['win_rate']:.0%}")
    console.print(t)


# ── match ─────────────────────────────────────────────────────────────────────
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
                                difficulty=args.difficulty)
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
    from .tasks import get_tasks, list_categories

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
                    from .evaluator import evaluate
                    score = evaluate(task, res.text) if res.ok else 0.0
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
            cat_scores[cat] = round(sum(results[model][cat]) / len(results[model][cat]) * 100, 1)
        total_score = round(sum(cat_scores.values()) / len(cat_scores), 1)
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


# ── tasks ─────────────────────────────────────────────────────────────────────
def cmd_tasks(args):
    console = _console()
    from rich.table import Table
    from .tasks import task_stats, get_tasks, list_languages
    stats = task_stats()
    t = Table(title="Built-in benchmarks", show_lines=False)
    t.add_column("Category", style="bold cyan")
    t.add_column("Tasks",  justify="right")
    t.add_column("Easy",   justify="right", style="green")
    t.add_column("Medium", justify="right", style="yellow")
    t.add_column("Hard",   justify="right", style="red")
    for cat, count in stats.items():
        tasks = get_tasks(category=cat)
        easy   = sum(1 for x in tasks if x.get("difficulty") == "easy")
        medium = sum(1 for x in tasks if x.get("difficulty") == "medium")
        hard   = sum(1 for x in tasks if x.get("difficulty") == "hard")
        t.add_row(cat, str(count), str(easy), str(medium), str(hard))
    t.add_section()
    t.add_row("[bold]Total[/bold]", f"[bold]{sum(stats.values())}[/bold]", "", "", "")
    console.print(t)
    console.print(f"\nLanguages covered: [cyan]{', '.join(list_languages())}[/cyan]")


# ── datasets ──────────────────────────────────────────────────────────────────
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
    t.add_column("name",     style="bold cyan")
    t.add_column("hf id",    style="dim")
    t.add_column("category")
    t.add_column("cached",   justify="right")
    t.add_column("license",  style="dim")
    for d in available_datasets():
        cached = "yes" if d["cached"] else "—"
        t.add_row(d["name"], d["hf_id"], d["category"], cached, d["license"])
    console.print(t)
    console.print("\nPull:  [cyan]ollama-arena datasets --pull humaneval[/cyan]")


# ── results ───────────────────────────────────────────────────────────────────
def cmd_results(args):
    """Show recent matches with per-task breakdowns."""
    console = _console()
    from rich.table import Table
    from rich.rule import Rule
    from rich.panel import Panel
    from .elo import EloStore

    store = EloStore(db_path=args.db)

    if args.match:
        _show_match_detail(console, store, args.match, args.full)
        return

    # List recent matches
    matches = store.recent_matches_summary(limit=args.last)
    if not matches:
        console.print("[yellow]No matches recorded yet.[/yellow]"); return

    t = Table(title=f"Last {len(matches)} matches", show_lines=False)
    t.add_column("ID",       style="dim", width=5)
    t.add_column("Model A",  style="cyan", min_width=18)
    t.add_column("Model B",  style="magenta", min_width=18)
    t.add_column("Category", style="yellow")
    t.add_column("Tasks",    justify="right")
    t.add_column("A wins",   style="green",  justify="right")
    t.add_column("B wins",   style="red",    justify="right")
    t.add_column("Draws",    style="dim",    justify="right")
    t.add_column("Winner",   style="bold")
    t.add_column("Date")
    for m in matches:
        dt = datetime.fromtimestamp(m["ts"]).strftime("%m-%d %H:%M")
        t.add_row(str(m["id"]), m["model_a"], m["model_b"], m["category"],
                  str(m["tasks"]), str(m["a_wins"]), str(m["b_wins"]),
                  str(m["draws"]), m["winner"], dt)
    console.print(t)
    console.print("\nDrill into a match: [cyan]ollama-arena results --match <ID>[/cyan]")
    console.print("Full responses:     [cyan]ollama-arena results --match <ID> --full[/cyan]")


def _show_match_detail(console, store, match_id: int, full: bool = False):
    from rich.rule import Rule
    from rich.panel import Panel

    tasks = store.tasks_for_match(match_id)
    if not tasks:
        console.print(f"[red]Match #{match_id} not found or has no task detail.[/red]")
        console.print("[dim]Matches run before v2.2.0 were not stored at task level.[/dim]")
        return

    history = store.match_history(limit=200)
    info = next((m for m in history if m["id"] == match_id), None)
    if info:
        console.print(Rule(
            f"[bold]Match #{match_id}: [cyan]{info['model_a']}[/cyan] vs "
            f"[magenta]{info['model_b']}[/magenta]  [{info['category']}][/bold]"
        ))

    for i, t in enumerate(tasks, 1):
        _print_task_detail(
            console, t["task_id"], t["score_a"], t["score_b"], t["outcome"],
            t["instruction"], t["response_a"], t["response_b"], t["expected"],
            info["model_a"] if info else "A", info["model_b"] if info else "B",
            i, len(tasks), full,
            tps_a=t["tps_a"], tps_b=t["tps_b"],
            latency_a=t["latency_a"], latency_b=t["latency_b"],
            difficulty=t["difficulty"], language=t["language"],
        )


def _print_task_detail(
    console, task_id, score_a, score_b, outcome,
    instruction, resp_a, resp_b, expected,
    model_a, model_b, i=None, total=None, full=False,
    tps_a=0.0, tps_b=0.0, latency_a=0.0, latency_b=0.0,
    difficulty="", language="",
):
    from rich.panel import Panel
    from rich.columns import Columns

    icon = _outcome_icon(outcome)
    header = f"{icon}  [bold]{task_id}[/bold]"
    if i and total:
        header = f"[dim]{i}/{total}[/dim]  " + header
    meta = []
    if difficulty:
        col = {"easy": "green", "medium": "yellow", "hard": "red"}.get(difficulty, "dim")
        meta.append(f"[{col}]{difficulty}[/{col}]")
    if language and language != "natural":
        meta.append(f"[blue]{language}[/blue]")
    if meta:
        header += "  " + "  ".join(meta)

    console.print()
    console.print(header)
    console.print(f"  [dim]Score:[/dim]  "
                  f"[cyan]{model_a or 'A'}[/cyan] [bold]{score_a:.3f}[/bold]  "
                  f"[magenta]{model_b or 'B'}[/magenta] [bold]{score_b:.3f}[/bold]")
    if tps_a or tps_b:
        console.print(f"  [dim]Speed:[/dim]  "
                      f"[cyan]{tps_a:.0f} tps  {latency_a:.2f}s[/cyan]  "
                      f"[magenta]{tps_b:.0f} tps  {latency_b:.2f}s[/magenta]")

    # Prompt
    instr_display = instruction if full else _wrap(instruction, 100)
    console.print(Panel(instr_display, title="[dim]Prompt[/dim]", border_style="dim",
                        padding=(0, 1)))

    # Responses
    if full:
        ra_disp = resp_a or "[dim](empty)[/dim]"
        rb_disp = resp_b or "[dim](empty)[/dim]"
    else:
        ra_disp = _wrap(resp_a, 100)
        rb_disp = _wrap(resp_b, 100)

    ra_color = "green" if score_a > score_b else ("red" if score_a < score_b else "dim")
    rb_color = "green" if score_b > score_a else ("red" if score_b < score_a else "dim")

    console.print(Panel(ra_disp,
                        title=f"[{ra_color}]{model_a or 'Model A'} ({score_a:.3f})[/{ra_color}]",
                        border_style=ra_color, padding=(0, 1)))
    console.print(Panel(rb_disp,
                        title=f"[{rb_color}]{model_b or 'Model B'} ({score_b:.3f})[/{rb_color}]",
                        border_style=rb_color, padding=(0, 1)))

    if expected:
        exp_disp = expected if full else _trunc(expected, 200)
        console.print(f"  [dim]Expected:[/dim] [yellow]{exp_disp}[/yellow]")


# ── inspect ───────────────────────────────────────────────────────────────────
def cmd_inspect(args):
    """Show all recorded runs for a specific task ID."""
    console = _console()
    from rich.table import Table
    from rich.rule import Rule
    from .elo import EloStore

    store = EloStore(db_path=args.db)
    history = store.task_history(args.task_id)
    if not history:
        console.print(f"[yellow]No history for task '{args.task_id}'.[/yellow]")
        return

    console.print(Rule(f"[bold]Task: {args.task_id}[/bold]"))

    # Show the prompt once
    console.print(Panel(
        history[0]["instruction"],
        title="[dim]Prompt[/dim]", border_style="dim", padding=(0, 1)
    ))
    if history[0]["expected"]:
        console.print(f"  [dim]Expected:[/dim] [yellow]{history[0]['expected']}[/yellow]")

    console.print()
    t = Table(title=f"All runs ({len(history)} total)", show_lines=False)
    t.add_column("Model A",  style="cyan")
    t.add_column("Model B",  style="magenta")
    t.add_column("A score",  justify="right", style="cyan")
    t.add_column("B score",  justify="right", style="magenta")
    t.add_column("Outcome",  justify="center")
    t.add_column("Date",     style="dim")
    for h in history:
        dt = datetime.fromtimestamp(h["ts"]).strftime("%Y-%m-%d %H:%M")
        icon = {"a_wins": "A ✓", "b_wins": "B ✓", "draw": "="}.get(h["outcome"], h["outcome"])
        t.add_row(h["model_a"], h["model_b"],
                  f"{h['score_a']:.3f}", f"{h['score_b']:.3f}",
                  icon, dt)
    console.print(t)

    if args.full:
        for h in history:
            dt = datetime.fromtimestamp(h["ts"]).strftime("%Y-%m-%d %H:%M")
            console.print(Rule(f"[dim]{h['model_a']} vs {h['model_b']} — {dt}[/dim]"))
            console.print(Panel(h["response_a"],
                                title=f"[cyan]{h['model_a']} ({h['score_a']:.3f})[/cyan]",
                                border_style="cyan", padding=(0, 1)))
            console.print(Panel(h["response_b"],
                                title=f"[magenta]{h['model_b']} ({h['score_b']:.3f})[/magenta]",
                                border_style="magenta", padding=(0, 1)))


# ── report ────────────────────────────────────────────────────────────────────
def cmd_report(args):
    """Per-model breakdown by category, difficulty, strengths/weaknesses."""
    console = _console()
    from rich.table import Table
    from rich.rule import Rule
    from .elo import EloStore

    store = EloStore(db_path=args.db)
    board = store.leaderboard()
    if not board:
        console.print("[yellow]No data yet.[/yellow]"); return

    models = [e["model"] for e in board]
    if args.model:
        models = [m for m in models if args.model.lower() in m.lower()]
        if not models:
            console.print(f"[red]No model matching '{args.model}'[/red]"); return

    for model in models:
        stats = store.category_stats(model)
        if not stats:
            continue

        console.print(Rule(f"[bold cyan]{model}[/bold cyan]"))

        elo_entry = next((e for e in board if e["model"] == model), None)
        if elo_entry:
            console.print(
                f"  ELO [bold green]{elo_entry['elo']:.0f}[/bold green]  "
                f"rank #{elo_entry['rank']}  "
                f"{elo_entry['wins']}W / {elo_entry['losses']}L / {elo_entry['draws']}D  "
                f"({elo_entry['win_rate']:.0%} win rate)"
            )

        t = Table(show_lines=False, padding=(0, 2))
        t.add_column("Category",  style="bold")
        t.add_column("Tasks",     justify="right")
        t.add_column("Won",       style="green",  justify="right")
        t.add_column("Lost",      style="red",    justify="right")
        t.add_column("Draw",      style="dim",    justify="right")
        t.add_column("Win rate",  justify="right")
        t.add_column("Verdict",   style="dim")

        strengths, weaknesses = [], []
        for s in stats:
            wr = s["win_rate"]
            bar = "█" * int(wr * 10) + "░" * (10 - int(wr * 10))
            if wr >= 0.6:
                verdict = "[green]strong[/green]"
                strengths.append(s["category"])
            elif wr <= 0.35:
                verdict = "[red]weak[/red]"
                weaknesses.append(s["category"])
            else:
                verdict = "[yellow]average[/yellow]"
            t.add_row(s["category"], str(s["total"]),
                      str(s["wins"]), str(s["losses"]), str(s["draws"]),
                      f"{wr:.0%} {bar}", verdict)
        console.print(t)

        if strengths:
            console.print(f"  Strengths:  [green]{', '.join(strengths)}[/green]")
        if weaknesses:
            console.print(f"  Weaknesses: [red]{', '.join(weaknesses)}[/red]")
        console.print()


# ── finetune ──────────────────────────────────────────────────────────────────
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


# ── perf ──────────────────────────────────────────────────────────────────────
def cmd_perf(args):
    console = _console()
    from rich.table import Table
    from .performance import PerfTracker
    stats = PerfTracker(args.db).stats()
    if not stats:
        console.print("[yellow]No performance data yet.[/yellow]"); return
    t = Table(title="Performance (per model)", show_lines=False)
    t.add_column("Model",             style="bold cyan")
    t.add_column("Samples",           justify="right")
    t.add_column("TPS mean",          style="green",  justify="right")
    t.add_column("TPS p95",           style="green",  justify="right")
    t.add_column("Latency mean (s)",  style="yellow", justify="right")
    t.add_column("Latency p95 (s)",   style="yellow", justify="right")
    t.add_column("TTFT (s)",          style="dim",    justify="right")
    for s in stats:
        t.add_row(s["model"], str(s["n_samples"]),
                  f"{s['tps_mean']:.1f}", f"{s['tps_p95']:.1f}",
                  f"{s['latency_mean_s']:.2f}", f"{s['latency_p95_s']:.2f}",
                  f"{s['ttft_mean_s']:.2f}")
    console.print(t)


# ── export ────────────────────────────────────────────────────────────────────
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


# ── publish ───────────────────────────────────────────────────────────────────
def cmd_publish(args):
    console = _console()
    import os
    import requests
    from .elo import EloStore
    from .performance import PerfTracker

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        console.print("[red]Error: GITHUB_TOKEN or GH_TOKEN environment variable not set.[/red]")
        console.print("Please set it to your GitHub Personal Access Token (with 'gist' scope) or run:")
        console.print("  [cyan]export GITHUB_TOKEN=your_token_here[/cyan]")
        sys.exit(1)

    store = EloStore(db_path=args.db)
    leaderboard = store.leaderboard()
    matches = store.recent_matches_summary(limit=20)
    perf_tracker = PerfTracker(args.db)
    perf = perf_tracker.stats()
    benchmarks = store.benchmark_history(limit=20)

    # Build markdown report
    md = []
    md.append("# ollama-arena ELO Leaderboard & Results")
    md.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    md.append("## ELO Leaderboard")
    if not leaderboard:
        md.append("No matches yet.\n")
    else:
        md.append("| Rank | Model | ELO | Wins | Losses | Draws | Matches | Win Rate |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for e in leaderboard:
            md.append(f"| {e['rank']} | {e['model']} | {e['elo']:.1f} | {e['wins']} | {e['losses']} | {e['draws']} | {e['matches']} | {e['win_rate']:.1%} |")
        md.append("")

    md.append("## Recent Matches")
    if not matches:
        md.append("No matches recorded yet.\n")
    else:
        md.append("| ID | Model A | Model B | Category | Tasks | A Wins | B Wins | Draws | Winner | Date |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for m in matches:
            dt = datetime.fromtimestamp(m["ts"]).strftime("%Y-%m-%d %H:%M")
            md.append(f"| {m['id']} | {m['model_a']} | {m['model_b']} | {m['category']} | {m['tasks']} | {m['a_wins']} | {m['b_wins']} | {m['draws']} | {m['winner']} | {dt} |")
        md.append("")

    md.append("## Benchmark Runs")
    if not benchmarks:
        md.append("No benchmark runs recorded yet.\n")
    else:
        md.append("| Model | Score | Total Tasks | Date |")
        md.append("| :--- | :--- | :--- | :--- |")
        for b in benchmarks:
            dt = datetime.fromtimestamp(b["ts"]).strftime("%Y-%m-%d %H:%M")
            md.append(f"| {b['model']} | {b['score']:.1f} | {b['n_tasks']} | {dt} |")
        md.append("")

    md.append("## Performance Stats")
    if not perf:
        md.append("No performance data recorded yet.\n")
    else:
        md.append("| Model | Samples | TPS Mean | TPS P95 | Latency Mean (s) | Latency P95 (s) | TTFT Mean (s) |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for s in perf:
            md.append(f"| {s['model']} | {s['n_samples']} | {s['tps_mean']:.1f} | {s['tps_p95']:.1f} | {s['latency_mean_s']:.2f} | {s['latency_p95_s']:.2f} | {s['ttft_mean_s']:.2f} |")
        md.append("")

    report_content = "\n".join(md)

    # Build JSON report
    import json
    data = {
        "leaderboard": leaderboard,
        "recent_matches": matches,
        "benchmarks": benchmarks,
        "performance": perf,
        "updated_at": datetime.now().isoformat()
    }
    json_content = json.dumps(data, indent=2)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    payload = {
        "description": "ollama-arena ELO Leaderboard & Results",
        "public": args.public,
        "files": {
            "ollama_arena_results.md": {
                "content": report_content
            },
            "ollama_arena_data.json": {
                "content": json_content
            }
        }
    }

    try:
        console.print("[cyan]Uploading results to GitHub Gist...[/cyan]")
        r = requests.post("https://api.github.com/gists", json=payload, headers=headers)
        if r.status_code == 201:
            gist_url = r.json().get("html_url")
            console.print(f"[green]Successfully published! Gist URL:[/green] [cyan]{gist_url}[/cyan]")
        else:
            console.print(f"[red]Error publishing to Gist (status code {r.status_code}):[/red]")
            console.print(r.text)
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error publishing to Gist:[/red] {e}")
        sys.exit(1)


# ── web ───────────────────────────────────────────────────────────────────────
def cmd_web(args):
    from .web import run_web
    run_web(host=args.host, port=args.port,
            ollama_url=args.ollama, db_path=args.db,
            backend=args.backend, api_key=args.api_key)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        prog="ollama-arena",
        description="Local LLM ELO Arena — benchmark Ollama / vLLM / LM Studio / "
                    "llama.cpp / OpenAI-compat with auto-scored battles.",
    )
    p.add_argument("--ollama",   default="http://localhost:11434", metavar="URL")
    p.add_argument("--backend",  default=None, metavar="URL|PRESET",
                   help="vllm, lmstudio, llamacpp, openai, groq, together, openrouter,"
                        " or any URL with /v1/chat/completions")
    p.add_argument("--api-key",  default=None, metavar="KEY")
    p.add_argument("--db",       default="arena.db", metavar="PATH")
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    def add_common(parser):
        parser.add_argument("--dataset", default=None,
                            help="HF datasets to load (comma-sep): humaneval,mbpp,gsm8k,mmlu,...")
        parser.add_argument("--dataset-limit", type=int, default=None)

    # benchmark
    pb = sub.add_parser("benchmark",
                        help="Standardized 30-task Score (0–100) across all categories")
    pb.add_argument("models", metavar="MODEL[,MODEL2]",
                    help="One or more models to benchmark (comma-separated)")
    pb.add_argument("--compare",    action="store_true",
                    help="Side-by-side comparison when 2 models given")
    pb.add_argument("--fail-below", type=float, default=None, metavar="SCORE",
                    help="Exit code 1 if any model scores below this (for CI)")
    pb.set_defaults(func=cmd_benchmark)

    # match
    pm = sub.add_parser("match", help="Head-to-head battle(s)")
    pm.add_argument("--models",     required=True, metavar="A,B[,C...]")
    pm.add_argument("--category",   default="coding",
                    choices=["coding","reasoning","security","planning",
                             "inspection","math","knowledge","creative",
                             "json_format","tool_use","all"])
    pm.add_argument("--difficulty", default=None, choices=["easy","medium","hard"])
    pm.add_argument("-n",           type=int, default=10)
    pm.add_argument("--verbose", "-v", action="store_true",
                    help="Print full prompt + both responses for every task")
    pm.add_argument("--share",      action="store_true",
                    help="Print a shareable markdown results table at the end")
    add_common(pm)
    pm.set_defaults(func=cmd_match)

    # tournament
    pt = sub.add_parser("tournament", help="Round-robin tournament")
    pt.add_argument("--models",   required=True)
    pt.add_argument("--category", default="coding")
    pt.add_argument("-n",         type=int, default=5)
    add_common(pt)
    pt.set_defaults(func=cmd_tournament)

    # leaderboard
    sub.add_parser("leaderboard", aliases=["lb"],
                   help="Show ELO rankings").set_defaults(func=cmd_leaderboard)

    # list
    sub.add_parser("list",
                   help="List models available on the backend").set_defaults(func=cmd_list)

    # tasks
    sub.add_parser("tasks",
                   help="List built-in task categories and counts").set_defaults(func=cmd_tasks)

    # results
    pr = sub.add_parser("results",
                        help="Browse match history and per-task details")
    pr.add_argument("--match",  type=int, default=None,
                    help="Show all tasks from match <ID>")
    pr.add_argument("--last",   type=int, default=10,
                    help="How many recent matches to list (default 10)")
    pr.add_argument("--full",   action="store_true",
                    help="Print complete (untruncated) prompts and responses")
    pr.set_defaults(func=cmd_results)

    # inspect
    pi = sub.add_parser("inspect",
                        help="Show every recorded run for a single task ID")
    pi.add_argument("task_id", metavar="TASK_ID")
    pi.add_argument("--full", action="store_true",
                    help="Print complete responses")
    pi.set_defaults(func=cmd_inspect)

    # report
    prp = sub.add_parser("report",
                         help="Per-model category breakdown and strength/weakness analysis")
    prp.add_argument("--model", default=None,
                     help="Filter to a specific model (substring match)")
    prp.set_defaults(func=cmd_report)

    # datasets
    pd = sub.add_parser("datasets", help="HF dataset cache (pull / refresh)")
    pd.add_argument("--pull",    default=None, help="Comma-sep names to download")
    pd.add_argument("--refresh", default=None, help="Comma-sep names to re-download")
    pd.add_argument("--limit",   type=int, default=None)
    pd.set_defaults(func=cmd_datasets)

    # finetune
    pft = sub.add_parser("finetune", help="Unsloth pipeline (analyze/generate/train)")
    pft.add_argument("--analyze",    action="store_true")
    pft.add_argument("--generate",   action="store_true")
    pft.add_argument("--train",      default=None, metavar="JSONL_PATH")
    pft.add_argument("--model",      default=None)
    pft.add_argument("--teacher",    default=None)
    pft.add_argument("--category",   default="coding")
    pft.add_argument("--out",        default=None)
    pft.add_argument("--out-dir",    default=None)
    pft.add_argument("--n-tasks",    type=int, default=50)
    pft.add_argument("--base-model", default=None)
    pft.add_argument("--epochs",     type=int, default=2)
    pft.set_defaults(func=cmd_finetune)

    # perf
    sub.add_parser("perf",
                   help="Performance stats (TPS, latency, TTFT per model)").set_defaults(func=cmd_perf)

    # export
    pex = sub.add_parser("export", help="Export shareable HTML dashboard")
    pex.add_argument("--out", default="arena_dashboard.html")
    pex.set_defaults(func=cmd_export)

    # publish
    pp = sub.add_parser("publish", help="Upload ELO leaderboard and results to GitHub Gist")
    pp.add_argument("--public", action="store_true", help="Make the Gist public")
    pp.set_defaults(func=cmd_publish)

    # web
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
