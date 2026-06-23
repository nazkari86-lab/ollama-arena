"""Data, reporting, and export commands."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .common import (
    _console, _show_match_detail,
)


def cmd_list(args):
    console = _console()
    from rich.table import Table
    from ..backends.auto import auto_backend
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
    from ..elo import EloStore
    board = EloStore(db_path=args.db).leaderboard()
    if not board:
        console.print("[yellow]No matches yet.[/yellow]")
        return
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

def cmd_anti_leaderboard(args):
    """Show models ranked by hallucination rate (highest first)."""
    console = _console()
    from rich.table import Table
    from ..elo import EloStore
    board = EloStore(db_path=args.db).anti_leaderboard()
    if not board:
        console.print("[yellow]No hallucination data yet (run matches with --judge).[/yellow]")
        return

    t = Table(title="Anti-Leaderboard (Hallucination Rate)")
    t.add_column("Rank", justify="right", style="cyan")
    t.add_column("Model", style="bold")
    t.add_column("Rate", justify="right", style="red")
    t.add_column("Count", justify="center")
    t.add_column("Checked", justify="right")
    for e in board:
        t.add_row(str(e["rank"]), e["model"], f"{e['halluc_rate']:.1%}",
                  str(e["hallucinations"]), str(e["total_checked"]))
    console.print(t)
    console.print("\n[dim]Note: Lower is better. Rate = detected hallucinations / tasks checked by judge.[/dim]")


# ── match ─────────────────────────────────────────────────────────────────────

def cmd_import(args):
    """Import a local CSV/JSON dataset for evaluation.

    NOTE: this command currently only validates and counts records in the
    file — it does not yet register a queryable 'local_<name>' task category.
    """
    console = _console()
    import csv
    import json as _json
    import sys
    from pathlib import Path

    file_path = Path(args.file)
    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        sys.exit(1)

    console.print(f"Importing local dataset: [cyan]{file_path.name}[/cyan]")
    console.print("[dim]Parsing file format...[/dim]")

    suffix = file_path.suffix.lower()
    try:
        if suffix == ".csv":
            with file_path.open(newline="", encoding="utf-8") as f:
                n_records = sum(1 for _ in csv.reader(f)) - 1  # minus header
                n_records = max(n_records, 0)
        elif suffix in (".json", ".jsonl"):
            text = file_path.read_text(encoding="utf-8")
            if suffix == ".jsonl":
                n_records = sum(1 for ln in text.splitlines() if ln.strip())
            else:
                data = _json.loads(text)
                n_records = len(data) if isinstance(data, list) else 1
        else:
            console.print(f"[red]Unsupported file format: {suffix or '(none)'}. Use .csv, .json, or .jsonl[/red]")
            sys.exit(1)
    except (OSError, _json.JSONDecodeError, csv.Error) as e:
        console.print(f"[red]Failed to parse {file_path.name}: {e}[/red]")
        sys.exit(1)

    if n_records == 0:
        console.print(f"[yellow]⚠ {file_path.name} contains no records — nothing imported.[/yellow]")
        sys.exit(1)

    console.print(
        f"[green]✓ Parsed {n_records} record(s) from {file_path.name}[/green] "
        f"[dim](category registration for 'local_{file_path.stem}' is not yet implemented)[/dim]"
    )


# ── tasks ─────────────────────────────────────────────────────────────────────

def cmd_tasks(args):
    console = _console()
    from rich.table import Table
    from ..tasks import task_stats, get_tasks, list_languages
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
    from ..datasets import available_datasets, load_dataset, refresh_dataset

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
    from ..elo import EloStore

    store = EloStore(db_path=args.db)

    if args.match:
        _show_match_detail(console, store, args.match, args.full)
        if args.export:
            from ..visualize import export_match_report
            tasks = store.tasks_for_match(args.match)
            history = store.match_history(limit=200)
            info = next((m for m in history if m["id"] == args.match), None)
            if info:
                out = export_match_report(args.match, info, tasks)
                console.print(f"\n  [green]✓ Match report exported to: [bold]{out}[/bold][/green]")
            else:
                console.print(
                    f"\n  [yellow]⚠ Could not export match #{args.match}: "
                    f"not found in recent match history.[/yellow]"
                )
        return

    # List recent matches
    matches = store.recent_matches_summary(limit=args.last)
    if not matches:
        console.print("[yellow]No matches recorded yet.[/yellow]")
        return

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

def cmd_inspect(args):
    """Show all recorded runs for a specific task ID."""
    console = _console()
    from rich.table import Table
    from rich.rule import Rule
    from rich.panel import Panel
    from ..elo import EloStore

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
    from ..elo import EloStore

    store = EloStore(db_path=args.db)
    board = store.leaderboard()
    if not board:
        console.print("[yellow]No data yet.[/yellow]")
        return

    models = [e["model"] for e in board]
    if args.model:
        models = [m for m in models if args.model.lower() in m.lower()]
        if not models:
            console.print(f"[red]No model matching '{args.model}'[/red]")
            return

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

def cmd_export(args):
    console = _console()
    from ..elo import EloStore
    from ..performance import PerfTracker
    from ..visualize import export_dashboard
    from ..tasks import list_categories

    store = EloStore(args.db)
    leaderboard = store.leaderboard()
    matches = store.match_history(limit=1000)
    perf = PerfTracker(args.db).stats()
    anti_leaderboard = store.anti_leaderboard()

    out = export_dashboard(
        args.out, leaderboard=leaderboard, matches=matches,
        categories=list_categories(), performance=perf,
        anti_leaderboard=anti_leaderboard,
    )
    console.print(f"  dashboard exported → [cyan]{out}[/cyan]")
    console.print(f"     open file://{Path(out).absolute()}")


# ── publish ───────────────────────────────────────────────────────────────────

def cmd_publish(args):
    console = _console()
    import requests
    from ..elo import EloStore
    from ..performance import PerfTracker

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
        r = requests.post("https://api.github.com/gists", json=payload, headers=headers, timeout=30)
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

def cmd_perf(args):
    console = _console()
    from rich.table import Table
    from ..performance import PerfTracker
    stats = PerfTracker(args.db).stats()
    if not stats:
        console.print("[yellow]No performance data yet.[/yellow]")
        return
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
