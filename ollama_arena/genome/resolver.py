"""Orchestrates scanner → registry → evidence → store."""
from __future__ import annotations
from .db import GenomeStore
from .registry import CanonicalRegistry
from .scanner import LocalModelInfo, extract_quant
from .evidence import score_name_match, score_from_chain, confidence_label


class GenomeResolver:
    def __init__(self, store: GenomeStore, registry: CanonicalRegistry):
        self.store = store
        self.registry = registry
        for m in registry.all_models():
            self.store.upsert_canonical(m)
        self._seed_lineage_from_registry()

    def _seed_lineage_from_registry(self) -> None:
        """Populate genome_lineage edges from bundled seed_registry.json."""
        for model in self.registry.all_models():
            child_id = model["id"]
            lineage = model.get("lineage") or {}
            for relation, parent_id in lineage.items():
                if not parent_id or not isinstance(parent_id, str):
                    continue
                if not self.registry.get(parent_id):
                    continue
                self.store.add_lineage_if_absent(
                    child_id=child_id,
                    parent_id=parent_id,
                    relation=relation,
                    confidence=1.0,
                    evidence_source="seed_registry",
                )

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
        quant = info.quant or extract_quant(info.name)
        self.store.upsert_local(
            name=info.name,
            genome_id=best_id,
            confidence=conf,
            quant=quant,
            size_gb=info.size_gb,
            modelfile=info.modelfile,
        )
        return {"genome_id": best_id, "confidence": conf, "score": best_score}

    def scan_and_resolve_all(
        self,
        scanner_results: list[LocalModelInfo],
        on_progress=None,
    ) -> list[dict]:
        total = len(scanner_results)
        out = []
        for i, r in enumerate(scanner_results, 1):
            out.append({"name": r.name, **self.resolve(r)})
            if on_progress:
                on_progress(i, total, r.name)
        return out
