"""Pair-wise match driver and ELO bookkeeping."""
from __future__ import annotations
import logging, time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Optional

from .backends import auto_backend, Backend, GenResult
from .backends.ollama import OllamaBackend
from .backends.openai_compat import OpenAICompatBackend
from .backends.auto import spec_backend_for_model
from .memory_scheduler import MemoryScheduler, Strategy, StrategyDecision
from .elo import EloStore
from .evaluator import evaluate
from .performance import PerfTracker
from .tasks import get_tasks

log = logging.getLogger("arena")


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

        self.judge = None
        if judge_model:
            from .judge import LLMJudge
            self.judge = LLMJudge(self.client, judge_model)

        if from_datasets:
            for name in from_datasets:
                self.load_hf_dataset(name)

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
                            cached_a: bool, cached_b: bool) -> dict:
            if self.judge and task.get("use_judge"):
                jr = self.judge.grade_pair(
                    task["instruction"], res_a.text, res_b.text,
                    reference=task.get("expected_answer", ""),
                )
                score_a, score_b = jr.score_a, jr.score_b
            else:
                score_a = evaluate(task, res_a.text) if res_a.ok else 0.0
                score_b = evaluate(task, res_b.text) if res_b.ok else 0.0
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
            Strategy.CONCURRENT: 180,
            Strategy.HOT_SWAP:   480,
            Strategy.PIPELINE:   900,
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
            return client.generate(model, task["instruction"],
                                   _timeout=_gen_timeout), False

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

        for r in results:
            task = r["task"]
            res_a, res_b = r["res_a"], r["res_b"]
            cached_a, cached_b = r["cached_a"], r["cached_b"]
            score_a, score_b = r["score_a"], r["score_b"]
            outcome = r["outcome"]

            if not cached_a:
                self._log_perf(model_a, res_a)
            if not cached_b:
                self._log_perf(model_b, res_b)

            if outcome == "a_wins": a_wins += 1
            elif outcome == "b_wins": b_wins += 1
            else: draws += 1

            self.elo.record_match(model_a, model_b, category, score_a, score_b)
            last_match_id = self.elo.last_match_id()

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
        return MatchResult(
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
        client_a = spec_backend_for_model(model_a) or self.client
        client_b = spec_backend_for_model(model_b) or self.client
        res_a = client_a.generate(model_a, instruction)
        res_b = client_b.generate(model_b, instruction)

        if self.judge and task.get("use_judge"):
            jr = self.judge.grade_pair(instruction, res_a.text, res_b.text,
                                       reference=expected)
            score_a, score_b = jr.score_a, jr.score_b
        else:
            score_a = evaluate(task, res_a.text) if res_a.ok else 0.0
            score_b = evaluate(task, res_b.text) if res_b.ok else 0.0
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
        )
        self._log_perf(model_a, res_a)
        self._log_perf(model_b, res_b)

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

    def match_history(self, limit: int = 20) -> list[dict]:
        return self.elo.match_history(limit=limit)

    def performance_stats(self) -> list[dict]:
        return self.perf.stats()

    def _log_perf(self, model: str, res: GenResult):
        if res.ok:
            backend_name = res.backend_type or self.client.name
            self.perf.record(
                model=model, backend=backend_name,
                tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                latency_s=res.latency_s, tps=res.tps,
                time_to_first=res.time_to_first,
            )
