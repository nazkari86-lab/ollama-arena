"""CLI commands for agentic evaluation features."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .common import _console, _make_arena


def cmd_sandbox(args):
    """Manage VM sandboxes for isolated task execution."""
    c = _console()

    arena = _make_arena(args)
    from ..agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend

    config = SandboxConfig(
        backend=SandboxBackend(args.backend) if args.backend else SandboxBackend.DOCKER,
        cpu_limit=args.cpu_limit,
        memory_limit=args.memory,
        timeout_seconds=args.timeout,
        network_isolated=not args.no_network_isolation,
    )

    manager = SandboxManager(config)

    if args.sandbox_action == "create":
        c.print(f"[cyan]Creating sandbox {args.sandbox_id}...[/cyan]")
        instance = manager.create_sandbox(args.sandbox_id)
        if instance.status.value == "running":
            c.print(f"[green]✓ Sandbox {args.sandbox_id} created successfully[/green]")
        else:
            c.print(f"[red]✗ Failed to create sandbox: {instance.metadata.get('error', 'Unknown error')}[/red]")
            sys.exit(1)

    elif args.sandbox_action == "execute":
        c.print(f"[cyan]Executing task in sandbox {args.sandbox_id}...[/cyan]")
        result = manager.execute_task(args.sandbox_id, args.task)
        if result.success:
            c.print(f"[green]✓ Task completed successfully[/green]")
            c.print(f"Output: {result.output[:500]}")
        else:
            c.print(f"[red]✗ Task failed: {result.error}[/red]")
            sys.exit(1)

    elif args.sandbox_action == "stop":
        c.print(f"[cyan]Stopping sandbox {args.sandbox_id}...[/cyan]")
        if manager.stop_sandbox(args.sandbox_id):
            c.print(f"[green]✓ Sandbox stopped[/green]")
        else:
            c.print(f"[red]✗ Failed to stop sandbox[/red]")
            sys.exit(1)

    elif args.sandbox_action == "list":
        sandboxes = manager.list_sandboxes()
        c.print(f"[bold]Active Sandboxes ({len(sandboxes)}):[/bold]")
        for sb_id in sandboxes:
            status = manager.get_sandbox_status(sb_id)
            c.print(f"  - {sb_id}: {status.value if status else 'unknown'}")

    elif args.sandbox_action == "cleanup":
        if args.sandbox_id:
            c.print(f"[cyan]Cleaning up sandbox {args.sandbox_id}...[/cyan]")
            if manager.cleanup_sandbox(args.sandbox_id):
                c.print(f"[green]✓ Sandbox cleaned up[/green]")
            else:
                c.print(f"[red]✗ Failed to cleanup sandbox[/red]")
        else:
            c.print("[cyan]Cleaning up all sandboxes...[/cyan]")
            manager.cleanup_all()
            c.print("[green]✓ All sandboxes cleaned up[/green]")


def cmd_swarm(args):
    """Run swarm battles between teams of agents."""
    c = _console()
    from rich.panel import Panel

    arena = _make_arena(args)
    if not arena.client.is_alive():
        c.print("[red]✗ Backend not reachable.[/red]")
        sys.exit(1)

    from ..agentic.swarm import SwarmBattle, SwarmTeam, example_2v2_setup, example_3v3_setup, AgentRole

    # Parse team configurations
    if args.mode == "2v2":
        team_a_config, team_b_config = example_2v2_setup()
    elif args.mode == "3v3":
        team_a_config, team_b_config = example_3v3_setup()
    else:
        c.print("[red]Invalid mode. Use 2v2 or 3v3[/red]")
        sys.exit(1)

    # Override with custom configs if provided
    if args.team_a:
        team_a_config = dict(
            item.split(":") for item in args.team_a.split(",")
        )
        # Convert role strings to AgentRole
        team_a_config = {
            model: AgentRole(role) for model, role in team_a_config.items()
        }

    if args.team_b:
        team_b_config = dict(
            item.split(":") for item in args.team_b.split(",")
        )
        team_b_config = {
            model: AgentRole(role) for model, role in team_b_config.items()
        }

    battle = SwarmBattle(arena.client, arena.mcp)
    team_a = battle.create_team("Team A", team_a_config)
    team_b = battle.create_team("Team B", team_b_config)

    c.print(Panel(
        f"[bold]Swarm Battle[/bold]\n"
        f"Mode: [cyan]{args.mode}[/cyan]\n"
        f"Team A: [yellow]{', '.join(team_a_config.keys())}[/yellow]\n"
        f"Team B: [yellow]{', '.join(team_b_config.keys())}[/yellow]\n"
        f"Task: [cyan]{args.task[:100]}...[/cyan]\n"
        f"Rounds: [cyan]{args.rounds}[/cyan]",
        title="ollama-arena swarm",
    ))

    with c.status("Running swarm battle..."):
        result = battle.run_battle(
            team_a,
            team_b,
            args.task,
            rounds=args.rounds,
            max_steps_per_round=args.max_steps,
        )

    c.print(f"\n[bold green]Result:[/bold green]")
    c.print(f"Winner: [cyan]{result.winner}[/cyan]")
    c.print(f"Score: {result.team_a_name} {result.team_a_score} vs {result.team_b_name} {result.team_b_score}")
    c.print(f"Duration: {result.duration_s:.2f}s")
    c.print(f"Rounds completed: {result.rounds_completed}")

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(
                {
                    "winner": result.winner,
                    "team_a_score": result.team_a_score,
                    "team_b_score": result.team_b_score,
                    "collaboration_metrics": result.collaboration_metrics,
                    "details": {
                        "team_a": result.team_a_details,
                        "team_b": result.team_b_details,
                    },
                },
                f,
                indent=2,
            )
        c.print(f"\n[dim]Results saved to {output_path}[/dim]")


def cmd_redteam(args):
    """Run red team arena for security evaluation."""
    c = _console()
    from rich.panel import Panel

    arena = _make_arena(args)
    if not arena.client.is_alive():
        c.print("[red]✗ Backend not reachable.[/red]")
        sys.exit(1)

    from ..agentic.redteam import RedTeamArena, RedTeamConfig

    config = RedTeamConfig(
        max_rounds=args.rounds,
        severity_levels=args.severity.split(",") if args.severity else ["low", "medium", "high", "critical"],
        allow_adaptive_attacks=not args.no_adaptive,
        timeout_per_round=args.timeout,
    )

    arena_session = RedTeamArena(arena.client, config)

    c.print(Panel(
        f"[bold]Red Team Arena[/bold]\n"
        f"Attacker: [cyan]{args.attacker}[/cyan]\n"
        f"Defender: [cyan]{args.defender}[/cyan]\n"
        f"Context: [yellow]{args.context}[/yellow]\n"
        f"Rounds: [cyan]{args.rounds}[/cyan]\n"
        f"Adaptive attacks: [cyan]{not args.no_adaptive}[/cyan]",
        title="ollama-arena redteam",
    ))

    with c.status("Running red team arena..."):
        result = arena_session.run_arena(
            attacker_model=args.attacker,
            defender_model=args.defender,
            task_context=args.context,
        )

    c.print(f"\n[bold green]Result:[/bold green]")
    c.print(f"Overall winner: [cyan]{result.overall_winner}[/cyan]")
    c.print(f"Attacker score: {result.attacker_score:.3f}")
    c.print(f"Defender score: {result.defender_score:.3f}")
    c.print(f"Attacker wins: {result.attacker_wins}/{result.total_rounds}")
    c.print(f"Defender wins: {result.defender_wins}/{result.total_rounds}")
    c.print(f"Duration: {result.duration_s:.2f}s")

    c.print(f"\n[bold]Defense Metrics:[/bold]")
    c.print(f"Detection rate: {result.defense_metrics['detection_rate']:.3f}")
    c.print(f"Blocked: {result.defense_metrics['blocked']}")
    c.print(f"Detected: {result.defense_metrics['detected']}")
    c.print(f"Failed: {result.defense_metrics['failed']}")
    c.print(f"Vulnerable: {result.defense_metrics['vulnerable']}")

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(
                {
                    "attacker": result.attacker_model,
                    "defender": result.defender_model,
                    "overall_winner": result.overall_winner,
                    "attacker_score": result.attacker_score,
                    "defender_score": result.defender_score,
                    "defense_metrics": result.defense_metrics,
                    "attack_breakdown": result.attack_breakdown,
                },
                f,
                indent=2,
            )
        c.print(f"\n[dim]Results saved to {output_path}[/dim]")


def cmd_long_horizon(args):
    """Manage and execute long-horizon tasks."""
    c = _console()
    from rich.table import Table

    from ..tasks.long_horizon import LongHorizonTaskManager, LONG_HORIZON_TASKS, default_task_evaluator

    manager = LongHorizonTaskManager(checkpoint_dir=Path(args.checkpoint_dir))

    if args.lh_action == "list":
        table = Table(title="Long-Horizon Tasks")
        table.add_column("ID", style="cyan")
        table.add_column("Role", style="yellow")
        table.add_column("Difficulty", style="magenta")
        table.add_column("Est. Hours", style="green")
        table.add_column("Checkpoints")

        for task_def in LONG_HORIZON_TASKS:
            table.add_row(
                task_def["id"],
                task_def["role"],
                task_def["difficulty"],
                str(task_def["estimated_hours"]),
                str(len(task_def.get("checkpoints", []))),
            )
        c.print(table)

    elif args.lh_action == "start":
        task_def = next((t for t in LONG_HORIZON_TASKS if t["id"] == args.task_id), None)
        if not task_def:
            c.print(f"[red]Task {args.task_id} not found[/red]")
            sys.exit(1)

        task = manager.create_task(task_def)
        manager.start_task(task.id)
        c.print(f"[green]✓ Started task {task.id}[/green]")
        c.print(f"Estimated duration: {task.estimated_duration_hours} hours")

    elif args.lh_action == "pause":
        if manager.pause_task(args.task_id):
            c.print(f"[green]✓ Paused task {args.task_id}[/green]")
        else:
            c.print(f"[red]✗ Failed to pause task[/red]")
            sys.exit(1)

    elif args.lh_action == "resume":
        if manager.resume_task(args.task_id):
            c.print(f"[green]✓ Resumed task {args.task_id}[/green]")
        else:
            c.print(f"[red]✗ Failed to resume task[/red]")
            sys.exit(1)

    elif args.lh_action == "progress":
        task = manager.get_task(args.task_id)
        if not task:
            c.print(f"[red]Task {args.task_id} not found[/red]")
            sys.exit(1)

        progress = manager.update_progress(
            args.task_id,
            args.progress,
            args.step_description,
        )
        if progress:
            c.print(f"[cyan]Progress updated:[/cyan]")
            c.print(f"  Progress: {progress.progress_percentage:.1f}%")
            c.print(f"  Step: {progress.step_description}")
            c.print(f"  Time elapsed: {progress.time_elapsed_s:.1f}s")
            c.print(f"  Est. remaining: {progress.estimated_remaining_s:.1f}s")

    elif args.lh_action == "complete":
        task = manager.get_task(args.task_id)
        if not task:
            c.print(f"[red]Task {args.task_id} not found[/red]")
            sys.exit(1)

        # Simulate final results
        final_results = {"status": "completed", "artifacts": []}
        if manager.complete_task(args.task_id, final_results):
            c.print(f"[green]✓ Completed task {args.task_id}[/green]")

            # Evaluate task
            evaluation = manager.evaluate_task(args.task_id, default_task_evaluator)
            if evaluation:
                c.print(f"[cyan]Evaluation:[/cyan]")
                c.print(f"  Overall score: {evaluation.overall_score:.3f}")
                c.print(f"  Completion: {evaluation.completion_percentage:.1f}%")
                c.print(f"  Duration: {evaluation.duration_s:.1f}s")
                c.print(f"  Assessment: {evaluation.final_assessment}")
        else:
            c.print(f"[red]✗ Failed to complete task[/red]")
            sys.exit(1)

    elif args.lh_action == "status":
        task = manager.get_task(args.task_id)
        if not task:
            c.print(f"[red]Task {args.task_id} not found[/red]")
            sys.exit(1)

        c.print(f"[bold]Task {task.id} Status:[/bold]")
        c.print(f"  Status: {task.status.value}")
        c.print(f"  Progress: {task.current_progress*100:.1f}%")
        c.print(f"  Checkpoints: {len(task.checkpoints)}")
        c.print(f"  Intermediate results: {len(task.intermediate_results)}")
        if task.started_at:
            import time as time_module
            elapsed = time_module.time() - task.started_at
            c.print(f"  Time elapsed: {elapsed:.1f}s")
