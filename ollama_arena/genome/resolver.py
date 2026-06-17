"""Orchestrates scanner → registry → evidence → store."""
from __future__ import annotations
from .db import GenomeStore
from .registry import CanonicalRegistry
from .scanner import LocalModelInfo
from .evidence import score_name_match, score_from_chain, confidence_label


class GenomeResolver:
    def __init__(self, store: GenomeStore, registry: CanonicalRegistry):
        self.store = store
        self.registry = registry
        for m in registry.all_models():
            self.store.upsert_canonical(m)

    def resolve(self, info: LocalModelInfo) -> dict:
        """Return {'genome_id': str|None, 'confidence': str, 'score': float}."""
        best_id: str | None = None
        best_score = 0.0

        direct = self.registry.match_by_name(info.name)
        if direct:
            canonical = self.registry.get(direct)
            s = score_name_match(info.name, direct,
                                 canonical.get("aliases", []))
            if s > best_score:
                best_score = s
                best_id = direct

        if info.from_model:
            from_id = self.registry.match_by_name(info.from_model)
            if from_id:
                canonical = self.registry.get(from_id)
                s = score_from_chain(info.from_model, from_id,
                                     canonical.get("aliases", []))
                if s > best_score:
                    best_score = s
                    best_id = from_id

        conf = confidence_label(best_score)
        self.store.upsert_local(
            name=info.name,
            genome_id=best_id,
            confidence=conf,
            quant=info.parameters.get("num_gpu", ""),
            size_gb=info.size_gb,
            modelfile=info.modelfile,
        )
        return {"genome_id": best_id, "confidence": conf, "score": best_score}

    def scan_and_resolve_all(self, scanner_results: list[LocalModelInfo]) -> list[dict]:
        return [{"name": r.name, **self.resolve(r)} for r in scanner_results]
