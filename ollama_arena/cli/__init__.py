"""CLI package entry point."""
from __future__ import annotations

import argparse
import sys

from .agentic import cmd_long_horizon, cmd_redteam, cmd_sandbox, cmd_swarm
from .agents import cmd_council, cmd_optimize_prompt, cmd_resolve_issue, cmd_review_pr
from .common import add_common
from .mcp_cmd import cmd_mcp_diagnose, cmd_mcp_enable, cmd_mcp_disable, cmd_mcp_install, cmd_mcp_list
from .data import (
    cmd_anti_leaderboard,
    cmd_datasets,
    cmd_export,
    cmd_import,
    cmd_inspect,
    cmd_leaderboard,
    cmd_list,
    cmd_perf,
    cmd_publish,
    cmd_report,
    cmd_results,
    cmd_tasks,
)
from .finetune_cmd import cmd_finetune
from .genome_cmd import cmd_genome
from .match import cmd_benchmark, cmd_match, cmd_royale, cmd_tournament
from .p2p_cmd import cmd_node, cmd_p2p
from .sim_cmd import cmd_sim
from .web_cmd import cmd_web


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
    p.add_argument("--db", default="arena.db", metavar="PATH")
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    pb = sub.add_parser("benchmark",
                        help="Standardized 30-task Score (0–100) across all categories")
    pb.add_argument("models", metavar="MODEL[,MODEL2]",
                    help="One or more models to benchmark (comma-separated)")
    pb.add_argument("--compare", action="store_true",
                    help="Side-by-side comparison when 2 models given")
    pb.add_argument("--fail-below", type=float, default=None, metavar="SCORE",
                    help="Exit code 1 if any model scores below this (for CI)")
    pb.set_defaults(func=cmd_benchmark)

    pm = sub.add_parser("match", help="Head-to-head battle(s)")
    pm.add_argument("--models", required=True, metavar="A,B[,C...]")
    pm.add_argument("--category", default="coding",
                    choices=["coding", "reasoning", "security", "planning",
                             "inspection", "math", "knowledge", "creative",
                             "json_format", "tool_use", "vision", "all"])
    pm.add_argument("--difficulty", default=None, choices=["easy", "medium", "hard"])
    pm.add_argument("-n", type=int, default=10)
    pm.add_argument("--verbose", "-v", action="store_true",
                    help="Print full prompt + both responses for every task")
    pm.add_argument("--share", action="store_true",
                    help="Print a shareable markdown results table at the end")
    pm.add_argument("--tools", action="store_true",
                    help="Enable tool use (web search, etc.) for all tasks")
    add_common(pm)
    pm.set_defaults(func=cmd_match)

    pt = sub.add_parser("tournament", help="Round-robin tournament")
    pt.add_argument("--models", required=True)
    pt.add_argument("--category", default="coding")
    pt.add_argument("-n", type=int, default=5)
    add_common(pt)
    pt.set_defaults(func=cmd_tournament)

    pr = sub.add_parser("royale", help="N-way simultaneous battle royale")
    pr.add_argument("--models", required=True, metavar="A,B,C[,D...]",
                    help="At least 3 models comma-separated")
    pr.add_argument("--category", default="coding",
                    choices=["coding", "reasoning", "security", "planning",
                             "inspection", "math", "knowledge", "creative",
                             "json_format", "tool_use", "vision", "all"])
    pr.add_argument("--difficulty", default=None, choices=["easy", "medium", "hard"])
    pr.add_argument("-n", type=int, default=5)
    add_common(pr)
    pr.set_defaults(func=cmd_royale)

    pc = sub.add_parser("council", help="Multi-agent debate (LLM Council)")
    pc.add_argument("--models", required=True, metavar="A,B[,C...]",
                    help="Models to participate in the council")
    pc.add_argument("--topic", required=True,
                    help="The topic, question, or problem to debate")
    pc.add_argument("--rounds", type=int, default=2,
                    help="Number of debate rounds (default: 2)")
    pc.add_argument("--blind", action="store_true",
                    help="Blind review rounds with anonymized councilors")
    add_common(pc)
    pc.set_defaults(func=cmd_council)

    pi = sub.add_parser("resolve-issue", aliases=["resolve"],
                        help="Run autonomous agent to resolve an issue")
    pi.add_argument("--model", required=True, help="Model to use")
    pi.add_argument("--issue", required=True, help="Issue description or path to issue file")
    pi.add_argument("--max-steps", type=int, default=30, help="Maximum number of agent steps")
    pi.add_argument("--report", default="resolve_report.json",
                    help="Path for structured JSON report (default: resolve_report.json)")
    add_common(pi)
    pi.set_defaults(func=cmd_resolve_issue)

    po = sub.add_parser("optimize-prompt", help="Auto-optimize a model's system prompt")
    po.add_argument("--model", required=True, help="Model to optimize")
    po.add_argument("--category", default="all", help="Target task category for optimization")
    add_common(po)
    po.set_defaults(func=cmd_optimize_prompt)

    prv = sub.add_parser("review-pr", aliases=["pr"], help="Review current git diff using models")
    prv.add_argument("--models", required=True, help="Models to use for review (comma separated)")
    prv.add_argument("--sarif", default=None, metavar="PATH",
                     help="Write SARIF 2.1.0 report to this path")
    prv.add_argument("--files", default=None,
                     help="Comma-separated paths to limit git diff scope")
    add_common(prv)
    prv.set_defaults(func=cmd_review_pr)

    p_imp = sub.add_parser("import", help="Import a local CSV/JSON dataset")
    p_imp.add_argument("--file", required=True, help="Path to the dataset file")
    add_common(p_imp)
    p_imp.set_defaults(func=cmd_import)

    sub.add_parser("leaderboard", aliases=["lb"],
                   help="Show ELO rankings").set_defaults(func=cmd_leaderboard)

    sub.add_parser("anti-leaderboard", aliases=["alb"],
                   help="Show hallucination rankings").set_defaults(func=cmd_anti_leaderboard)

    sub.add_parser("list",
                   help="List models available on the backend").set_defaults(func=cmd_list)

    sub.add_parser("tasks",
                   help="List built-in task categories and counts").set_defaults(func=cmd_tasks)

    prs = sub.add_parser("results",
                         help="Browse match history and per-task details")
    prs.add_argument("--match", type=int, default=None,
                     help="Show all tasks from match <ID>")
    prs.add_argument("--last", type=int, default=10,
                     help="How many recent matches to list (default 10)")
    prs.add_argument("--full", action="store_true",
                     help="Print complete (untruncated) prompts and responses")
    prs.add_argument("--export", action="store_true",
                     help="Export match results to HTML/JSON in /reports folder")
    prs.set_defaults(func=cmd_results)

    pi2 = sub.add_parser("inspect",
                         help="Show every recorded run for a single task ID")
    pi2.add_argument("task_id", metavar="TASK_ID")
    pi2.add_argument("--full", action="store_true",
                     help="Print complete responses")
    pi2.set_defaults(func=cmd_inspect)

    prp = sub.add_parser("report",
                         help="Per-model category breakdown and strength/weakness analysis")
    prp.add_argument("--model", default=None,
                     help="Filter to a specific model (substring match)")
    prp.set_defaults(func=cmd_report)

    pd = sub.add_parser("datasets", help="HF dataset cache (pull / refresh)")
    pd.add_argument("--pull", default=None, help="Comma-sep names to download")
    pd.add_argument("--refresh", default=None, help="Comma-sep names to re-download")
    pd.add_argument("--limit", type=int, default=None)
    pd.set_defaults(func=cmd_datasets)

    pft = sub.add_parser("finetune", help="Unsloth pipeline (analyze/generate/train/run)")
    pft.add_argument("--run", action="store_true",
                     help="Full pipeline: analyze → generate → train → export")
    pft.add_argument("--analyze", action="store_true")
    pft.add_argument("--generate", action="store_true")
    pft.add_argument("--train", default=None, metavar="JSONL_PATH")
    pft.add_argument("--model", default=None)
    pft.add_argument("--teacher", default=None)
    pft.add_argument("--category", default="coding")
    pft.add_argument("--format", default="sft", choices=["sft", "dpo"],
                     help="Dataset format for --generate / --run")
    pft.add_argument("--out", default=None)
    pft.add_argument("--out-dir", default=None)
    pft.add_argument("--ollama-name", default=None,
                     help="Ollama model name when exporting after --run")
    pft.add_argument("--skip-train", action="store_true",
                     help="With --run, stop after dataset generation")
    pft.add_argument("--skip-export", action="store_true",
                     help="With --run, skip Ollama export after training")
    pft.add_argument("--n-tasks", type=int, default=50)
    pft.add_argument("--base-model", default=None)
    pft.add_argument("--epochs", type=int, default=2)
    pft.set_defaults(func=cmd_finetune)

    sub.add_parser("perf",
                   help="Performance stats (TPS, latency, TTFT per model)").set_defaults(func=cmd_perf)

    pex = sub.add_parser("export", help="Export shareable HTML dashboard")
    pex.add_argument("--out", default="arena_dashboard.html")
    pex.set_defaults(func=cmd_export)

    pp = sub.add_parser("publish", help="Upload ELO leaderboard and results to GitHub Gist")
    pp.add_argument("--public", action="store_true", help="Make the Gist public")
    pp.set_defaults(func=cmd_publish)

    pg = sub.add_parser("genome", help="LLM Genome Explorer — lineage and identity")
    genome_sub = pg.add_subparsers(dest="genome_cmd")
    pg_scan = genome_sub.add_parser("scan", help="Scan local Ollama models and resolve lineage")
    pg_scan.add_argument("--genome-db", default="genome.db", metavar="PATH")
    pg_tree = genome_sub.add_parser("tree", help="Print lineage tree in terminal")
    pg_tree.add_argument("--model", default=None, help="Filter to subtree of this model")
    pg_tree.add_argument("--genome-db", default="genome.db", metavar="PATH")
    pg_show = genome_sub.add_parser("show", help="Show genome card for a model")
    pg_show.add_argument("model", help="Local model name (e.g. llama3.1:8b)")
    pg_show.add_argument("--genome-db", default="genome.db", metavar="PATH")
    pg.set_defaults(func=cmd_genome)

    # MCP commands
    pmcp = sub.add_parser("mcp", help="MCP server management and diagnostics")
    pmcp_sub = pmcp.add_subparsers(dest="mcp_cmd", metavar="MCP_CMD")

    pmcp_diag = pmcp_sub.add_parser("diagnose", help="Diagnose MCP server availability")
    pmcp_diag.add_argument("--config", default=None, help="Path to MCP config file")
    pmcp_diag.set_defaults(func=cmd_mcp_diagnose)

    pmcp_list = pmcp_sub.add_parser("list", help="List all configured MCP servers")
    pmcp_list.add_argument("--config", default=None, help="Path to MCP config file")
    pmcp_list.set_defaults(func=cmd_mcp_list)

    pmcp_enable = pmcp_sub.add_parser("enable", help="Enable a specific MCP server")
    pmcp_enable.add_argument("server", help="Server name to enable")
    pmcp_enable.add_argument("--config", default=None, help="Path to MCP config file")
    pmcp_enable.set_defaults(func=cmd_mcp_enable)

    pmcp_disable = pmcp_sub.add_parser("disable", help="Disable a specific MCP server")
    pmcp_disable.add_argument("server", help="Server name to disable")
    pmcp_disable.add_argument("--config", default=None, help="Path to MCP config file")
    pmcp_disable.set_defaults(func=cmd_mcp_disable)

    pmcp_install = pmcp_sub.add_parser("install", help="Install a popular MCP server")
    pmcp_install.add_argument("server", help="Server template to install (sqlite, filesystem, memory, git, time)")
    pmcp_install.set_defaults(func=cmd_mcp_install)

    psb = sub.add_parser("sandbox", help="Manage VM sandboxes for isolated task execution")
    psb.add_argument("sandbox_action",
                     choices=["create", "execute", "stop", "list", "cleanup"],
                     help="Sandbox action to perform")
    psb.add_argument("--sandbox-id", dest="sandbox_id", default=None,
                     help="Sandbox identifier (required for create/execute/stop; "
                          "optional for cleanup — omit to clean up all)")
    psb.add_argument("--backend", dest="backend", default=None,
                     choices=["docker", "firecracker", "kubevirt", "mock"],
                     help="Sandbox backend (default: docker)")
    psb.add_argument("--cpu-limit", dest="cpu_limit", default="2",
                     help="CPU limit passed to the sandbox backend (default: 2)")
    psb.add_argument("--memory", dest="memory", default="4g",
                     help="Memory limit passed to the sandbox backend (default: 4g)")
    psb.add_argument("--timeout", dest="timeout", type=int, default=300,
                     help="Sandbox timeout in seconds (default: 300)")
    psb.add_argument("--no-network-isolation", action="store_true",
                     help="Disable network isolation for the sandbox")
    psb.add_argument("--task", default=None, help="Task to execute (with 'execute')")
    add_common(psb)
    psb.set_defaults(func=cmd_sandbox)

    psw = sub.add_parser("swarm", help="Run swarm battles between teams of agents")
    psw.add_argument("--mode", default="2v2", choices=["2v2", "3v3"],
                     help="Team size preset (default: 2v2)")
    psw.add_argument("--task", required=True, help="Task for the swarm to solve")
    psw.add_argument("--rounds", type=int, default=3)
    psw.add_argument("--max-steps", dest="max_steps", type=int, default=10,
                     help="Max steps per round (default: 10)")
    psw.add_argument("--team-a", dest="team_a", default=None, metavar="MODEL:ROLE[,MODEL:ROLE]",
                     help="Override Team A composition (default: example preset for --mode)")
    psw.add_argument("--team-b", dest="team_b", default=None, metavar="MODEL:ROLE[,MODEL:ROLE]",
                     help="Override Team B composition (default: example preset for --mode)")
    psw.add_argument("--output", default=None, metavar="PATH",
                     help="Save full results as JSON to this path")
    add_common(psw)
    psw.set_defaults(func=cmd_swarm)

    prt = sub.add_parser("redteam", help="Run red team arena for security evaluation")
    prt.add_argument("--attacker", required=True, help="Attacker model")
    prt.add_argument("--defender", required=True, help="Defender model")
    prt.add_argument("--context", required=True, help="Task context for the evaluation")
    prt.add_argument("--rounds", type=int, default=3)
    prt.add_argument("--severity", default=None, metavar="LOW,MEDIUM,...",
                     help="Comma-separated severity levels (default: low,medium,high,critical)")
    prt.add_argument("--no-adaptive", action="store_true",
                     help="Disable adaptive attack escalation")
    prt.add_argument("--timeout", type=int, default=60, help="Timeout per round in seconds")
    prt.add_argument("--output", default=None, metavar="PATH",
                     help="Save full results as JSON to this path")
    add_common(prt)
    prt.set_defaults(func=cmd_redteam)

    plh = sub.add_parser("long-horizon", aliases=["lh"],
                         help="Manage and execute long-horizon agent tasks")
    plh.add_argument("lh_action",
                     choices=["list", "start", "pause", "resume", "progress", "complete", "status"],
                     help="Long-horizon task action")
    plh.add_argument("--task-id", dest="task_id", default=None,
                     help="Task ID (required for all actions except 'list')")
    plh.add_argument("--checkpoint-dir", dest="checkpoint_dir", default="checkpoints",
                     help="Directory for task checkpoints (default: checkpoints)")
    plh.add_argument("--progress", type=float, default=0.0,
                     help="Progress percentage (with 'progress')")
    plh.add_argument("--step-description", dest="step_description", default="",
                     help="Description of the current step (with 'progress')")
    plh.set_defaults(func=cmd_long_horizon)

    pn = sub.add_parser("node", help="P2P Grid node management")
    pn.add_argument("--join-global", dest="join_global", action="store_true",
                    help="Join the global P2P network and run until interrupted")
    pn.add_argument("--status", action="store_true", help="Show node status")
    pn.add_argument("--peers", action="store_true", help="List discovered peers")
    pn.add_argument("--global-leaderboard", dest="global_leaderboard", action="store_true",
                    help="Show the global verified leaderboard")
    pn.add_argument("--distribute-task", dest="distribute_task", action="store_true",
                    help="Distribute an A/B test task across the network")
    pn.add_argument("--bootstrap", default=None, metavar="HOST:PORT[,HOST:PORT]",
                    help="Comma-separated bootstrap node addresses")
    pn.add_argument("--host", default="0.0.0.0")
    pn.add_argument("--port", type=int, default=8080)
    pn.add_argument("--model-a", dest="model_a", default=None)
    pn.add_argument("--model-b", dest="model_b", default=None)
    pn.add_argument("--category", default="coding")
    pn.add_argument("--limit", type=int, default=10)
    pn.set_defaults(func=cmd_node)

    pp2p = sub.add_parser("p2p", help="P2P Grid cryptographic proof utilities")
    pp2p.add_argument("--verify-result", dest="verify_result", default=None, metavar="FILE",
                      help="Verify a cryptographic proof bundle from FILE")
    pp2p.add_argument("--generate-proof", dest="generate_proof", action="store_true",
                      help="Generate a cryptographic proof bundle")
    pp2p.add_argument("--task-id", dest="task_id", default=None)
    pp2p.add_argument("--result", default=None, metavar="JSON",
                      help="Result data as a JSON string (with --generate-proof)")
    pp2p.set_defaults(func=cmd_p2p)

    psim = sub.add_parser("sim", help="Run/inspect agent-driven simulations (Mafia, Sims-world, ...)")
    psim.add_argument("--sim-db", dest="sim_db", default="sim.db", metavar="PATH")
    sim_sub = psim.add_subparsers(dest="sim_cmd", metavar="SIM_CMD")

    sim_sub.add_parser("list", help="List available simulation scenarios")

    psim_run = sim_sub.add_parser("run", help="Run a simulation scenario")
    psim_run.add_argument("scenario", help="Scenario name (see 'sim list')")
    psim_run.add_argument("--agents", required=True, metavar="MODEL[,MODEL2,...]",
                          help="Comma-separated model names, one per agent")
    psim_run.add_argument("--config", default=None, metavar="PATH",
                          help="Path to a JSON or YAML scenario config file")
    psim_run.add_argument("--seed", type=int, default=None)
    psim_run.add_argument("--ticks", type=int, default=1000, help="Max ticks before truncation")

    psim_bench = sim_sub.add_parser("benchmark", help="Run N episodes and compare metrics")
    psim_bench.add_argument("scenario", help="Scenario name (see 'sim list')")
    psim_bench.add_argument("--agents", required=True, metavar="MODEL[,MODEL2,...]")
    psim_bench.add_argument("--config", default=None, metavar="PATH")
    psim_bench.add_argument("--episodes", type=int, default=5)
    psim_bench.add_argument("--ticks", type=int, default=1000)

    psim_train = sim_sub.add_parser("train", help="Imitation-learn from a stored run's transitions")
    psim_train.add_argument("--run-id", dest="run_id", required=True)
    psim_train.add_argument("--epochs", type=int, default=10)

    psim_replay = sim_sub.add_parser("replay", help="Print a stored run's event log")
    psim_replay.add_argument("run_id")
    psim_replay.add_argument("--tick", type=int, default=None, help="Only events up to this tick")

    psim_inspect = sim_sub.add_parser("inspect", help="Show status/outcome/metrics for a run")
    psim_inspect.add_argument("run_id")

    psim.set_defaults(func=cmd_sim)

    pw = sub.add_parser("web", help="Launch web dashboard")
    pw.add_argument("--host", default="0.0.0.0")
    pw.add_argument("--port", type=int, default=7860)
    pw.set_defaults(func=cmd_web)

    args = p.parse_args()
    if not args.cmd:
        from .. import __version__
        from .._banner import print_banner
        print_banner(__version__)
        p.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
