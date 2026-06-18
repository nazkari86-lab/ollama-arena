"""CLI package entry point."""
from __future__ import annotations

import argparse
import sys

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
