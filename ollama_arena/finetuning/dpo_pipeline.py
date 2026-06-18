"""Loss-Driven RLHF/DPO Pipeline for extracting preference pairs from arena results."""
from __future__ import annotations

import json
import logging
import sqlite3
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from collections import defaultdict

log = logging.getLogger("arena.finetuning.dpo")


@dataclass
class DatasetVersion:
    """Metadata for a versioned DPO dataset."""
    version_id: str
    created_at: str
    base_model: str
    target_model: str
    category: str
    num_pairs: int
    min_elo_gap: float
    avg_elo_gap: float
    file_path: str
    checksum: str


@dataclass
class DPOPair:
    """A single preference pair for DPO training."""
    prompt: str
    chosen: str
    rejected: str
    chosen_model: str
    rejected_model: str
    category: str
    task_id: str
    elo_gap: float
    match_id: int
    metadata: Dict = field(default_factory=dict)


class DatasetStorage:
    """Manages DPO dataset storage and versioning."""

    def __init__(self, base_dir: str = "data/dpo_datasets"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "dataset_index.json"
        self._index: Dict[str, Dict] = self._load_index()

    def _load_index(self) -> Dict[str, Dict]:
        """Load the dataset index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Failed to load dataset index: {e}")
        return {}

    def _save_index(self):
        """Save the dataset index to disk."""
        try:
            with open(self.index_path, 'w') as f:
                json.dump(self._index, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save dataset index: {e}")

    def store_dataset(
        self,
        pairs: List[DPOPair],
        base_model: str,
        target_model: str,
        category: str,
    ) -> DatasetVersion:
        """Store a DPO dataset with versioning."""
        # Generate version ID based on content
        content_hash = self._compute_hash(pairs)
        version_id = f"{category}_{target_model.replace(':', '_')}_{content_hash[:8]}"

        # Create file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{version_id}_{timestamp}.jsonl"
        file_path = self.base_dir / filename

        # Calculate statistics
        elo_gaps = [p.elo_gap for p in pairs]
        min_gap = min(elo_gaps) if elo_gaps else 0.0
        avg_gap = sum(elo_gaps) / len(elo_gaps) if elo_gaps else 0.0

        # Write dataset
        with open(file_path, 'w', encoding='utf-8') as f:
            for pair in pairs:
                f.write(json.dumps({
                    "prompt": pair.prompt,
                    "chosen": pair.chosen,
                    "rejected": pair.rejected,
                    "chosen_model": pair.chosen_model,
                    "rejected_model": pair.rejected_model,
                    "category": pair.category,
                    "task_id": pair.task_id,
                    "elo_gap": pair.elo_gap,
                    "match_id": pair.match_id,
                    "metadata": pair.metadata,
                }, ensure_ascii=False) + "\n")

        # Create version metadata
        version = DatasetVersion(
            version_id=version_id,
            created_at=datetime.now().isoformat(),
            base_model=base_model,
            target_model=target_model,
            category=category,
            num_pairs=len(pairs),
            min_elo_gap=min_gap,
            avg_elo_gap=avg_gap,
            file_path=str(file_path),
            checksum=content_hash,
        )

        # Update index
        self._index[version_id] = {
            "created_at": version.created_at,
            "base_model": base_model,
            "target_model": target_model,
            "category": category,
            "num_pairs": len(pairs),
            "min_elo_gap": min_gap,
            "avg_elo_gap": avg_gap,
            "file_path": str(file_path),
            "checksum": content_hash,
        }
        self._save_index()

        log.info(f"[dpo] Stored dataset {version_id} with {len(pairs)} pairs at {file_path}")
        return version

    def load_dataset(self, version_id: str) -> Optional[List[DPOPair]]:
        """Load a dataset by version ID."""
        if version_id not in self._index:
            log.error(f"Dataset version {version_id} not found")
            return None

        file_path = Path(self._index[version_id]["file_path"])
        if not file_path.exists():
            log.error(f"Dataset file not found: {file_path}")
            return None

        pairs = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    pairs.append(DPOPair(
                        prompt=data["prompt"],
                        chosen=data["chosen"],
                        rejected=data["rejected"],
                        chosen_model=data["chosen_model"],
                        rejected_model=data["rejected_model"],
                        category=data["category"],
                        task_id=data["task_id"],
                        elo_gap=data["elo_gap"],
                        match_id=data["match_id"],
                        metadata=data.get("metadata", {}),
                    ))
        except Exception as e:
            log.error(f"Failed to load dataset {version_id}: {e}")
            return None

        return pairs

    def list_versions(
        self,
        target_model: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[DatasetVersion]:
        """List all dataset versions, optionally filtered."""
        versions = []
        for vid, meta in self._index.items():
            if target_model and meta["target_model"] != target_model:
                continue
            if category and meta["category"] != category:
                continue
            versions.append(DatasetVersion(
                version_id=vid,
                created_at=meta["created_at"],
                base_model=meta["base_model"],
                target_model=meta["target_model"],
                category=meta["category"],
                num_pairs=meta["num_pairs"],
                min_elo_gap=meta["min_elo_gap"],
                avg_elo_gap=meta["avg_elo_gap"],
                file_path=meta["file_path"],
                checksum=meta["checksum"],
            ))
        return sorted(versions, key=lambda v: v.created_at, reverse=True)

    def _compute_hash(self, pairs: List[DPOPair]) -> str:
        """Compute a hash of the dataset content."""
        content = ""
        for pair in sorted(pairs, key=lambda p: (p.task_id, p.match_id)):
            content += f"{pair.task_id}|{pair.match_id}|{pair.prompt[:100]}|{pair.chosen[:100]}|{pair.rejected[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()


def extract_dpo_pairs(
    db_path: str = "arena.db",
    min_elo_gap: float = 50.0,
    category: Optional[str] = None,
    model_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[DPOPair]:
    """
    Extract DPO preference pairs from arena match results.

    Args:
        db_path: Path to arena SQLite database
        min_elo_gap: Minimum ELO gap between winner and loser to include
        category: Filter by category (optional)
        model_filter: Only extract pairs involving this model (optional)
        limit: Maximum number of pairs to extract (optional)

    Returns:
        List of DPOPair objects with winner as chosen, loser as rejected
    """
    query = """
        SELECT
            m.id as match_id,
            m.model_a,
            m.model_b,
            m.category,
            m.elo_a_before,
            m.elo_b_before,
            m.elo_a_after,
            m.elo_b_after,
            d.task_id,
            d.instruction,
            d.response_a,
            d.response_b,
            d.score_a,
            d.score_b,
            d.outcome
        FROM match_log m
        JOIN task_detail d ON d.match_id = m.id
    """
    params = []
    conditions = []

    if category:
        conditions.append("m.category = ?")
        params.append(category)

    if model_filter:
        conditions.append("(m.model_a = ? OR m.model_b = ?)")
        params.extend([model_filter, model_filter])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY m.ts DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    pairs = []
    try:
        with sqlite3.connect(db_path) as cx:
            rows = cx.execute(query, params).fetchall()

            for row in rows:
                (match_id, model_a, model_b, category_name,
                 elo_a_before, elo_b_before, elo_a_after, elo_b_after,
                 task_id, instruction, response_a, response_b,
                 score_a, score_b, outcome) = row

                # Determine winner and loser based on outcome
                if outcome == "a_wins":
                    winner, loser = model_a, model_b
                    winner_response, loser_response = response_a, response_b
                    winner_elo_before, loser_elo_before = elo_a_before, elo_b_before
                elif outcome == "b_wins":
                    winner, loser = model_b, model_a
                    winner_response, loser_response = response_b, response_a
                    winner_elo_before, loser_elo_before = elo_b_before, elo_a_before
                else:
                    continue  # Skip draws

                # Calculate ELO gap
                elo_gap = abs(winner_elo_before - loser_elo_before)
                if elo_gap < min_elo_gap:
                    continue

                # Skip if responses are empty
                if not winner_response or not loser_response:
                    continue

                pairs.append(DPOPair(
                    prompt=instruction or "",
                    chosen=winner_response,
                    rejected=loser_response,
                    chosen_model=winner,
                    rejected_model=loser,
                    category=category_name,
                    task_id=task_id,
                    elo_gap=elo_gap,
                    match_id=match_id,
                    metadata={
                        "winner_elo_before": winner_elo_before,
                        "loser_elo_before": loser_elo_before,
                        "score_winner": score_a if outcome == "a_wins" else score_b,
                        "score_loser": score_b if outcome == "a_wins" else score_a,
                    },
                ))

    except Exception as e:
        log.error(f"Failed to extract DPO pairs: {e}")
        return []

    log.info(f"[dpo] Extracted {len(pairs)} DPO pairs from {len(rows) if rows else 0} matches")
    return pairs


def collect_preference_dataset(
    target_model: str,
    db_path: str = "arena.db",
    min_samples: int = 100,
    min_elo_gap: float = 50.0,
    storage: Optional[DatasetStorage] = None,
) -> Tuple[List[DPOPair], Optional[DatasetVersion]]:
    """
    Collect a preference dataset for a specific model from arena results.

    Args:
        target_model: The model to fine-tune (loser in pairs)
        db_path: Path to arena database
        min_samples: Minimum number of pairs to collect
        min_elo_gap: Minimum ELO gap for high-quality pairs
        storage: DatasetStorage instance for versioning (optional)

    Returns:
        Tuple of (pairs, version) where version is None if storage not provided
    """
    # Extract pairs where target_model is the loser
    pairs = extract_dpo_pairs(
        db_path=db_path,
        min_elo_gap=min_elo_gap,
        model_filter=target_model,
        limit=None,  # Get all available
    )

    # Filter to only include pairs where target_model is the rejected (loser)
    pairs = [p for p in pairs if p.rejected_model == target_model]

    if len(pairs) < min_samples:
        log.warning(
            f"[dpo] Insufficient pairs for {target_model}: "
            f"found {len(pairs)}, need {min_samples}"
        )
        return pairs, None

    # Sort by ELO gap (highest quality first)
    pairs = sorted(pairs, key=lambda p: p.elo_gap, reverse=True)

    # Determine base model (most common winner)
    winner_counts = defaultdict(int)
    for p in pairs:
        winner_counts[p.chosen_model] += 1
    base_model = max(winner_counts.items(), key=lambda x: x[1])[0] if winner_counts else "unknown"

    # Determine category (most common)
    category_counts = defaultdict(int)
    for p in pairs:
        category_counts[p.category] += 1
    category = max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else "general"

    # Store if storage provided
    version = None
    if storage:
        version = storage.store_dataset(
            pairs=pairs,
            base_model=base_model,
            target_model=target_model,
            category=category,
        )

    log.info(
        f"[dpo] Collected {len(pairs)} preference pairs for {target_model} "
        f"(base: {base_model}, category: {category})"
    )
    return pairs, version


def format_dpo_dataset(pairs: List[DPOPair], format_type: str = "trl") -> List[Dict]:
    """
    Format DPO pairs for different training frameworks.

    Args:
        pairs: List of DPOPair objects
        format_type: "trl" for HuggingFace TRL, "openai" for OpenAI format

    Returns:
        List of formatted dictionaries
    """
    formatted = []
    for pair in pairs:
        if format_type == "trl":
            formatted.append({
                "prompt": pair.prompt,
                "chosen": pair.chosen,
                "rejected": pair.rejected,
                "category": pair.category,
            })
        elif format_type == "openai":
            formatted.append({
                "messages": [
                    {"role": "user", "content": pair.prompt},
                    {"role": "assistant", "content": pair.chosen},
                ],
                "rejected": [
                    {"role": "user", "content": pair.prompt},
                    {"role": "assistant", "content": pair.rejected},
                ],
            })
        else:
            raise ValueError(f"Unknown format_type: {format_type}")

    return formatted


def validate_dpo_dataset(pairs: List[DPOPair]) -> Dict[str, any]:
    """
    Validate a DPO dataset for quality and consistency.

    Returns:
        Dictionary with validation results and statistics
    """
    issues = []

    # Check for empty prompts
    empty_prompts = [i for i, p in enumerate(pairs) if not p.prompt.strip()]
    if empty_prompts:
        issues.append(f"Empty prompts at indices: {empty_prompts[:10]}")

    # Check for empty chosen
    empty_chosen = [i for i, p in enumerate(pairs) if not p.chosen.strip()]
    if empty_chosen:
        issues.append(f"Empty chosen at indices: {empty_chosen[:10]}")

    # Check for empty rejected
    empty_rejected = [i for i, p in enumerate(pairs) if not p.rejected.strip()]
    if empty_rejected:
        issues.append(f"Empty rejected at indices: {empty_rejected[:10]}")

    # Check for identical chosen/rejected
    identical = [i for i, p in enumerate(pairs) if p.chosen == p.rejected]
    if identical:
        issues.append(f"Identical chosen/rejected at indices: {identical[:10]}")

    # Check for very short responses
    short_chosen = [i for i, p in enumerate(pairs) if len(p.chosen) < 10]
    short_rejected = [i for i, p in enumerate(pairs) if len(p.rejected) < 10]
    if short_chosen:
        issues.append(f"Very short chosen responses at indices: {short_chosen[:10]}")
    if short_rejected:
        issues.append(f"Very short rejected responses at indices: {short_rejected[:10]}")

    # Calculate statistics
    elo_gaps = [p.elo_gap for p in pairs]
    prompt_lengths = [len(p.prompt) for p in pairs]
    chosen_lengths = [len(p.chosen) for p in pairs]
    rejected_lengths = [len(p.rejected) for p in pairs]

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "num_pairs": len(pairs),
        "stats": {
            "elo_gap": {
                "min": min(elo_gaps) if elo_gaps else 0,
                "max": max(elo_gaps) if elo_gaps else 0,
                "avg": sum(elo_gaps) / len(elo_gaps) if elo_gaps else 0,
            },
            "prompt_length": {
                "min": min(prompt_lengths) if prompt_lengths else 0,
                "max": max(prompt_lengths) if prompt_lengths else 0,
                "avg": sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else 0,
            },
            "chosen_length": {
                "min": min(chosen_lengths) if chosen_lengths else 0,
                "max": max(chosen_lengths) if chosen_lengths else 0,
                "avg": sum(chosen_lengths) / len(chosen_lengths) if chosen_lengths else 0,
            },
            "rejected_length": {
                "min": min(rejected_lengths) if rejected_lengths else 0,
                "max": max(rejected_lengths) if rejected_lengths else 0,
                "avg": sum(rejected_lengths) / len(rejected_lengths) if rejected_lengths else 0,
            },
        },
        "categories": list(set(p.category for p in pairs)),
        "chosen_models": list(set(p.chosen_model for p in pairs)),
        "rejected_models": list(set(p.rejected_model for p in pairs)),
    }


class DPOPipeline:
    """High-level pipeline for continuous DPO dataset collection."""

    def __init__(
        self,
        db_path: str = "arena.db",
        storage_dir: str = "data/dpo_datasets",
        min_samples: int = 100,
        min_elo_gap: float = 50.0,
    ):
        self.db_path = db_path
        self.storage = DatasetStorage(storage_dir)
        self.min_samples = min_samples
        self.min_elo_gap = min_elo_gap

    def collect_for_model(
        self,
        target_model: str,
        category: Optional[str] = None,
    ) -> Tuple[List[DPOPair], DatasetVersion]:
        """Collect and store a DPO dataset for a specific model."""
        pairs, version = collect_preference_dataset(
            target_model=target_model,
            db_path=self.db_path,
            min_samples=self.min_samples,
            min_elo_gap=self.min_elo_gap,
            storage=self.storage,
        )
        return pairs, version

    def get_latest_dataset(self, target_model: str) -> Optional[List[DPOPair]]:
        """Get the latest DPO dataset for a model."""
        versions = self.storage.list_versions(target_model=target_model)
        if not versions:
            return None
        return self.storage.load_dataset(versions[0].version_id)

    def get_model_readiness(self, target_model: str) -> Dict[str, any]:
        """Check if a model has enough data for fine-tuning."""
        versions = self.storage.list_versions(target_model=target_model)
        if not versions:
            return {
                "ready": False,
                "reason": "No datasets available",
                "total_pairs": 0,
            }

        latest = versions[0]
        ready = latest.num_pairs >= self.min_samples

        return {
            "ready": ready,
            "reason": "Ready" if ready else f"Need {self.min_samples} pairs, have {latest.num_pairs}",
            "total_pairs": latest.num_pairs,
            "latest_version": latest.version_id,
            "avg_elo_gap": latest.avg_elo_gap,
        }
