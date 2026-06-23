"""Genome explorer CLI commands."""
from __future__ import annotations

from .common import _console


def cmd_genome(args):
    console = _console()
    from ..genome.db import GenomeStore
    from ..genome.registry import CanonicalRegistry
    from ..genome.scanner import OllamaScanner
    from ..genome.resolver import GenomeResolver
    from ..genome.graph import GraphEngine

    db_path = getattr(args, "genome_db", "genome.db")
    store = GenomeStore(db_path=db_path)
    registry = CanonicalRegistry()
    resolver = GenomeResolver(store=store, registry=registry)

    genome_cmd = getattr(args, "genome_cmd", None)

    if genome_cmd == "scan":
        from rich.table import Table

        scanner = OllamaScanner(ollama_url=args.ollama)
        local = scanner.scan_local()
        if not local:
            console.print("[yellow]No local Ollama models found.[/yellow]")
            return
        results = resolver.scan_and_resolve_all(local)
        table = Table(title="Genome Scan Results")
        table.add_column("Local Model", style="cyan")
        table.add_column("Canonical ID", style="green")
        table.add_column("Confidence", style="yellow")
        table.add_column("Size GB", justify="right")
        local_map = {item.name: item for item in local}
        for r in results:
            linfo = local_map.get(r["name"])
            size = f"{linfo.size_gb:.1f}" if linfo else "?"
            table.add_row(r["name"], r.get("genome_id") or "Unknown",
                          r["confidence"], size)
        console.print(table)

    elif genome_cmd == "tree":
        from rich import print as rprint

        engine = GraphEngine(store)
        if args.model:
            gid = registry.match_by_name(args.model)
            data = engine.subtree(gid or args.model)
        else:
            data = engine.to_d3()

        if not data["nodes"]:
            console.print(f"[yellow]No lineage data found{f' for {args.model}' if args.model else ''}.[/yellow]")
            return

        targets = {link["target"] for link in data["links"]}
        roots = [n for n in data["nodes"] if n["id"] not in targets]
        if not roots:
            roots = data["nodes"][:1]

        def add_children(rich_node, parent_id: str, depth: int = 0):
            if depth > 6:
                return
            children = [link["source"] for link in data["links"] if link["target"] == parent_id]
            for cid in children:
                cnode = next((n for n in data["nodes"] if n["id"] == cid), None)
                if cnode:
                    pb = cnode.get("params_b", 0) or 0
                    label = f"[cyan]{cnode['name']}[/] ({pb:.1f}B)"
                    branch = rich_node.add(label)
                    add_children(branch, cid, depth + 1)

        try:
            from rich.tree import Tree as RichTree
            for root in roots[:5]:
                pb = root.get("params_b", 0) or 0
                rich_tree = RichTree(f"[bold]{root['name']}[/] ({pb:.1f}B)")
                add_children(rich_tree, root["id"])
                rprint(rich_tree)
        except ImportError:
            console.print("[yellow]Install rich for tree view.[/yellow]")

    elif genome_cmd == "show":
        match_id = registry.match_by_name(args.model)
        canonical = registry.get(match_id) if match_id else None
        local_rows = store.list_local()
        local_match = next((r for r in local_rows if r["name"] == args.model), None)
        if canonical:
            console.print(f"\n[bold cyan]{canonical['name']}[/bold cyan]")
            console.print(f"Family: {canonical.get('family','')}  |  Org: {canonical.get('org','')}")
            arch = canonical.get("architecture", {})
            console.print(
                f"Params: {arch.get('params_b','?')}B | Layers: {arch.get('n_layers','?')} | "
                f"Context: {arch.get('context_length','?')}"
            )
            if local_match:
                console.print(
                    f"Local: [green]{local_match['confidence']}[/green] confidence  |  "
                    f"{local_match.get('size_gb',0):.1f} GB"
                )
        else:
            console.print(f"[yellow]No canonical genome entry found for '{args.model}'[/yellow]")
    else:
        console.print("[yellow]Usage: arena genome <scan|tree|show>[/yellow]")
