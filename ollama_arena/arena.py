"""Pair-wise match driver and ELO bookkeeping."""
from __future__ import annotations
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Optional

from .agent_loop import run_agent_sync
from .backends import auto_backend, Backend, GenResult
from .backends.ollama import OllamaBackend
from .backends.openai_compat import OpenAICompatBackend
from .backends.auto import spec_backend_for_model
from .memory_scheduler import MemoryScheduler, Strategy, StrategyDecision
from .elo import EloStore
from .evaluator import evaluate
from .performance import PerfTracker
from .tasks import get_task, get_tasks

log = logging.getLogger("arena")


def _agent_trace_json(res: GenResult) -> str | None:
    trace = getattr(res, "agent_trace", None) or []
    if not trace:
        return None
    try:
        return json.dumps(trace)
    except (TypeError, ValueError):
        return None


@dataclass
class MatchResult:
    model_a: str
    model_b: str
    category: str
    tasks_run: int
    a_wins: int
    b_wins: int
    draws: int
    a_win_rate: float
    b_win_rate: float
    elo_a_before: float
    elo_b_before: float
    elo_a_after: float
    elo_b_after: float
    task_results: list[dict] = field(default_factory=list)
    duration_s: float = 0.0
    match_id: int = 0
    strategy:  str = "CONCURRENT"            # CONCURRENT | HOT_SWAP | PIPELINE
    strategy_reason: str = ""                # why the scheduler picked it


@dataclass
class RoyaleResult:
    models: list[str]
    category: str
    tasks_run: int
    winner: str
    rankings: list[dict] # {model, elo_after, total_score, rank}
    duration_s: float = 0.0
    royale_id: int = 0
    strategy: str = "CONCURRENT"


class Arena:
    """Pair-wise match driver with persistent ELO ratings.

    `backend` accepts a preset name ("ollama", "vllm", "lmstudio",
    "openai", "groq", ...), a full URL, or a Backend instance. If omitted,
    the legacy `ollama_url` kwarg is used (default :11434).
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        db_path: str = "arena.db",
        on_task_done: Optional[Callable] = None,
        backend: str | Backend | None = None,
        api_key: str | None = None,
        from_datasets: list[str] | None = None,
        judge_model: str | None = None,
    ):
        if backend is None:
            self.client = auto_backend(ollama_url)
        elif isinstance(backend, str):
            self.client = auto_backend(backend, api_key=api_key)
        else:
            self.client = backend

        self.elo  = EloStore(db_path=db_path)
        self.perf = PerfTracker(db_path=db_path)
        self._on_task_done = on_task_done
        self._extra_tasks: dict[str, list[dict]] = {}
        # Memory-Adaptive Pipeline Tournament — auto-picks CONCURRENT /
        # HOT_SWAP / PIPELINE so that big models on small machines stop
        # OOM-ing the arena.
        ollama_url = ollama_url if isinstance(ollama_url, str) else "http://localhost:11434"
        self.scheduler = MemoryScheduler(ollama_base=ollama_url)
        # Caller hook for "we're about to enter pipeline phase X" events.
        self._on_phase: Optional[Callable] = None

        # Experimental Open WebUI sync (opt-in via WEBUI_API_KEY) — lazy
        self._webui: object | None = None
        
        # MCP Orchestration — lazy: initialized only on first use to avoid
        # requiring Node.js / npx for every Arena() instantiation.
        self._mcp_config = {
            "sqlite": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sqlite"]},
            "playwright": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-playwright"]},
            "google": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-google-search"]},
            "searxng": {"url": "http://localhost:8080"}
        }
        self._mcp: object | None = None

        self.judge = None
        if judge_model:
            from .judge import LLMJudge
            self.judge = LLMJudge(self.client, judge_model)

        if from_datasets:
            for name in from_datasets:
                self.load_hf_dataset(name)

    @property
    def mcp(self) -> object:
        if self._mcp is None:
            from .mcp_client import MCPOrchestrator
            self._mcp = MCPOrchestrator(self._mcp_config)
        return self._mcp

    @property
    def webui(self):
        if self._webui is None:
            from .webui_bridge import WebUIBridge
            self._webui = WebUIBridge()
        return self._webui

    def load_hf_dataset(self, name: str, limit: int | None = None) -> int:
        from .datasets import load_dataset
        tasks = load_dataset(name, limit=limit)
        for t in tasks:
            cat = t.get("category", "coding")
            self._extra_tasks.setdefault(cat, []).append(t)
        log.info(f"[arena] loaded {len(tasks)} tasks from '{name}'")
        return len(tasks)

    def _gather_tasks(self, category: str, n: int,
                      difficulty: str | None = None) -> list[dict]:
        pool = list(get_tasks(category=category, difficulty=difficulty))
        pool += self._extra_tasks.get(category, [])
        if difficulty:
            pool = [t for t in pool if t.get("difficulty") == difficulty]
        return pool[:n]

    def run_match(
        self,
        model_a: str,
        model_b: str,
        category: str = "coding",
        n: int = 10,
        difficulty: str | None = None,
        concurrency: int = 1,
        use_tools: bool = False,
    ) -> MatchResult:
        # Clear Ollama cache / unload loaded models before the match
        if getattr(self.client, "name", "") == "ollama" and hasattr(self.client, "base"):
            try:
                import requests
                r = requests.get(f"{self.client.base}/api/ps", timeout=3)
                if r.ok:
                    for m in r.json().get("models", []):
                        requests.post(f"{self.client.base}/api/generate", 
                                      json={"model": m["name"], "keep_alive": 0}, 
                                      timeout=3)
            except Exception as e:
                log.warning(f"Failed to clear Ollama memory cache: {e}")

        tasks = self._gather_tasks(category, n, difficulty)
        if not tasks:
            raise ValueError(
                f"No tasks for category='{category}' difficulty='{difficulty}'. "
                f"Available: {list(self._extra_tasks.keys())}"
            )

        elo_a_before = self.elo.get(model_a)
        elo_b_before = self.elo.get(model_b)
        a_wins = b_wins = draws = 0
        task_results = []
        t0 = time.time()
        last_match_id = 0

        from concurrent.futures import ThreadPoolExecutor

        # Per-model backend routing: spec: models get their own llama-server backend
        client_a = spec_backend_for_model(model_a) or self.client
        client_b = spec_backend_for_model(model_b) or self.client

        # ── NEW: pick a memory-aware execution strategy ──────────────────
        decision = self.scheduler.choose(model_a, model_b)
        log.info(f"[scheduler] {decision.strategy.value}: {decision.reason}")
        if self._on_phase:
            try:
                self._on_phase({"type": "strategy", **decision.to_dict()})
            except Exception:
                pass
        if decision.strategy is Strategy.INSUFFICIENT:
            raise RuntimeError(
                f"Not enough memory to run this match. {decision.reason}"
            )

        def _score_and_pack(task, res_a: GenResult, res_b: GenResult,
                            cached_a: bool, cached_b: bool) -> dict | None:
            if self.judge and task.get("use_judge"):
                jr = self.judge.grade_pair(
                    task["instruction"], res_a.text, res_b.text,
                    reference=task.get("expected_answer", ""),
                )
                score_a, score_b = jr.score_a, jr.score_b
            else:
                trace_a = getattr(res_a, "agent_trace", None) if res_a.ok else None
                trace_b = getattr(res_b, "agent_trace", None) if res_b.ok else None
                score_a = evaluate(task, res_a.text, trace=trace_a, judge=self.judge) if res_a.ok else 0.0
                score_b = evaluate(task, res_b.text, trace=trace_b, judge=self.judge) if res_b.ok else 0.0

            if score_a is None or score_b is None:
                log.warning(f"[arena] skipping task {task['id']}: needs judge.")
                return None

            if score_a > score_b:   outcome = "a_wins"
            elif score_b > score_a: outcome = "b_wins"
            else:                   outcome = "draw"
            return {"task": task, "res_a": res_a, "res_b": res_b,
                    "cached_a": cached_a, "cached_b": cached_b,
                    "score_a": score_a, "score_b": score_b,
                    "outcome": outcome}

        # Dynamic timeout — large models on PIPELINE need more wall-clock
        # because they swap to SSD; HOT_SWAP needs the unload+reload time too.
        _timeout_for_strategy = {
            Strategy.CONCURRENT: 600,   # 10 minutes
            Strategy.HOT_SWAP:   1200,  # 20 minutes
            Strategy.PIPELINE:   3600,  # 60 minutes (for huge outputs)
        }
        _gen_timeout = _timeout_for_strategy.get(decision.strategy, 180)

        def _gen(model: str, client: Backend, task: dict,
                 unload_first: Optional[str] = None) -> tuple[GenResult, bool]:
            """Return (GenResult, was_cached). Honors `unload_first` for HOT_SWAP."""
            cached = self.elo.get_cached_response(
                model, task["id"], task["instruction"])
            if cached:
                return GenResult(text=cached, model=model, tps=0.0,
                                 latency_s=0.0), True
            if unload_first:
                self.scheduler.unload(unload_first)

            if use_tools or task.get("category") == "tool_use":
                try:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        fut = pool.submit(
                            run_agent_sync,
                            client,
                            model,
                            task["instruction"],
                            self.mcp,
                            images=task.get("images")
                        )
                        return fut.result(timeout=_gen_timeout), False
                except FuturesTimeoutError:
                    return GenResult(
                        text="",
                        model=model,
                        error=f"agent timeout after {_gen_timeout}s",
                    ), False
                except Exception as e:
                    log.error(f"[arena] agent loop failed: {e}")
                    return GenResult(text="", model=model, error=str(e)), False

            return client.generate(model, task["instruction"], images=task.get("images")), False

        def _execute_concurrent(task):
            res_a, ca = _gen(model_a, client_a, task)
            res_b, cb = _gen(model_b, client_b, task)
            return _score_and_pack(task, res_a, res_b, ca, cb)

        def _execute_hotswap(task):
            # Evict B before generating A, then evict A before generating B.
            # Inside a single task the model stays loaded; the swap happens
            # *between* tasks naturally on the next call.
            res_a, ca = _gen(model_a, client_a, task, unload_first=model_b)
            res_b, cb = _gen(model_b, client_b, task, unload_first=model_a)
            return _score_and_pack(task, res_a, res_b, ca, cb)

        def _execute_pipelined(tasks_list):
            """The breakthrough: generate ALL tasks vs A, unload, ALL vs B."""
            # Phase 1 — model A
            self.scheduler.unload_all_except([model_a])
            if self._on_phase:
                try: self._on_phase({"type":"phase_start","phase":1,
                                     "model":model_a,"total":len(tasks_list)})
                except Exception: pass
            a_outs: list[tuple[GenResult, bool]] = []
            # Pre-warm B's blob into OS page cache while A is generating
            self.scheduler.prefetch(model_b)
            for i, task in enumerate(tasks_list, 1):
                res, c = _gen(model_a, client_a, task)
                a_outs.append((res, c))
                if self._on_phase:
                    try: self._on_phase({"type":"phase_progress","phase":1,
                                         "i":i,"total":len(tasks_list),
                                         "task_id":task["id"]})
                    except Exception: pass
            # Phase 2 — unload A, run model B on every task
            self.scheduler.unload(model_a)
            self.scheduler.unload_all_except([model_b])
            if self._on_phase:
                try: self._on_phase({"type":"phase_start","phase":2,
                                     "model":model_b,"total":len(tasks_list)})
                except Exception: pass
            b_outs: list[tuple[GenResult, bool]] = []
            for i, task in enumerate(tasks_list, 1):
                res, c = _gen(model_b, client_b, task)
                b_outs.append((res, c))
                if self._on_phase:
                    try: self._on_phase({"type":"phase_progress","phase":2,
                                         "i":i,"total":len(tasks_list),
                                         "task_id":task["id"]})
                    except Exception: pass
            # Phase 3 — score every pair
            return [
                _score_and_pack(tasks_list[i], a_outs[i][0], b_outs[i][0],
                                a_outs[i][1], b_outs[i][1])
                for i in range(len(tasks_list))
            ]

        # ── dispatch by strategy ────────────────────────────────────────
        if decision.strategy is Strategy.PIPELINE:
            results = _execute_pipelined(tasks)
        elif decision.strategy is Strategy.HOT_SWAP:
            # HOT_SWAP serialized for memory safety — concurrency=1 only
            results = [_execute_hotswap(t) for t in tasks]
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                results = list(executor.map(_execute_concurrent, tasks))

        # Filter out skipped tasks (None)
        results = [r for r in results if r is not None]

        for r in results:
            task = r["task"]
            res_a, res_b = r["res_a"], r["res_b"]
            cached_a, cached_b = r["cached_a"], r["cached_b"]
            score_a, score_b = r["score_a"], r["score_b"]
            outcome = r["outcome"]

            if not cached_a:
                self._log_perf(model_a, res_a, task.get("category"))
            if not cached_b:
                self._log_perf(model_b, res_b, task.get("category"))

            if outcome == "a_wins": a_wins += 1
            elif outcome == "b_wins": b_wins += 1
            else: draws += 1

            self.elo.record_match(model_a, model_b, category, score_a, score_b)
            last_match_id = self.elo.last_match_id()

            # Hallucination check (if judge enabled)
            halluc_a = halluc_b = None
            if self.judge:
                try:
                    halluc_a = self.judge.check_hallucination(task["instruction"], res_a.text, 
                                                              reference=str(task.get("expected_answer", "")))
                    halluc_b = self.judge.check_hallucination(task["instruction"], res_b.text,
                                                              reference=str(task.get("expected_answer", "")))
                except Exception as e:
                    log.warning(f"Hallucination check failed: {e}")

            self.elo.save_task_detail(
                match_id=last_match_id,
                task_id=task["id"],
                category=task.get("category", category),
                difficulty=task.get("difficulty", "unknown"),
                language=task.get("language", "natural"),
                instruction=task["instruction"],
                response_a=res_a.text if res_a.ok else f"[ERROR: {res_a.error}]",
                response_b=res_b.text if res_b.ok else f"[ERROR: {res_b.error}]",
                expected=str(task.get("expected_answer", task.get("expected_vulns", ""))),
                score_a=round(score_a, 3),
                score_b=round(score_b, 3),
                outcome=outcome,
                tps_a=res_a.tps,
                tps_b=res_b.tps,
                latency_a=res_a.latency_s,
                latency_b=res_b.latency_s,
                tool_call_a=_agent_trace_json(res_a),
                tool_call_b=_agent_trace_json(res_b),
                hallucination_a=halluc_a,
                hallucination_b=halluc_b,
            )

            task_results.append({
                "task_id":     task["id"],
                "difficulty":  task.get("difficulty", "?"),
                "language":    task.get("language", "natural"),
                "instruction": task["instruction"],
                "response_a":  res_a.text if res_a.ok else "",
                "response_b":  res_b.text if res_b.ok else "",
                "expected":    str(task.get("expected_answer", "")),
                "score_a":     round(score_a, 3),
                "score_b":     round(score_b, 3),
                "tps_a":       res_a.tps,
                "tps_b":       res_b.tps,
                "latency_a":   res_a.latency_s,
                "latency_b":   res_b.latency_s,
                "outcome":     outcome,
            })

            log.info(
                f"[{task['id']}] {model_a}={score_a:.2f} ({res_a.tps:.0f}tps)  "
                f"{model_b}={score_b:.2f} ({res_b.tps:.0f}tps)  → {outcome}"
            )
            if self._on_task_done:
                self._on_task_done(
                    task["id"], score_a, score_b, outcome,
                    task["instruction"],
                    res_a.text if res_a.ok else "",
                    res_b.text if res_b.ok else "",
                    str(task.get("expected_answer", "")),
                )

        total = len(tasks)
        match_result = MatchResult(
            model_a=model_a, model_b=model_b, category=category,
            tasks_run=total, a_wins=a_wins, b_wins=b_wins, draws=draws,
            a_win_rate=round(a_wins / total, 3),
            b_win_rate=round(b_wins / total, 3),
            elo_a_before=elo_a_before, elo_b_before=elo_b_before,
            elo_a_after=self.elo.get(model_a),
            elo_b_after=self.elo.get(model_b),
            task_results=task_results,
            duration_s=round(time.time() - t0, 1),
            match_id=last_match_id,
            strategy=decision.strategy.value,
            strategy_reason=decision.reason,
        )
        self._sync_webui_bridge(match_result)
        return match_result

    def run_tournament(
        self,
        models: list[str],
        category: str = "coding",
        n_per_match: int = 5,
    ) -> list[dict]:
        pairs = list(combinations(models, 2))
        log.info(f"[tournament] {len(models)} models × {len(pairs)} matches × {n_per_match} tasks")
        for i, (a, b) in enumerate(pairs, 1):
            log.info(f"[tournament] {i}/{len(pairs)}: {a} vs {b}")
            self.run_match(a, b, category=category, n=n_per_match)
        return self.leaderboard()

    def retry_task(self, task_id: str) -> dict:
        """Rerun the most recent record of ``task_id``.

        Cheap one-shot reruns let the user re-do a single task when a
        Docker error / network blip / OOM truncated one side's response.
        Pulls the original instruction, model_a, model_b, category, and
        expected from the last task_detail row, regenerates both, scores,
        updates ELO with that single sample, and returns the new pair.
        """
        runs = self.elo.task_history(task_id)
        if not runs:
            raise ValueError(f"No prior record for task_id={task_id!r}")
        last = runs[0]
        model_a, model_b = last["model_a"], last["model_b"]
        category         = last.get("category", "coding")
        instruction      = last["instruction"]
        expected         = last.get("expected", "")
        # Build a synthetic task object that evaluate() understands
        task = {
            "id":               task_id,
            "instruction":      instruction,
            "expected_answer":  expected,
            "category":         category,
            "difficulty":       last.get("difficulty", "unknown"),
            "language":         "natural",
        }
        known = get_task(task_id)
        if known:
            for key, val in known.items():
                if key not in task or task.get(key) in ("", None, "natural"):
                    task[key] = val
        client_a = spec_backend_for_model(model_a) or self.client
        client_b = spec_backend_for_model(model_b) or self.client

        def _retry_gen(client: Backend, model: str) -> GenResult:
            if category == "tool_use":
                with ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(
                        run_agent_sync, client, model, instruction, self.mcp
                    ).result(timeout=480)
            return client.generate(model, instruction)

        res_a = _retry_gen(client_a, model_a)
        res_b = _retry_gen(client_b, model_b)

        if self.judge and task.get("use_judge"):
            jr = self.judge.grade_pair(instruction, res_a.text, res_b.text,
                                       reference=expected)
            score_a, score_b = jr.score_a, jr.score_b
        else:
            trace_a = getattr(res_a, "agent_trace", None) if res_a.ok else None
            trace_b = getattr(res_b, "agent_trace", None) if res_b.ok else None
            score_a = evaluate(task, res_a.text, trace=trace_a, judge=self.judge) if res_a.ok else 0.0
            score_b = evaluate(task, res_b.text, trace=trace_b, judge=self.judge) if res_b.ok else 0.0

        if score_a is None or score_b is None:
            return {"ok": False, "error": f"Task {task_id} requires a judge model."}

        if score_a > score_b: outcome = "a_wins"
        elif score_b > score_a: outcome = "b_wins"
        else: outcome = "draw"

        # ELO + persistence (a single-sample update)
        self.elo.record_match(model_a, model_b, category, score_a, score_b)
        match_id = self.elo.last_match_id()
        self.elo.save_task_detail(
            match_id=match_id, task_id=task_id, category=category,
            difficulty=task["difficulty"], language=task["language"],
            instruction=instruction,
            response_a=res_a.text if res_a.ok else f"[ERROR: {res_a.error}]",
            response_b=res_b.text if res_b.ok else f"[ERROR: {res_b.error}]",
            expected=str(expected),
            score_a=round(score_a, 3), score_b=round(score_b, 3),
            outcome=outcome,
            tps_a=res_a.tps, tps_b=res_b.tps,
            latency_a=res_a.latency_s, latency_b=res_b.latency_s,
            tool_call_a=_agent_trace_json(res_a),
            tool_call_b=_agent_trace_json(res_b),
        )
        self._log_perf(model_a, res_a, category)
        self._log_perf(model_b, res_b, category)

        return {
            "ok": True,
            "task_id":   task_id,
            "model_a":   model_a,
            "model_b":   model_b,
            "response_a": res_a.text if res_a.ok else f"[ERROR: {res_a.error}]",
            "response_b": res_b.text if res_b.ok else f"[ERROR: {res_b.error}]",
            "score_a":   round(score_a, 3),
            "score_b":   round(score_b, 3),
            "outcome":   outcome,
            "tps_a":     res_a.tps, "tps_b": res_b.tps,
            "latency_a": res_a.latency_s, "latency_b": res_b.latency_s,
            "elo_a_after": self.elo.get(model_a),
            "elo_b_after": self.elo.get(model_b),
        }

    def leaderboard(self) -> list[dict]:
        return self.elo.leaderboard()

    def _sync_webui_bridge(self, result: MatchResult) -> None:
        """Push match summary + leaderboard to Open WebUI when configured."""
        if not getattr(self, "webui", None):
            return
        if not os.environ.get("WEBUI_API_KEY"):
            return
        try:
            summary = (
                f"Match #{result.match_id}: {result.model_a} vs {result.model_b} "
                f"({result.category}) — {result.a_wins}-{result.b_wins}-{result.draws} "
                f"in {result.duration_s}s"
            )
            self.webui.broadcast_match_result(summary)
            self.webui.sync_leaderboard(self.leaderboard())
        except Exception as e:
            log.warning(f"[webui] post-match sync failed: {e}")

    def match_history(self, limit: int = 20) -> list[dict]:
        return self.elo.match_history(limit=limit)

    def performance_stats(self) -> dict:
        return self.perf.export_summary()

    def _log_perf(self, model: str, res: GenResult, category: str | None = None):
        if res.ok:
            backend_name = res.backend_type or self.client.name
            self.perf.record(
                model=model, backend=backend_name,
                tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                latency_s=res.latency_s, tps=res.tps,
                time_to_first=res.time_to_first,
                category=category,
            )
            for step in getattr(res, "agent_trace", []) or []:
                for tr in step.get("tool_results") or []:
                    lat = tr.get("latency_s")
                    if lat is not None and tr.get("name"):
                        self.perf.record_tool(tr["name"], model, lat, category=category)

    def run_royale(
        self,
        models: list[str],
        category: str = "coding",
        n: int = 5,
        difficulty: str | None = None,
        concurrency: int = 1,
    ) -> RoyaleResult:
        """Run an N-way Battle Royale between models on a shared set of tasks."""
        tasks = self._gather_tasks(category, n, difficulty)
        decision = self.scheduler.choose_royale(models)
        log.info(f"[royale] {decision.strategy.value}: {decision.reason}")

        royale_id = self.elo.start_royale(category, len(models), len(tasks))
        t0 = time.time()
        
        # model -> total_score
        total_scores = {m: 0.0 for m in models}
        
        # Per-model client mapping
        clients = {m: spec_backend_for_model(m) or self.client for m in models}

        def _gen(model: str, task: dict) -> GenResult:
            if task.get("category") == "tool_use":
                return run_agent_sync(clients[model], model, task["instruction"], self.mcp)
            return clients[model].generate(model, task["instruction"])

        # execution results: task_id -> {model: GenResult}
        all_results: dict[str, dict[str, GenResult]] = {t["id"]: {} for t in tasks}

        if decision.strategy == Strategy.PIPELINE:
            # Phase 1: One model at a time runs all tasks
            for model in models:
                self.scheduler.unload_all_except([model])
                for task in tasks:
                    res = _gen(model, task)
                    all_results[task["id"]][model] = res
                    self._log_perf(model, res)
        else:
            # Concurrent or HOT_SWAP (we'll just use ThreadPool for royale)
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                for task in tasks:
                    futs = {executor.submit(_gen, m, task): m for m in models}
                    for f in futs:
                        m = futs[f]
                        res = f.result()
                        all_results[task["id"]][m] = res
                        self._log_perf(m, res)

        # Scoring & ELO updates
        for task in tasks:
            tid = task["id"]
            model_task_results = []
            for model in models:
                res = all_results[tid][model]
                score = evaluate(task, res.text) if res.ok else 0.0
                total_scores[model] += score
                model_task_results.append({"model": model, "score": score, "res": res})
            
            # Sort by score for ranking
            model_task_results.sort(key=lambda x: x["score"], reverse=True)
            
            for i, r in enumerate(model_task_results):
                # Hallucination check (if judge enabled)
                halluc = None
                if self.judge:
                    try:
                        halluc = self.judge.check_hallucination(task["instruction"], r["res"].text, 
                                                              reference=str(task.get("expected_answer", "")))
                    except Exception as e:
                        log.warning(f"Hallucination check failed: {e}")

                self.elo.save_royale_entry(
                    royale_id=royale_id,
                    task_id=tid,
                    model=r["model"],
                    rank=i + 1,
                    score=r["score"],
                    response=r["res"].text if r["res"].ok else f"[ERROR: {r['res'].error}]",
                    tps=r["res"].tps,
                    latency_s=r["res"].latency_s,
                    instruction=task["instruction"],
                    hallucination=halluc
                )
            
            # Update ELO pairwise for this task
            self.elo.record_royale_elo([{"model": r["model"], "score": r["score"]} for r in model_task_results])
            
            if self._on_task_done:
                # Callback for first two models to satisfy legacy UI
                # In Royale, we might need a new callback type, but for now we'll just use the first two
                if len(models) >= 2:
                    m1, m2 = model_task_results[0], model_task_results[1]
                    self._on_task_done(tid, m1["score"], m2["score"], 
                                      "a_wins" if m1["score"] > m2["score"] else "b_wins" if m2["score"] > m1["score"] else "draw",
                                      task["instruction"], m1["res"].text, m2["res"].text, "")

        # Final Rankings
        rankings = []
        sorted_models = sorted(models, key=lambda m: total_scores[m], reverse=True)
        for i, m in enumerate(sorted_models):
            rankings.append({
                "model": m,
                "total_score": round(total_scores[m], 2),
                "rank": i + 1,
                "elo_after": self.elo.get(m)
            })

        return RoyaleResult(
            models=models,
            category=category,
            tasks_run=len(tasks),
            winner=sorted_models[0],
            rankings=rankings,
            duration_s=round(time.time() - t0, 1),
            royale_id=royale_id,
            strategy=decision.strategy.value
        )
