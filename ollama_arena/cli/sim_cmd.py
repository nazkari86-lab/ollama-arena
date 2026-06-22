"""Simulations CLI commands -- sim list/run/benchmark/train/replay/inspect."""
from __future__ import annotations

import json

from .common import _console


def _make_manager(args, router=None):
    from ..simulations.core.runner import SimulationManager
    return SimulationManager(db_path=getattr(args, "sim_db", "sim.db"), router=router)


def _agent_specs_from_models(models: list[str], router_role: str | None = None):
    from ..simulations.core.types import AgentSpec
    counts: dict[str, int] = {}
    specs = []
    for m in models:
        counts[m] = counts.get(m, 0) + 1
        suffix = f"_{counts[m]}" if counts[m] > 1 else ""
        specs.append(AgentSpec(agent_id=f"{m}{suffix}", model=m, router_role=router_role))
    return specs


def _router_from_config(config: dict):
    """Pop routing config (role_models / agent_router_role) out of the
    scenario config dict and build a RoleRouter from it, switching which
    models a sim uses without touching any code -- just the config file.

    Returns (router_or_None, agent_router_role_or_None). Absent
    "role_models" means no router at all: every CLI-specified agent keeps
    using its literal --agents model string, identical to before this
    feature existed.
    """
    role_models = config.pop("role_models", None)
    agent_router_role = config.pop("agent_router_role", "npc_dialogue")
    if not role_models:
        return None, None
    from ..model_router import RoleRouter
    return RoleRouter(role_models=role_models), agent_router_role


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    with open(path) as f:
        if path.endswith((".yaml", ".yml")):
            try:
                import yaml
            except ImportError:
                raise SystemExit(
                    "Install the config extra for YAML support:\n"
                    "    pip install 'ollama-arena[config]'"
                )
            return yaml.safe_load(f) or {}
        return json.load(f)


def cmd_sim(args):
    console = _console()
    sim_cmd = getattr(args, "sim_cmd", None)

    if sim_cmd == "list":
        from ..simulations.core.scenario import list_scenarios
        from rich.table import Table

        table = Table(title="Available Simulation Scenarios")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        for spec in sorted(list_scenarios(), key=lambda s: s.name):
            table.add_row(spec.name, spec.description)
        console.print(table)

    elif sim_cmd == "run":
        config = _load_config(args.config)
        router, agent_role = _router_from_config(config)
        mgr = _make_manager(args, router=router)
        models = [m.strip() for m in args.agents.split(",") if m.strip()]
        specs = _agent_specs_from_models(models, router_role=agent_role)
        run_id = mgr.create_run(args.scenario, specs, config=config, seed=args.seed)
        console.print(f"[cyan]Run created:[/cyan] {run_id}")
        result = mgr.start_run(run_id, max_ticks=args.ticks)
        console.print(f"[bold]Result:[/bold] terminated={result.terminated} truncated={result.truncated}")
        console.print(f"Ticks: {result.ticks}")
        if result.outcome:
            console.print(f"Outcome: {result.outcome}")
        if result.metrics:
            console.print(f"Metrics: {result.metrics}")
        console.print(f"\n[dim]Replay with:[/dim] ollama-arena sim replay {run_id}")

    elif sim_cmd == "benchmark":
        config = _load_config(args.config)
        router, agent_role = _router_from_config(config)
        mgr = _make_manager(args, router=router)
        models = [m.strip() for m in args.agents.split(",") if m.strip()]
        run_ids = []
        for i in range(args.episodes):
            specs = _agent_specs_from_models(models, router_role=agent_role)
            run_id = mgr.create_run(args.scenario, specs, config=config, seed=i)
            mgr.start_run(run_id, max_ticks=args.ticks)
            run_ids.append(run_id)

        from ..simulations.eval.compare import compare_runs
        from rich.table import Table

        report = compare_runs(run_ids, db_path=getattr(args, "sim_db", "sim.db"))
        table = Table(title=f"Benchmark: {args.scenario} ({len(run_ids)} episodes)")
        table.add_column("Run ID", style="cyan")
        for name in report.metric_names:
            table.add_column(name, justify="right")
        for run_id in report.run_ids:
            row_metrics = report.metrics_by_run.get(run_id, {})
            table.add_row(run_id, *[f"{row_metrics.get(n, ''):.3f}" if n in row_metrics else "" for n in report.metric_names])
        console.print(table)

    elif sim_cmd == "train":
        from ..simulations.training.dataset import export_run_to_jsonl, load_jsonl
        from ..simulations.training.imitation import ImitationConfig, train_imitation

        tmp_path = f"/tmp/sim_train_{args.run_id}.jsonl"
        n = export_run_to_jsonl(args.run_id, tmp_path, db_path=getattr(args, "sim_db", "sim.db"))
        if n == 0:
            console.print(f"[yellow]No transitions found for run {args.run_id}.[/yellow]")
            return
        rows = load_jsonl(tmp_path)
        try:
            result = train_imitation(rows, config=ImitationConfig(epochs=args.epochs))
        except (ValueError, RuntimeError) as e:
            console.print(f"[red]Training failed: {e}[/red]")
            return
        console.print(f"[bold]Trained on {n} transitions, {args.epochs} epochs[/bold]")
        console.print(f"Action kinds: {result.kind_vocab}")
        console.print(f"Final loss: {result.final_loss:.4f}")
        console.print(f"Loss by epoch: {[round(l, 4) for l in result.losses_by_epoch]}")

    elif sim_cmd == "replay":
        from ..simulations.replay.player import ReplayPlayer

        player = ReplayPlayer(args.run_id, db_path=getattr(args, "sim_db", "sim.db"))
        events = player.seek(args.tick) if args.tick is not None else player.all_events()
        if not events:
            console.print(f"[yellow]No events found for run {args.run_id}.[/yellow]")
            return
        for event in events:
            console.print(f"[dim][{event.tick}][/dim] [cyan]{event.kind}[/cyan] {event.payload}")

    elif sim_cmd == "inspect":
        mgr = _make_manager(args)
        run = mgr.store.get_run(args.run_id)
        if not run:
            console.print(f"[yellow]No run found with id {args.run_id}.[/yellow]")
            return
        console.print(f"[bold cyan]{args.run_id}[/bold cyan]  scenario={run['scenario']}  status={run['status']}")
        console.print(f"Agents: {[a['agent_id'] + ':' + a['model'] for a in run['agents']]}")
        console.print(f"Config: {run['config']}")
        if run.get("outcome"):
            console.print(f"Outcome: {run['outcome']}")
        metrics = mgr.store.get_metrics(args.run_id)
        if metrics:
            by_name = {m["metric_name"]: m["value"] for m in metrics}
            console.print(f"Metrics: {by_name}")

    else:
        console.print("[yellow]Usage: ollama-arena sim <list|run|benchmark|train|replay|inspect>[/yellow]")
