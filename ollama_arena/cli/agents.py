"""Agent commands: council, resolve-issue, optimize-prompt, review-pr."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .common import _console, _make_arena


def _anonymize(text: str, mapping: dict[str, str]) -> str:
    out = text
    for real, alias in mapping.items():
        out = out.replace(real, alias)
    return out


def _build_blind_mapping(models: list[str]) -> dict[str, str]:
    labels = [chr(ord("A") + i) for i in range(len(models))]
    return {m: f"Councilor {lbl}" for m, lbl in zip(models, labels)}


def cmd_council(args):
    c = _console()
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.rule import Rule

    models = [m.strip() for m in args.models.split(",")]
    if len(models) < 2:
        c.print("[red]Council requires at least 2 models[/red]")
        sys.exit(1)

    arena = _make_arena(args)
    if not arena.client.is_alive():
        c.print("[red]✗ Backend not reachable.[/red]")
        sys.exit(1)

    topic = args.topic
    rounds = getattr(args, "rounds", 2)
    blind = getattr(args, "blind", False)
    blind_map = _build_blind_mapping(models) if blind else {}

    c.print(Panel(
        f"[bold]LLM Council Convened[/bold]\n"
        f"Models : [cyan]{', '.join(models)}[/cyan]\n"
        f"Topic  : [yellow]{topic}[/yellow]\n"
        f"Rounds : [yellow]{rounds}[/yellow]\n"
        f"Blind  : [yellow]{'yes' if blind else 'no'}[/yellow]",
        title="ollama-arena council",
    ))

    history: list[dict[str, str]] = []
    scores: dict[str, int] = {m: 0 for m in models}

    for r in range(1, rounds + 1):
        c.print(Rule(f"[bold]Round {r}[/bold]"))
        round_responses: dict[str, str] = {}
        for m in models:
            prompt = f"Topic to discuss: {topic}\n\n"
            if r == 1:
                prompt += (
                    "Please provide your initial thoughts, detailed analysis, "
                    "and proposed solution. Be analytical."
                )
            else:
                prompt += "Here are anonymized thoughts from other council members:\n\n"
                for other_m, other_resp in history[-1].items():
                    if other_m != m:
                        label = blind_map.get(other_m, other_m) if blind else other_m
                        body = _anonymize(other_resp, blind_map) if blind else other_resp
                        prompt += f"--- {label} argued:\n{body}\n\n"
                prompt += (
                    "Review the other arguments. Acknowledge valid points, note flaws, "
                    "and provide your refined conclusion."
                )

            with c.status(f"[cyan]{m}[/cyan] is deliberating..."):
                res = arena.client.generate(m, prompt)

            round_responses[m] = res.text
            display_name = blind_map.get(m, m) if blind else m
            c.print(f"[bold cyan]{display_name}[/bold cyan]:")
            c.print(Markdown(res.text))
            c.print()

        if r > 1 and blind:
            for m in models:
                review_prompt = (
                    f"Topic: {topic}\n\nYou previously wrote:\n{round_responses[m]}\n\n"
                    "Other council members wrote:\n"
                )
                for other_m, other_resp in round_responses.items():
                    if other_m == m:
                        continue
                    review_prompt += f"- {_anonymize(other_resp, blind_map)}\n"
                review_prompt += (
                    "\nScore each other response 0-10 for quality and correctness. "
                    "Reply as JSON: {\"scores\": {\"Councilor A\": 8, ...}, \"notes\": \"...\"}"
                )
                review = arena.client.generate(m, review_prompt)
                try:
                    parsed = json.loads(re.search(r"\{.*\}", review.text, re.S).group())
                    for alias, val in (parsed.get("scores") or {}).items():
                        for real, mapped in blind_map.items():
                            if mapped == alias or real in alias:
                                scores[real] += int(val)
                except Exception:
                    pass

        history.append(round_responses)

    if blind and any(scores.values()):
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        c.print(Rule("[bold]Blind consensus scores[/bold]"))
        for model, score in ranked:
            c.print(f"  {model}: {score}")

    c.print(Rule("[bold green]Council Concluded[/bold green]"))


def cmd_resolve_issue(args):
    c = _console()
    from rich.panel import Panel
    from rich.markdown import Markdown
    from ..agent_loop import run_agent_sync

    model = args.model.strip()
    issue_path = Path(args.issue)
    issue = issue_path.read_text(encoding="utf-8") if issue_path.is_file() else args.issue

    arena = _make_arena(args)
    if not arena.client.is_alive():
        c.print("[red]✗ Backend not reachable.[/red]")
        sys.exit(1)

    os.environ["ARENA_MCP_MOCK"] = "0"
    arena.mcp.use_mock = False

    c.print(Panel(
        f"[bold]Autonomous Agent Mode[/bold]\n"
        f"Model: [cyan]{model}[/cyan]\n"
        f"Issue: [yellow]{issue[:200]}{'…' if len(issue) > 200 else ''}[/yellow]\n"
        f"Max Steps: [yellow]{args.max_steps}[/yellow]",
        title="ollama-arena resolve-issue",
    ))

    with c.status(f"[cyan]{model}[/cyan] is working autonomously (this may take a while)..."):
        res = run_agent_sync(
            backend=arena.client,
            model=model,
            instruction=(
                "You are an autonomous AI software engineer. Resolve the following issue:\n\n"
                f"{issue}\n\nUse your available tools to explore the codebase, plan, and write "
                "code. Do not stop until you have completely resolved the issue."
            ),
            mcp=arena.mcp,
            max_steps=args.max_steps,
        )

    c.print(f"\n[bold green]Final Result ({res.finish_reason}):[/bold green]")
    c.print(Markdown(res.text))

    trace = getattr(res, "agent_trace", []) or []
    tool_steps = []
    for step in trace:
        if step.get("tool_calls"):
            tools = [
                tc.get("function", {}).get("name", "")
                for tc in step["tool_calls"]
            ]
            tool_steps.append({"step": step.get("step"), "tools": tools})
            c.print(f"[dim]Step {step.get('step')}: Used {', '.join(tools)}[/dim]")

    report = {
        "model": model,
        "issue": issue,
        "finish_reason": res.finish_reason,
        "result": res.text,
        "steps": len(trace),
        "tool_steps": tool_steps,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    report_path = getattr(args, "report", None) or "resolve_report.json"
    Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    c.print(f"\n[dim]JSON report → {report_path}[/dim]")


def cmd_optimize_prompt(args):
    c = _console()
    from rich.panel import Panel
    from ..finetune.analyzer import analyze_task_failures
    from ..genome.registry import CanonicalRegistry

    model = args.model.strip()
    category = args.category
    c.print(Panel(
        f"[bold]Prompt Optimizer[/bold]\n"
        f"Model: [cyan]{model}[/cyan]\n"
        f"Target Category: [yellow]{category}[/yellow]",
        title="ollama-arena optimize-prompt",
    ))

    arena = _make_arena(args)
    if not arena.client.is_alive():
        c.print("[red]✗ Backend not reachable.[/red]")
        sys.exit(1)

    failures = analyze_task_failures(
        db_path=args.db,
        model=model,
        category=None if category == "all" else category,
        score_threshold=0.5,
    )
    c.print(f"[dim]Step 1: Found {len(failures)} task-level failure records[/dim]")

    registry = CanonicalRegistry()
    genome_id = registry.match_by_name(model)
    genome_hint = ""
    if genome_id:
        canonical = registry.get(genome_id) or {}
        family = canonical.get("family", "")
        org = canonical.get("org", "")
        genome_hint = f"You are a {family} model from {org}. " if family else ""
        c.print(f"[dim]Step 2: Genome match → {genome_id} ({family})[/dim]")
    else:
        c.print("[dim]Step 2: No genome match — using generic optimizer[/dim]")

    failure_summary = "\n".join(
        f"- {f['task_id']} ({f['category']}): avg score {f['avg_score']}"
        for f in failures[:8]
    ) or "No recorded failures."

    opt_prompt = (
        f"{genome_hint}You are an expert AI assistant optimized for arena benchmarks.\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Think step-by-step before answering.\n"
        "2. Address these known weak areas:\n"
        f"{failure_summary}\n"
        "3. Be precise, avoid filler, and verify logic before responding.\n"
    )

    c.print("[dim]Step 3: Evaluating candidate prompt via model self-review...[/dim]")
    review = arena.client.generate(
        model,
        f"Improve this system prompt for category '{category}':\n{opt_prompt}\n"
        "Return only the improved prompt text.",
    )
    optimized = review.text.strip() if review.ok and review.text.strip() else opt_prompt

    c.print("\n[bold green]✓ Optimization Complete[/bold green]")
    c.print(Panel(optimized, title="Optimized System Prompt"))


def _parse_review_findings(text: str, model: str) -> list[dict]:
    findings = []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sev = "note"
        lower = line.lower()
        if any(w in lower for w in ("critical", "security", "vulnerability", "cve")):
            sev = "error"
        elif any(w in lower for w in ("bug", "fix", "issue", "wrong")):
            sev = "warning"
        findings.append({
            "ruleId": f"arena/review/{model}/{i}",
            "level": sev,
            "message": {"text": line},
        })
    return findings


def _findings_to_sarif(findings: list[dict], tool_name: str) -> dict:
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": tool_name,
                    "informationUri": "https://github.com/ollama-arena",
                    "rules": [{"id": f["ruleId"], "shortDescription": {"text": f["message"]["text"][:80]}}
                              for f in findings],
                }
            },
            "results": findings,
        }],
    }


def cmd_review_pr(args):
    c = _console()
    from rich.panel import Panel
    from rich.markdown import Markdown

    models = [m.strip() for m in args.models.split(",")]
    file_filter = getattr(args, "files", None)

    try:
        cmd = ["git", "diff", "HEAD"]
        if file_filter:
            cmd.extend(file_filter.split(","))
        diff = subprocess.run(cmd, capture_output=True, text=True).stdout
        if not diff:
            diff = subprocess.run(["git", "show", "HEAD"], capture_output=True, text=True).stdout
    except Exception as e:
        c.print(f"[red]Failed to get git diff: {e}[/red]")
        sys.exit(1)

    if not diff.strip():
        c.print("[yellow]No changes found in repository.[/yellow]")
        sys.exit(0)

    arena = _make_arena(args)
    c.print(Panel(
        f"Reviewing {len(diff.splitlines())} lines of changes with {len(models)} models.",
        title="ollama-arena review-pr",
    ))

    prompt = (
        "Review the following git diff. List findings as bullet points with severity "
        "(critical/warning/note). Identify bugs, security issues, and quality problems.\n\n"
        f"```diff\n{diff[:15000]}\n```"
    )

    all_findings: list[dict] = []
    for m in models:
        with c.status(f"[cyan]{m}[/cyan] is reviewing..."):
            res = arena.client.generate(m, prompt)
        c.print(f"\n[bold cyan]Review by {m}:[/bold cyan]")
        c.print(Markdown(res.text))
        all_findings.extend(_parse_review_findings(res.text, m))

    sarif_path = getattr(args, "sarif", None)
    if sarif_path:
        sarif = _findings_to_sarif(all_findings, "ollama-arena-review-pr")
        Path(sarif_path).write_text(json.dumps(sarif, indent=2), encoding="utf-8")
        c.print(f"\n[dim]SARIF report → {sarif_path} ({len(all_findings)} findings)[/dim]")
