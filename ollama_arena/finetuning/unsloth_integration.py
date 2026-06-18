"""Auto-Unsloth Integration for automatic LoRA fine-tuning."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Callable

from ..finetune.unsloth_runner import unsloth_train, UnslothConfig
from ..finetune.ollama_export import build_modelfile, install_to_ollama
from .dpo_pipeline import DPOPipeline, DatasetStorage, DPOPair

log = logging.getLogger("arena.finetuning.unsloth")


class TriggerType(Enum):
    """Types of fine-tuning triggers."""
    LOSS_COUNT = "loss_count"  # Trigger after N losses
    WIN_RATE = "win_rate"  # Trigger when win rate below threshold
    ELO_GAP = "elo_gap"  # Trigger when ELO gap to leader exceeds threshold
    MANUAL = "manual"  # Manual trigger
    SCHEDULED = "scheduled"  # Time-based trigger


@dataclass
class FinetuneTrigger:
    """Configuration for when to auto-finetune."""
    trigger_type: TriggerType
    threshold: float  # Value threshold (e.g., loss count, win rate)
    min_samples: int = 100  # Minimum samples before trigger
    cooldown_hours: float = 24.0  # Minimum hours between finetunes
    enabled: bool = True


@dataclass
class LoRAConfig:
    """Configuration for LoRA fine-tuning."""
    base_model: str = "unsloth/llama-3.2-3b-instruct-bnb-4bit"
    max_seq_length: int = 2048
    load_in_4bit: bool = True
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.0
    learning_rate: float = 2e-4
    epochs: int = 2
    batch_size: int = 2
    grad_accumulation: int = 4
    warmup_steps: int = 5
    output_dir: str = "outputs/lora"
    save_merged: bool = True
    save_gguf: bool = True
    quant_method: str = "q4_k_m"

    def to_unsloth_config(self) -> UnslothConfig:
        """Convert to UnslothConfig for compatibility."""
        return UnslothConfig(
            base_model=self.base_model,
            max_seq_length=self.max_seq_length,
            load_in_4bit=self.load_in_4bit,
            lora_r=self.lora_r,
            lora_alpha=self.lora_alpha,
            lora_dropout=self.lora_dropout,
            learning_rate=self.learning_rate,
            epochs=self.epochs,
            batch_size=self.batch_size,
            grad_accumulation=self.grad_accumulation,
            warmup_steps=self.warmup_steps,
            output_dir=self.output_dir,
            save_merged=self.save_merged,
            save_gguf=self.save_gguf,
            quant_method=self.quant_method,
        )


@dataclass
class AutoFinetuneResult:
    """Result of an auto-finetune operation."""
    success: bool
    model_name: str
    ollama_name: Optional[str]
    adapter_dir: Optional[str]
    gguf_path: Optional[str]
    modelfile_path: Optional[str]
    dataset_version: Optional[str]
    training_time_seconds: float
    error_message: Optional[str]
    timestamp: str
    trigger_type: TriggerType


class ModelRegistry:
    """Registry for tracking fine-tuned models in the arena."""

    def __init__(self, db_path: str = "arena.db"):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        """Ensure the fine-tuned models table exists."""
        with sqlite3.connect(self.db_path) as cx:
            cx.execute("""
                CREATE TABLE IF NOT EXISTS finetuned_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_model TEXT NOT NULL,
                    finetuned_name TEXT NOT NULL UNIQUE,
                    ollama_name TEXT,
                    dataset_version TEXT,
                    trigger_type TEXT,
                    created_at REAL,
                    elo_rating REAL,
                    num_matches INTEGER DEFAULT 0,
                    metadata TEXT,
                    active BOOLEAN DEFAULT 1
                )
            """)

    def register_model(
        self,
        base_model: str,
        finetuned_name: str,
        ollama_name: str,
        dataset_version: str,
        trigger_type: TriggerType,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Register a fine-tuned model in the arena."""
        try:
            with sqlite3.connect(self.db_path) as cx:
                cx.execute("""
                    INSERT INTO finetuned_models
                    (base_model, finetuned_name, ollama_name, dataset_version,
                     trigger_type, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    base_model,
                    finetuned_name,
                    ollama_name,
                    dataset_version,
                    trigger_type.value,
                    datetime.now().timestamp(),
                    json.dumps(metadata or {}),
                ))
                log.info(f"[unsloth] Registered finetuned model: {finetuned_name}")
                return True
        except Exception as e:
            log.error(f"[unsloth] Failed to register model: {e}")
            return False

    def get_model_info(self, finetuned_name: str) -> Optional[Dict]:
        """Get information about a fine-tuned model."""
        with sqlite3.connect(self.db_path) as cx:
            row = cx.execute("""
                SELECT * FROM finetuned_models WHERE finetuned_name = ?
            """, (finetuned_name,)).fetchone()

            if not row:
                return None

            cols = [desc[0] for desc in cx.description]
            info = dict(zip(cols, row))
            if info.get("metadata"):
                info["metadata"] = json.loads(info["metadata"])
            return info

    def list_models(
        self,
        base_model: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict]:
        """List all fine-tuned models."""
        query = "SELECT * FROM finetuned_models"
        params = []
        conditions = []

        if base_model:
            conditions.append("base_model = ?")
            params.append(base_model)

        if active_only:
            conditions.append("active = 1")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        with sqlite3.connect(self.db_path) as cx:
            rows = cx.execute(query, params).fetchall()
            cols = [desc[0] for desc in cx.description]

            models = []
            for row in rows:
                info = dict(zip(cols, row))
                if info.get("metadata"):
                    info["metadata"] = json.loads(info["metadata"])
                models.append(info)
            return models

    def update_elo(self, finetuned_name: str, elo: float):
        """Update ELO rating for a fine-tuned model."""
        with sqlite3.connect(self.db_path) as cx:
            cx.execute("""
                UPDATE finetuned_models
                SET elo_rating = ?
                WHERE finetuned_name = ?
            """, (elo, finetuned_name))

    def increment_matches(self, finetuned_name: str):
        """Increment match count for a fine-tuned model."""
        with sqlite3.connect(self.db_path) as cx:
            cx.execute("""
                UPDATE finetuned_models
                SET num_matches = num_matches + 1
                WHERE finetuned_name = ?
            """, (finetuned_name,))

    def deactivate_model(self, finetuned_name: str):
        """Deactivate a fine-tuned model."""
        with sqlite3.connect(self.db_path) as cx:
            cx.execute("""
                UPDATE finetuned_models
                SET active = 0
                WHERE finetuned_name = ?
            """, (finetuned_name,))


class AutoUnslothIntegrator:
    """Automated Unsloth integration with trigger-based fine-tuning."""

    def __init__(
        self,
        db_path: str = "arena.db",
        dpo_pipeline: Optional[DPOPipeline] = None,
        lora_config: Optional[LoRAConfig] = None,
        triggers: Optional[List[FinetuneTrigger]] = None,
    ):
        self.db_path = db_path
        self.dpo_pipeline = dpo_pipeline or DPOPipeline(db_path=db_path)
        self.lora_config = lora_config or LoRAConfig()
        self.triggers = triggers or [
            FinetuneTrigger(
                trigger_type=TriggerType.LOSS_COUNT,
                threshold=1000,  # After 1000 losses
                min_samples=100,
            ),
        ]
        self.registry = ModelRegistry(db_path=db_path)
        self._last_finetune_times: Dict[str, float] = {}

    def should_finetune(
        self,
        model: str,
        category: Optional[str] = None,
    ) -> Tuple[bool, Optional[FinetuneTrigger], str]:
        """
        Check if a model should be fine-tuned based on triggers.

        Returns:
            Tuple of (should_finetune, trigger, reason)
        """
        # Check cooldown
        last_time = self._last_finetune_times.get(model, 0)
        for trigger in self.triggers:
            if not trigger.enabled:
                continue

            cooldown_ok = (datetime.now().timestamp() - last_time) >= (trigger.cooldown_hours * 3600)
            if not cooldown_ok:
                continue

            if trigger.trigger_type == TriggerType.LOSS_COUNT:
                loss_count = self._get_loss_count(model, category)
                if loss_count >= trigger.threshold:
                    return True, trigger, f"Loss count {loss_count} >= {trigger.threshold}"

            elif trigger.trigger_type == TriggerType.WIN_RATE:
                win_rate = self._get_win_rate(model, category)
                if win_rate < trigger.threshold:
                    samples = self._get_sample_count(model, category)
                    if samples >= trigger.min_samples:
                        return True, trigger, f"Win rate {win_rate:.2%} < {trigger.threshold:.2%}"

            elif trigger.trigger_type == TriggerType.ELO_GAP:
                elo_gap = self._get_elo_gap_to_leader(model, category)
                if elo_gap >= trigger.threshold:
                    samples = self._get_sample_count(model, category)
                    if samples >= trigger.min_samples:
                        return True, trigger, f"ELO gap {elo_gap:.1f} >= {trigger.threshold}"

        return False, None, "No trigger conditions met"

    def _get_loss_count(self, model: str, category: Optional[str]) -> int:
        """Get the number of losses for a model."""
        try:
            with sqlite3.connect(self.db_path) as cx:
                query = """
                    SELECT COUNT(*) FROM task_detail d
                    JOIN match_log m ON m.id = d.match_id
                    WHERE (m.model_a = ? OR m.model_b = ?)
                """
                params = [model, model]

                if category:
                    query += " AND d.category = ?"
                    params.append(category)

                # Count losses
                losses = 0
                rows = cx.execute(query, params).fetchall()
                # Simplified: count all tasks as potential losses
                # In production, you'd filter by outcome
                return rows[0][0] if rows else 0
        except Exception as e:
            log.error(f"Failed to get loss count: {e}")
            return 0

    def _get_win_rate(self, model: str, category: Optional[str]) -> float:
        """Get the win rate for a model."""
        try:
            with sqlite3.connect(self.db_path) as cx:
                query = """
                    SELECT
                        SUM(CASE WHEN (m.model_a = ? AND d.outcome = 'a_wins')
                                  OR (m.model_b = ? AND d.outcome = 'b_wins')
                                  THEN 1 ELSE 0 END) as wins,
                        COUNT(*) as total
                    FROM task_detail d
                    JOIN match_log m ON m.id = d.match_id
                    WHERE m.model_a = ? OR m.model_b = ?
                """
                params = [model, model, model, model]

                if category:
                    query += " AND d.category = ?"
                    params.append(category)

                row = cx.execute(query, params).fetchone()
                if row and row[1] > 0:
                    return row[0] / row[1]
                return 0.0
        except Exception as e:
            log.error(f"Failed to get win rate: {e}")
            return 0.0

    def _get_elo_gap_to_leader(self, model: str, category: Optional[str]) -> float:
        """Get the ELO gap between model and the leader."""
        try:
            with sqlite3.connect(self.db_path) as cx:
                # Get model's ELO
                model_elo = cx.execute("""
                    SELECT elo_after FROM match_log
                    WHERE model_a = ? OR model_b = ?
                    ORDER BY ts DESC LIMIT 1
                """, (model, model)).fetchone()

                if not model_elo:
                    return 0.0

                model_elo = max(model_elo[0], model_elo[1]) if model_elo[1] else model_elo[0]

                # Get leader's ELO
                query = """
                    SELECT MAX(MAX(elo_a_after, elo_b_after))
                    FROM match_log
                """
                if category:
                    query += " WHERE category = ?"

                leader_elo = cx.execute(query, (category,) if category else ()).fetchone()
                if not leader_elo:
                    return 0.0

                return leader_elo[0] - model_elo if leader_elo[0] else 0.0
        except Exception as e:
            log.error(f"Failed to get ELO gap: {e}")
            return 0.0

    def _get_sample_count(self, model: str, category: Optional[str]) -> int:
        """Get the number of samples for a model."""
        try:
            with sqlite3.connect(self.db_path) as cx:
                query = """
                    SELECT COUNT(*) FROM task_detail d
                    JOIN match_log m ON m.id = d.match_id
                    WHERE m.model_a = ? OR m.model_b = ?
                """
                params = [model, model]

                if category:
                    query += " AND d.category = ?"
                    params.append(category)

                row = cx.execute(query, params).fetchone()
                return row[0] if row else 0
        except Exception as e:
            log.error(f"Failed to get sample count: {e}")
            return 0

    def autofinetune(
        self,
        model: str,
        trigger: FinetuneTrigger,
        category: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> AutoFinetuneResult:
        """
        Execute automatic fine-tuning for a model.

        Args:
            model: The model to fine-tune
            trigger: The trigger that initiated fine-tuning
            category: Optional category filter
            progress_callback: Optional callback for progress updates (message, progress)

        Returns:
            AutoFinetuneResult with details of the operation
        """
        start_time = datetime.now()

        if progress_callback:
            progress_callback("Collecting DPO dataset...", 0.1)

        # Step 1: Collect DPO dataset
        pairs, version = self.dpo_pipeline.collect_for_model(model, category=category)

        if not pairs:
            return AutoFinetuneResult(
                success=False,
                model_name=model,
                ollama_name=None,
                adapter_dir=None,
                gguf_path=None,
                modelfile_path=None,
                dataset_version=None,
                training_time_seconds=0.0,
                error_message="No DPO pairs collected",
                timestamp=datetime.now().isoformat(),
                trigger_type=trigger.trigger_type,
            )

        if progress_callback:
            progress_callback(f"Collected {len(pairs)} DPO pairs", 0.3)

        # Step 2: Format dataset for training
        from .dpo_pipeline import format_dpo_dataset
        formatted = format_dpo_dataset(pairs, format_type="trl")

        # Create temporary JSONL file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for item in formatted:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            jsonl_path = f.name

        try:
            if progress_callback:
                progress_callback("Starting LoRA training...", 0.5)

            # Step 3: Train with Unsloth
            unsloth_cfg = self.lora_config.to_unsloth_config()
            artifacts = unsloth_train(jsonl_path, unsloth_cfg)

            if progress_callback:
                progress_callback("Training complete, exporting...", 0.8)

            # Step 4: Export to Ollama
            gguf_path = artifacts.get("gguf_path")
            modelfile_path = None
            ollama_name = None

            if gguf_path and Path(gguf_path).exists():
                modelfile_path = str(Path(self.lora_config.output_dir) / "Modelfile")
                build_modelfile(gguf_path, out_path=modelfile_path)

                # Generate Ollama model name
                base_name = model.replace(":", "-")
                timestamp = datetime.now().strftime("%Y%m%d")
                ollama_name = f"{base_name}-arena-tuned-{timestamp}"

                if install_to_ollama(modelfile_path, ollama_name):
                    log.info(f"[unsloth] Installed to Ollama as {ollama_name}")
                else:
                    ollama_name = None

            # Step 5: Register in arena
            finetuned_name = f"{model}-finetuned-{version.version_id if version else 'latest'}"
            if ollama_name:
                self.registry.register_model(
                    base_model=model,
                    finetuned_name=finetuned_name,
                    ollama_name=ollama_name,
                    dataset_version=version.version_id if version else "unknown",
                    trigger_type=trigger.trigger_type,
                    metadata={
                        "lora_config": asdict(self.lora_config),
                        "artifacts": artifacts,
                        "num_pairs": len(pairs),
                    },
                )

            # Update cooldown
            self._last_finetune_times[model] = datetime.now().timestamp()

            training_time = (datetime.now() - start_time).total_seconds()

            if progress_callback:
                progress_callback("Fine-tuning complete!", 1.0)

            return AutoFinetuneResult(
                success=True,
                model_name=model,
                ollama_name=ollama_name,
                adapter_dir=artifacts.get("adapter_dir"),
                gguf_path=gguf_path,
                modelfile_path=modelfile_path,
                dataset_version=version.version_id if version else None,
                training_time_seconds=training_time,
                error_message=None,
                timestamp=datetime.now().isoformat(),
                trigger_type=trigger.trigger_type,
            )

        except Exception as e:
            log.error(f"[unsloth] Auto-finetune failed for {model}: {e}")
            training_time = (datetime.now() - start_time).total_seconds()

            return AutoFinetuneResult(
                success=False,
                model_name=model,
                ollama_name=None,
                adapter_dir=None,
                gguf_path=None,
                modelfile_path=None,
                dataset_version=None,
                training_time_seconds=training_time,
                error_message=str(e),
                timestamp=datetime.now().isoformat(),
                trigger_type=trigger.trigger_type,
            )

        finally:
            # Cleanup temp file
            try:
                Path(jsonl_path).unlink()
            except:
                pass


def register_arena_model(
    base_model: str,
    ollama_name: str,
    dataset_version: str,
    trigger_type: TriggerType,
    db_path: str = "arena.db",
    metadata: Optional[Dict] = None,
) -> bool:
    """
    Register a fine-tuned model in the arena registry.

    This is a convenience function for external registration.
    """
    registry = ModelRegistry(db_path=db_path)
    finetuned_name = f"{base_model}-arena-tuned"
    return registry.register_model(
        base_model=base_model,
        finetuned_name=finetuned_name,
        ollama_name=ollama_name,
        dataset_version=dataset_version,
        trigger_type=trigger_type,
        metadata=metadata,
    )
