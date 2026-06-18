"""Shared CLI helpers and display utilities."""
from __future__ import annotations

import sys
import textwrap
import time
from contextlib import contextmanager


def _console():
    try:
        from rich.console import Console
        return Console()
    except ImportError:
        print("Install rich first: pip install rich")
        sys.exit(1)

def _make_arena(args):
    from ..arena import Arena
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


# ── Progress Bars and Spinners ───────────────────────────────────────────────

@contextmanager
def progress_bar(description: str, total: int = None):
    """Context manager for progress bar using rich.Progress."""
    try:
        from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn

        console = _console()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(description, total=total)
            yield progress, task
    except ImportError:
        # Fallback to simple console output
        print(f"{description}...")
        yield None, None


@contextmanager
def spinner(text: str):
    """Context manager for spinner animation using rich.live."""
    try:
        from rich.live import Live
        from rich.spinner import Spinner

        console = _console()
        spin = Spinner("dots", text=text)
        with Live(spin, console=console, refresh_per_second=10):
            yield
    except ImportError:
        # Fallback to simple console output
        print(f"{text}...")
        yield


def print_success(message: str):
    """Print success message with green checkmark."""
    console = _console()
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str):
    """Print error message with red cross."""
    console = _console()
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str):
    """Print warning message with yellow warning sign."""
    console = _console()
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str):
    """Print info message with blue info sign."""
    console = _console()
    console.print(f"[blue]ℹ[/blue] {message}")


def print_step(step: int, total: int, message: str):
    """Print step indicator with progress."""
    console = _console()
    console.print(f"[dim]Step {step}/{total}:[/dim] {message}")


# ── Interactive Prompts ───────────────────────────────────────────────────────

def confirm(prompt: str, default: bool = False) -> bool:
    """Ask user for confirmation with y/n prompt."""
    try:
        from rich.prompt import Confirm

        console = _console()
        return Confirm.ask(prompt, default=default)
    except ImportError:
        # Fallback to simple input
        suffix = " [Y/n]" if default else " [y/N]"
        while True:
            response = input(f"{prompt}{suffix}: ").strip().lower()
            if not response:
                return default
            if response in ("y", "yes"):
                return True
            elif response in ("n", "no"):
                return False


# ── list ─────────────────────────────────────────────────────────────────────

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


def add_common(parser):
    parser.add_argument("--dataset", default=None,
                        help="HF datasets to load (comma-sep): humaneval,mbpp,gsm8k,mmlu,...")
    parser.add_argument("--dataset-limit", type=int, default=None)
