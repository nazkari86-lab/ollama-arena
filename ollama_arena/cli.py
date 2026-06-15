"""
ollama-arena CLI — beautiful terminal interface using Rich.
"""
from __future__ import annotations
import argparse, sys, time, json
from pathlib import Path


def _require_rich():
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        from rich.panel import Panel
        from rich import print as rprint
        return Console()
    except ImportError:
        print("Install rich: pip install rich")
        sys.exit(1)


def cmd_list(args):
    """List available Ollama models."""
    console = _require_rich()
    from .arena import OllamaClient
    client = OllamaClient(base_url=args.ollama)

    if not client.is_alive():
        console.print(f"[red]✗ Ollama not reachable at {args.ollama}[/red]")
        console.print("  Start it with: [bold]ollama serve[/bold]")
        sys.exit(1)

    models = client.list_models()
    if not models:
        console.print("[yellow]No models found. Pull one: ollama pull llama3.2[/yellow]")
        return

    from rich.table import Table
    t = Table(title=f"Ollama models at {args.ollama}", show_lines=False)
    t.add_column("#", style="dim", width=4)
    t.add_column("Model", style="bold cyan")
    for i, m in enumerate(models, 1):
        t.add_row(str(i), m)
    console.print(t)


def cmd_leaderboard(args):
    """Show current ELO leaderboard."""
    console = _require_rich()
    from .elo import EloStore
    from rich.table import Table

    store = EloStore(db_path=args.db)
    board = store.leaderboard()

    if not board:
        console.print("[yellow]No matches yet. Run: ollama-arena match --models a,b[/yellow]")
        return

    t = Table(title="🏆 ELO Leaderboard", show_lines=True)
    t.add_column("Rank", style="bold yellow", width=6)
    t.add_column("Model", style="bold cyan", min_width=20)
    t.add_column("ELO", style="bold green", justify="right")
    t.add_column("W", style="green", justify="right")
    t.add_column("L", style="red", justify="right")
    t.add_column("D", style="dim", justify="right")
    t.add_column("Matches", justify="right")
    t.add_column("Win%", justify="right")

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for entry in board:
        rank = entry["rank"]
        medal = medals.get(rank, str(rank))
        wr = f"{entry['win_rate']:.0%}"
        t.add_row(
            medal, entry["model"],
            str(entry["elo"]),
            str(entry["wins"]), str(entry["losses"]), str(entry["draws"]),
            str(entry["matches"]), wr,
        )
    console.print(t)


def cmd_match(args):
    """Run a head-to-head match between two or more models."""
    console = _require_rich()
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from .arena import Arena

    models = [m.strip() for m in args.models.split(",")]
    if len(models) < 2:
        console.print("[red]Provide at least 2 models: --models a,b[/red]")
        sys.exit(1)

    arena = Arena(ollama_url=args.ollama, db_path=args.db)

    if not arena.client.is_alive():
        console.print(f"[red]✗ Ollama not reachable at {args.ollama}[/red]")
        sys.exit(1)

    from itertools import combinations
    pairs = list(combinations(models, 2))
    category = args.category
    n = args.n

    console.print(Panel(
        f"[bold cyan]OLLAMA ARENA[/bold cyan]\n"
        f"Models: {', '.join(models)}\n"
        f"Category: [yellow]{category}[/yellow]  |  Tasks per match: [yellow]{n}[/yellow]\n"
        f"DB: {args.db}",
        title="⚔️  Battle Start"
    ))

    task_log = []

    def on_task(task_id, score_a, score_b, outcome):
        icon = {"a_wins": "✅", "b_wins": "❌", "draw": "🤝"}[outcome]
        task_log.append(f"  {icon} {task_id}: {score_a:.2f} vs {score_b:.2f}")

    arena._on_task_done = on_task

    all_results = []
    for i, (model_a, model_b) in enumerate(pairs, 1):
        console.print(f"\n[bold]Match {i}/{len(pairs)}: [cyan]{model_a}[/cyan] vs [magenta]{model_b}[/magenta][/bold]")

        task_log.clear()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=True) as prog:
            tid = prog.add_task(f"Running {n} tasks...", total=None)
            result = arena.run_match(model_a, model_b, category=category, n=n)
            prog.remove_task(tid)

        for line in task_log:
            console.print(line)

        winner = model_a if result.a_wins > result.b_wins else (
            model_b if result.b_wins > result.a_wins else "Draw"
        )
        elo_diff_a = result.elo_a_after - result.elo_a_before
        elo_diff_b = result.elo_b_after - result.elo_b_before

        summary = Table(show_header=False, box=None, padding=(0, 2))
        summary.add_column("", style="dim")
        summary.add_column("A", style="cyan", justify="right")
        summary.add_column("B", style="magenta", justify="right")
        summary.add_row("Model", model_a, model_b)
        summary.add_row("Wins", str(result.a_wins), str(result.b_wins))
        summary.add_row("Win rate", f"{result.a_win_rate:.0%}", f"{result.b_win_rate:.0%}")
        summary.add_row("ELO", f"{result.elo_a_after:.0f} ({elo_diff_a:+.0f})",
                         f"{result.elo_b_after:.0f} ({elo_diff_b:+.0f})")
        console.print(summary)
        console.print(f"  🏆 [bold]Winner: {winner}[/bold]  ({result.duration_s:.0f}s)")
        all_results.append(result)

    console.print()
    cmd_leaderboard(args)


def cmd_tasks(args):
    """Show available benchmark tasks."""
    console = _require_rich()
    from .tasks import task_stats, list_categories, get_tasks
    from rich.table import Table

    stats = task_stats()
    t = Table(title="📋 Benchmark Tasks", show_lines=False)
    t.add_column("Category", style="bold cyan")
    t.add_column("Tasks", justify="right")
    t.add_column("Easy", justify="right", style="green")
    t.add_column("Medium", justify="right", style="yellow")
    t.add_column("Hard", justify="right", style="red")

    for cat, count in stats.items():
        tasks = get_tasks(category=cat)
        easy   = sum(1 for t2 in tasks if t2.get("difficulty") == "easy")
        medium = sum(1 for t2 in tasks if t2.get("difficulty") == "medium")
        hard   = sum(1 for t2 in tasks if t2.get("difficulty") == "hard")
        t.add_row(cat, str(count), str(easy), str(medium), str(hard))

    total = sum(stats.values())
    t.add_section()
    t.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]", "", "", "")
    console.print(t)


def cmd_web(args):
    """Launch web dashboard."""
    try:
        from .web import run_web
        run_web(host=args.host, port=args.port, ollama_url=args.ollama, db_path=args.db)
    except ImportError as e:
        print(f"Install web deps: pip install 'ollama-arena[web]'  ({e})")
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(
        prog="ollama-arena",
        description="⚔️  Local LLM ELO Arena — benchmark your Ollama models",
    )
    p.add_argument("--ollama", default="http://localhost:11434", metavar="URL",
                   help="Ollama base URL (default: http://localhost:11434)")
    p.add_argument("--db", default="arena.db", metavar="PATH",
                   help="SQLite database path (default: arena.db)")
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    # match
    pm = sub.add_parser("match", help="Run a head-to-head battle")
    pm.add_argument("--models", required=True, metavar="A,B[,C...]",
                    help="Comma-separated model names")
    pm.add_argument("--category", default="coding",
                    choices=["coding", "reasoning", "security", "planning", "inspection", "all"],
                    help="Benchmark category (default: coding)")
    pm.add_argument("-n", type=int, default=10,
                    help="Tasks per match (default: 10)")
    pm.set_defaults(func=cmd_match)

    # leaderboard
    pl = sub.add_parser("leaderboard", aliases=["lb"], help="Show ELO leaderboard")
    pl.set_defaults(func=cmd_leaderboard)

    # list
    pls = sub.add_parser("list", help="List available Ollama models")
    pls.set_defaults(func=cmd_list)

    # tasks
    pt = sub.add_parser("tasks", help="Show benchmark task statistics")
    pt.set_defaults(func=cmd_tasks)

    # web
    pw = sub.add_parser("web", help="Launch web dashboard")
    pw.add_argument("--host", default="0.0.0.0")
    pw.add_argument("--port", type=int, default=7860)
    pw.set_defaults(func=cmd_web)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
