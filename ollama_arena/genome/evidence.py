"""Score evidence for a local model matching a canonical genome entry."""
from __future__ import annotations
from .scanner import LocalModelInfo


def score_name_match(local_name: str, candidate_id: str,
                     aliases: list[str]) -> float:
    """0.0-1.0: how well does the local name match this candidate."""
    from .registry import _normalize
    key = _normalize(local_name)
    for alias in aliases:
        if _normalize(alias) == key:
            return 1.0
    family_hint = candidate_id.split("/")[-1].split("-")[0].lower()
    if family_hint and family_hint in key:
        return 0.4
    return 0.0


def score_from_chain(from_model: str | None, candidate_id: str,
                     aliases: list[str]) -> float:
    """0.0-1.0: FROM line points at this candidate."""
    if not from_model:
        return 0.0
    from .registry import _normalize
    key = _normalize(from_model)
    for alias in aliases:
        if _normalize(alias) == key:
            return 0.5  # FROM-chain is weaker evidence than direct name match
    return 0.0


def confidence_label(score: float) -> str:
    if score >= 0.95:
        return "Confirmed"
    if score >= 0.7:
        return "High"
    if score >= 0.4:
        return "Medium"
    if score > 0.0:
        return "Low"
    return "Unknown"
