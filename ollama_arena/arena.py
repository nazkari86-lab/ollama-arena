"""
Core arena engine — runs head-to-head LLM battles with ELO tracking.
"""
from __future__ import annotations
import json, logging, re, time
from dataclasses import dataclass, field
from typing import Callable, Optional

import requests

from .elo import EloStore
from .evaluator import evaluate
from .tasks import get_tasks

log = logging.getLogger("arena")

_DEFAULT_OLLAMA = "http://localhost:11434"
_THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


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


class OllamaClient:
    def __init__(self, base_url: str = _DEFAULT_OLLAMA, timeout: int = 120):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, model: str, prompt: str) -> str:
        """Stream response from Ollama, strip <think> tags (for DeepSeek-R1)."""
        try:
            r = requests.post(
                f"{self.base}/api/generate",
                json={
                    "model": model, "prompt": prompt, "stream": True,
                    "options": {"num_ctx": 4096, "temperature": 0.0, "num_predict": 1024},
                },
                timeout=self.timeout, stream=True,
            )
            text = ""
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    text += chunk.get("response", "")
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    pass
            return _THINK_TAG.sub("", text).strip()
        except Exception as e:
            log.warning(f"[ollama] {model}: {e}")
            return ""

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base}/api/tags", timeout=5)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def is_alive(self) -> bool:
        try:
            requests.get(f"{self.base}/api/tags", timeout=3)
            return True
        except Exception:
            return False


class Arena:
    """
    Run ELO-rated head-to-head matches between Ollama models.

    Usage:
        arena = Arena()
        result = arena.run_match("llama3.2:3b", "qwen2.5:7b", category="coding", n=10)
        print(arena.leaderboard())
    """

    def __init__(
        self,
        ollama_url: str = _DEFAULT_OLLAMA,
        db_path: str = "arena.db",
        on_task_done: Optional[Callable] = None,
    ):
        self.client  = OllamaClient(base_url=ollama_url)
        self.elo     = EloStore(db_path=db_path)
        self._on_task_done = on_task_done  # callback(task_id, score_a, score_b, outcome)

    # ── Public API ──────────────────────────────────────────────────────────

    def run_match(
        self,
        model_a: str,
        model_b: str,
        category: str = "coding",
        n: int = 10,
        difficulty: Optional[str] = None,
    ) -> MatchResult:
        """
        Run n tasks from `category` between model_a and model_b.
        Updates ELO after every task. Returns MatchResult.
        """
        tasks = get_tasks(category=category, limit=n, difficulty=difficulty)
        if not tasks:
            raise ValueError(f"No tasks found for category='{category}' difficulty='{difficulty}'")

        elo_a_before = self.elo.get(model_a)
        elo_b_before = self.elo.get(model_b)

        a_wins = b_wins = draws = 0
        task_results = []
        t0 = time.time()

        for task in tasks:
            resp_a = self.client.generate(model_a, task["instruction"])
            resp_b = self.client.generate(model_b, task["instruction"])

            score_a = evaluate(task, resp_a)
            score_b = evaluate(task, resp_b)

            if score_a > score_b:
                outcome, a_wins = "a_wins", a_wins + 1
            elif score_b > score_a:
                outcome, b_wins = "b_wins", b_wins + 1
            else:
                outcome, draws = "draw", draws + 1

            # Per-task ELO update
            self.elo.record_match(model_a, model_b, category, score_a, score_b)

            task_results.append({
                "task_id": task["id"],
                "difficulty": task.get("difficulty", "?"),
                "score_a": round(score_a, 3),
                "score_b": round(score_b, 3),
                "outcome": outcome,
            })

            log.info(
                f"[{task['id']}] {model_a}={score_a:.2f}  {model_b}={score_b:.2f}  → {outcome}"
            )

            if self._on_task_done:
                self._on_task_done(task["id"], score_a, score_b, outcome)

        total = len(tasks)
        elo_a_after = self.elo.get(model_a)
        elo_b_after = self.elo.get(model_b)

        return MatchResult(
            model_a=model_a, model_b=model_b, category=category,
            tasks_run=total,
            a_wins=a_wins, b_wins=b_wins, draws=draws,
            a_win_rate=round(a_wins / total, 3),
            b_win_rate=round(b_wins / total, 3),
            elo_a_before=elo_a_before, elo_b_before=elo_b_before,
            elo_a_after=elo_a_after, elo_b_after=elo_b_after,
            task_results=task_results,
            duration_s=round(time.time() - t0, 1),
        )

    def run_tournament(
        self,
        models: list[str],
        category: str = "coding",
        n_per_match: int = 5,
    ) -> list[dict]:
        """
        Round-robin tournament: every model plays every other model.
        Returns final leaderboard.
        """
        from itertools import combinations
        pairs = list(combinations(models, 2))
        log.info(f"[tournament] {len(models)} models × {len(pairs)} matches × {n_per_match} tasks")

        for i, (a, b) in enumerate(pairs, 1):
            log.info(f"[tournament] Match {i}/{len(pairs)}: {a} vs {b}")
            self.run_match(a, b, category=category, n=n_per_match)

        return self.leaderboard()

    def leaderboard(self) -> list[dict]:
        return self.elo.leaderboard()

    def match_history(self, limit: int = 20) -> list[dict]:
        return self.elo.match_history(limit=limit)
