"""LLM-as-judge for open-ended responses.

Each pair is graded twice — once as (A, B) and once as (B, A) — and the
two scores are averaged. This mitigates the well-known position bias
where judges tend to prefer the response shown first (Zheng et al., 2023,
"Judging LLM-as-a-Judge").
"""
from __future__ import annotations
import logging, random, re
from dataclasses import dataclass
from typing import Optional

from .backends.base import Backend

log = logging.getLogger("arena.judge")


_RUBRIC = """\
You are an impartial judge evaluating two AI responses to the same task.

Task:
{task}

Reference answer (may be empty if not provided):
{reference}

Response A:
{response_a}

Response B:
{response_b}

Score each response 0-10 on correctness and completeness only. Do not reward
length or style. Output ONLY this exact format on two lines:

A: <0-10>
B: <0-10>
"""


@dataclass
class JudgeResult:
    score_a: float           # 0.0–1.0
    score_b: float
    raw:     str
    judge_model: str


class LLMJudge:
    """
    Pair-wise judge using a single LLM. Symmetrizes by swapping order.
    """

    def __init__(self, backend: Backend, model: str):
        self.backend = backend
        self.model = model

    def grade_pair(self, task: str, response_a: str, response_b: str,
                   reference: str = "") -> JudgeResult:
        # First ordering: A, B
        prompt1 = _RUBRIC.format(
            task=task, reference=reference,
            response_a=response_a, response_b=response_b,
        )
        raw1 = self.backend.generate(self.model, prompt1).text
        sa1, sb1 = _parse_scores(raw1)

        # Reversed ordering: B, A → swap back when reading
        prompt2 = _RUBRIC.format(
            task=task, reference=reference,
            response_a=response_b, response_b=response_a,
        )
        raw2 = self.backend.generate(self.model, prompt2).text
        sb2, sa2 = _parse_scores(raw2)

        score_a = ((sa1 + sa2) / 2) / 10.0
        score_b = ((sb1 + sb2) / 2) / 10.0
        return JudgeResult(
            score_a=round(score_a, 3), score_b=round(score_b, 3),
            raw=raw1 + "\n---\n" + raw2, judge_model=self.model,
        )

    def grade_single(self, task: str, response: str, reference: str = "") -> float:
        """Score one response on its own merits, 0.0–1.0."""
        prompt = (
            f"Task:\n{task}\n\n"
            f"Reference (may be empty):\n{reference}\n\n"
            f"Response:\n{response}\n\n"
            "Rate the response 0-10 on correctness and completeness only. "
            "Output ONLY the number."
        )
        raw = self.backend.generate(self.model, prompt).text
        try:
            return min(1.0, max(0.0, float(re.findall(r"\d+\.?\d*", raw)[0]) / 10.0))
        except (IndexError, ValueError):
            return 0.0


def _parse_scores(text: str) -> tuple[float, float]:
    """Extract 'A: N' and 'B: N' from judge output. Default to 0 on parse fail."""
    a = re.search(r"A:\s*(\d+\.?\d*)", text, re.IGNORECASE)
    b = re.search(r"B:\s*(\d+\.?\d*)", text, re.IGNORECASE)
    return (float(a.group(1)) if a else 0.0,
            float(b.group(1)) if b else 0.0)
