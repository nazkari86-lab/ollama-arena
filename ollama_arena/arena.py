"""Pair-wise match driver and ELO bookkeeping."""
from __future__ import annotations
import logging, time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Optional

from .backends import auto_backend, Backend, GenResult
from .backends.ollama import OllamaBackend
from .backends.openai_compat import OpenAICompatBackend
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
    ) -> MatchResult:
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

        for task in tasks:
            res_a = self.client.generate(model_a, task["instruction"])
            res_b = self.client.generate(model_b, task["instruction"])

            self._log_perf(model_a, res_a)
            self._log_perf(model_b, res_b)

            if self.judge and task.get("use_judge"):
                jr = self.judge.grade_pair(
                    task["instruction"], res_a.text, res_b.text,
                    reference=task.get("expected_answer", ""),
                )
                score_a, score_b = jr.score_a, jr.score_b
            else:
                score_a = evaluate(task, res_a.text) if res_a.ok else 0.0
                score_b = evaluate(task, res_b.text) if res_b.ok else 0.0

            if score_a > score_b:
                outcome, a_wins = "a_wins", a_wins + 1
            elif score_b > score_a:
                outcome, b_wins = "b_wins", b_wins + 1
            else:
                outcome, draws = "draw", draws + 1

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

    def leaderboard(self) -> list[dict]:
        return self.elo.leaderboard()

    def match_history(self, limit: int = 20) -> list[dict]:
        return self.elo.match_history(limit=limit)

    def performance_stats(self) -> list[dict]:
        return self.perf.stats()

    def _log_perf(self, model: str, res: GenResult):
        if res.ok:
            self.perf.record(
                model=model, backend=self.client.name,
                tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                latency_s=res.latency_s, tps=res.tps,
                time_to_first=res.time_to_first,
            )
