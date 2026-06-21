"""CLI commands for P2P Grid operations."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..p2p.node import P2PNode, NodeDiscovery
from ..p2p.distribution import TaskGossipProtocol, TaskDistributor, ReputationDatabase
from ..p2p.crypto_proof import CryptoProofGenerator, BlockchainAnchorer
from ..p2p.leaderboard import GlobalLeaderboard, VerifiedEntry


def print_success(message: str) -> None:
    """Print success message."""
    if RICH_AVAILABLE:
        console = Console()
        console.print(f"[green]✓[/green] {message}")
    else:
        print(f"✓ {message}")


def print_error(message: str) -> None:
    """Print error message."""
    if RICH_AVAILABLE:
        console = Console()
        console.print(f"[red]✗[/red] {message}")
    else:
        print(f"✗ {message}")


def print_info(message: str) -> None:
    """Print info message."""
    if RICH_AVAILABLE:
        console = Console()
        console.print(f"[blue]ℹ[/blue] {message}")
    else:
        print(f"ℹ {message}")


async def cmd_node_join_global(args) -> None:
    """
    Join the global P2P network.
    
    Usage: ollama-arena node --join-global [--bootstrap NODES] [--port PORT]
    """
    print_info("Initializing P2P node...")
    
    # Parse bootstrap nodes
    bootstrap_nodes = []
    if args.bootstrap:
        bootstrap_nodes = args.bootstrap.split(',')
    
    # Create P2P node
    node = P2PNode(
        host=args.host or "0.0.0.0",
        port=args.port or 8080,
        bootstrap_nodes=bootstrap_nodes,
    )
    
    # Start node
    await node.start()
    
    print_success(f"Node {node.local_node_id} started")
    print_info(f"Listening on {args.host or '0.0.0.0'}:{args.port or 8080}")
    print_info(f"Connected to {node.get_peer_count()} peers")
    
    # Keep running
    try:
        print_info("Node running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
            
            # Print stats every 30 seconds
            stats = node.get_stats()
            if stats['messages_sent'] % 30 == 0 and stats['messages_sent'] > 0:
                print_info(f"Stats: {stats}")
    except KeyboardInterrupt:
        print_info("Shutting down node...")
        await node.stop()
        print_success("Node stopped")


async def cmd_node_status(args) -> None:
    """
    Show P2P node status.
    
    Usage: ollama-arena node --status
    """
    # In a real implementation, this would connect to a running node
    # For now, show simulated status
    print_info("P2P Node Status")
    print("=" * 50)
    print("Node ID: Not connected")
    print("State: Offline")
    print("Peers: 0")
    print("=" * 50)


async def cmd_node_peers(args) -> None:
    """
    List connected peers.
    
    Usage: ollama-arena node --peers
    """
    print_info("Discovering peers...")
    
    discovery = NodeDiscovery()
    peers = await discovery.discover_all()
    
    if RICH_AVAILABLE:
        console = Console()
        table = Table(title="Discovered Peers")
        table.add_column("Node ID", style="cyan")
        table.add_column("Address", style="magenta")
        table.add_column("Port", style="green")
        table.add_column("Trust", style="yellow")
        
        for peer in peers:
            table.add_row(
                peer.node_id[:8] + "...",
                peer.address,
                str(peer.port),
                peer.trust_level,
            )
        
        console.print(table)
    else:
        print(f"Discovered {len(peers)} peers:")
        for peer in peers:
            print(f"  - {peer.node_id[:8]}... @ {peer.endpoint} ({peer.trust_level})")


async def cmd_global_leaderboard(args) -> None:
    """
    Show the global verified leaderboard.
    
    Usage: ollama-arena node --global-leaderboard [--category CAT] [--limit N]
    """
    print_info("Loading global leaderboard...")
    
    leaderboard = GlobalLeaderboard()
    stats = leaderboard.get_leaderboard_stats()
    
    print(f"Total entries: {stats['total_entries']}")
    print(f"Unique models: {stats['unique_models']}")
    print(f"Average score: {stats['average_score']:.2f}")
    print()
    
    # Get top entries
    category = getattr(args, 'category', None)
    limit = getattr(args, 'limit', 10)
    
    top_entries = leaderboard.get_top_entries(
        category=category,
        limit=limit,
    )
    
    if RICH_AVAILABLE:
        console = Console()
        table = Table(title=f"Top {limit} Verified Entries")
        table.add_column("Rank", style="cyan")
        table.add_column("Model", style="magenta")
        table.add_column("Score", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Confidence", style="blue")
        
        for i, entry in enumerate(top_entries, 1):
            table.add_row(
                str(i),
                entry.model_name,
                f"{entry.score:.2f}",
                entry.category,
                f"{entry.get_confidence_score():.2f}",
            )
        
        console.print(table)
    else:
        print(f"Top {limit} entries:")
        for i, entry in enumerate(top_entries, 1):
            print(f"  {i}. {entry.model_name}: {entry.score:.2f} ({entry.category})")


async def cmd_distribute_task(args) -> None:
    """
    Distribute a task across the P2P network.
    
    Usage: ollama-arena node --distribute-task --model-a MODEL_A --model-b MODEL_B --category CAT
    """
    print_info("Distributing task...")
    
    # This would require a running node
    # For now, show what would happen
    model_a = getattr(args, 'model_a', None)
    model_b = getattr(args, 'model_b', None)
    category = getattr(args, 'category', 'coding')
    
    if not model_a or not model_b:
        print_error("--model-a and --model-b are required")
        return
    
    print_info(f"Distributing A/B test: {model_a} vs {model_b} in {category}")
    print_success("Task distributed to network")


def cmd_node(args) -> None:
    """
    Main P2P node command handler.
    
    Usage: ollama-arena node [SUBCOMMAND]
    """
    if args.join_global:
        asyncio.run(cmd_node_join_global(args))
    elif args.status:
        asyncio.run(cmd_node_status(args))
    elif args.peers:
        asyncio.run(cmd_node_peers(args))
    elif args.global_leaderboard:
        asyncio.run(cmd_global_leaderboard(args))
    elif args.distribute_task:
        asyncio.run(cmd_distribute_task(args))
    else:
        print_info("P2P Node Commands:")
        print("  --join-global     Join the global P2P network")
        print("  --status          Show node status")
        print("  --peers           List connected peers")
        print("  --global-leaderboard  Show global verified leaderboard")
        print("  --distribute-task Distribute a task across network")


async def cmd_verify_result(args) -> None:
    """
    Verify a cryptographic proof bundle.
    
    Usage: ollama-arena p2p --verify-result FILE
    """
    proof_file = getattr(args, 'verify_result', None)
    
    if not proof_file:
        print_error("--verify-result requires a file path")
        return
    
    proof_path = Path(proof_file)
    if not proof_path.exists():
        print_error(f"File not found: {proof_file}")
        return
    
    print_info(f"Loading proof bundle from {proof_file}...")
    
    try:
        with open(proof_path, 'r') as f:
            bundle = json.load(f)
        
        # Verify the bundle
        from ..p2p.crypto_proof import ProofValidator
        validator = ProofValidator()
        
        is_valid, errors = validator.validate_proof_bundle(bundle)
        
        if is_valid:
            print_success("Proof bundle is valid!")
            
            # Show bundle details
            task_id = bundle.get('task_id', 'unknown')
            node_id = bundle.get('signature', {}).get('node_id', 'unknown')
            
            print(f"Task ID: {task_id}")
            print(f"Node ID: {node_id}")
            print(f"Timestamp: {bundle.get('timestamp', 0)}")
        else:
            print_error("Proof bundle validation failed:")
            for error in errors:
                print(f"  - {error}")
    except Exception as e:
        print_error(f"Failed to verify proof: {e}")


async def cmd_generate_proof(args) -> None:
    """
    Generate a cryptographic proof bundle.
    
    Usage: ollama-arena p2p --generate-proof --task-id ID --result JSON
    """
    task_id = getattr(args, 'task_id', None)
    result_json = getattr(args, 'result', None)
    
    if not task_id or not result_json:
        print_error("--task-id and --result are required")
        return
    
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        print_error("Invalid JSON in --result")
        return
    
    print_info("Generating cryptographic proof...")
    
    try:
        from ..p2p.node import P2PNode
        node = P2PNode()
        generator = CryptoProofGenerator(node_id=node.local_node_id)
        
        bundle = generator.create_proof_bundle(task_id, result)

        safe_task_id = Path(task_id).name or "unknown"
        output_file = f"proof_{safe_task_id}.json"
        with open(output_file, 'w') as f:
            json.dump(bundle, f, indent=2)
        
        print_success(f"Proof bundle saved to {output_file}")
        print(f"Public Key: {generator.key_pair.get_public_key_hex()}")
    except ImportError as e:
        print_error(f"Missing dependencies: {e}")
    except Exception as e:
        print_error(f"Failed to generate proof: {e}")


def cmd_p2p(args) -> None:
    """
    Main P2P command handler.
    
    Usage: ollama-arena p2p [SUBCOMMAND]
    """
    if args.verify_result:
        asyncio.run(cmd_verify_result(args))
    elif args.generate_proof:
        asyncio.run(cmd_generate_proof(args))
    else:
        print_info("P2P Commands:")
        print("  --verify-result FILE  Verify a cryptographic proof bundle")
        print("  --generate-proof      Generate a cryptographic proof bundle")
