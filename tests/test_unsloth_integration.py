"""Tests for finetuning/unsloth_integration — enums, dataclasses, ModelRegistry, AutoUnslothIntegrator."""
from __future__ import annotations

import sqlite3
import time

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Enums and dataclasses
# ──────────────────────────────────────────────────────────────────────────────

class TestTriggerType:
    def test_all_values_exist(self):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        assert TriggerType.LOSS_COUNT.value == "loss_count"
        assert TriggerType.WIN_RATE.value == "win_rate"
        assert TriggerType.ELO_GAP.value == "elo_gap"
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.SCHEDULED.value == "scheduled"


class TestFinetuneTrigger:
    def test_default_values(self):
        from ollama_arena.finetuning.unsloth_integration import FinetuneTrigger, TriggerType
        t = FinetuneTrigger(trigger_type=TriggerType.LOSS_COUNT, threshold=100)
        assert t.min_samples == 100
        assert t.cooldown_hours == 24.0
        assert t.enabled is True

    def test_custom_values(self):
        from ollama_arena.finetuning.unsloth_integration import FinetuneTrigger, TriggerType
        t = FinetuneTrigger(
            trigger_type=TriggerType.WIN_RATE,
            threshold=0.5,
            min_samples=50,
            cooldown_hours=12.0,
            enabled=False,
        )
        assert t.threshold == 0.5
        assert t.enabled is False


class TestLoRAConfig:
    def test_default_values(self):
        from ollama_arena.finetuning.unsloth_integration import LoRAConfig
        cfg = LoRAConfig()
        assert cfg.lora_r == 16
        assert cfg.lora_alpha == 32
        assert cfg.epochs == 2

    def test_to_unsloth_config(self):
        from ollama_arena.finetuning.unsloth_integration import LoRAConfig
        from ollama_arena.finetune.unsloth_runner import UnslothConfig
        cfg = LoRAConfig()
        uc = cfg.to_unsloth_config()
        assert isinstance(uc, UnslothConfig)
        assert uc.base_model == cfg.base_model
        assert uc.lora_r == cfg.lora_r
        assert uc.epochs == cfg.epochs

    def test_custom_to_unsloth_config(self):
        from ollama_arena.finetuning.unsloth_integration import LoRAConfig
        cfg = LoRAConfig(lora_r=32, epochs=5, learning_rate=1e-4)
        uc = cfg.to_unsloth_config()
        assert uc.lora_r == 32
        assert uc.epochs == 5


# ──────────────────────────────────────────────────────────────────────────────
# ModelRegistry
# ──────────────────────────────────────────────────────────────────────────────

class TestModelRegistry:
    def _make(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import ModelRegistry
        return ModelRegistry(db_path=str(tmp_path / "reg.db"))

    def test_init_does_not_crash(self, tmp_path):
        reg = self._make(tmp_path)
        assert reg is not None

    def test_register_model_returns_true(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        result = reg.register_model(
            base_model="llama3:8b",
            finetuned_name="llama3-ft-v1",
            ollama_name="llama3-ft-v1",
            dataset_version="v1",
            trigger_type=TriggerType.MANUAL,
        )
        assert result is True

    def test_register_model_duplicate_returns_false(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model(
            base_model="llama3:8b",
            finetuned_name="llama3-ft-v1",
            ollama_name="llama3-ft-v1",
            dataset_version="v1",
            trigger_type=TriggerType.MANUAL,
        )
        result = reg.register_model(
            base_model="llama3:8b",
            finetuned_name="llama3-ft-v1",  # duplicate
            ollama_name="llama3-ft-v1",
            dataset_version="v1",
            trigger_type=TriggerType.MANUAL,
        )
        assert result is False

    def test_get_model_info_registered_model(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model(
            base_model="llama3:8b",
            finetuned_name="llama3-ft-v1",
            ollama_name="llama3-ft-v1",
            dataset_version="v1",
            trigger_type=TriggerType.MANUAL,
        )
        info = reg.get_model_info("llama3-ft-v1")
        assert info is not None
        assert info["finetuned_name"] == "llama3-ft-v1"
        assert info["base_model"] == "llama3:8b"

    def test_get_model_info_nonexistent_returns_none(self, tmp_path):
        reg = self._make(tmp_path)
        info = reg.get_model_info("does_not_exist")
        assert info is None

    def test_list_models_empty_initially(self, tmp_path):
        reg = self._make(tmp_path)
        models = reg.list_models()
        assert models == []

    def test_list_models_returns_registered(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model("base", "ft-v1", "ft-v1", "v1", TriggerType.MANUAL)
        models = reg.list_models()
        assert len(models) == 1

    def test_list_models_filter_by_base_model(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model("llama3:8b", "ft-v1", "ft-v1", "v1", TriggerType.MANUAL)
        reg.register_model("phi3:3b", "ft-v2", "ft-v2", "v1", TriggerType.MANUAL)
        models = reg.list_models(base_model="llama3:8b")
        assert len(models) == 1
        assert models[0]["base_model"] == "llama3:8b"

    def test_list_models_all_includes_inactive(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model("base", "ft-v1", "ft-v1", "v1", TriggerType.MANUAL)
        reg.deactivate_model("ft-v1")
        active_only = reg.list_models(active_only=True)
        all_models = reg.list_models(active_only=False)
        assert len(active_only) == 0
        assert len(all_models) == 1

    def test_update_elo(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model("base", "ft-v1", "ft-v1", "v1", TriggerType.MANUAL)
        reg.update_elo("ft-v1", 1250.0)
        info = reg.get_model_info("ft-v1")
        assert info["elo_rating"] == pytest.approx(1250.0)

    def test_increment_matches(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model("base", "ft-v1", "ft-v1", "v1", TriggerType.MANUAL)
        reg.increment_matches("ft-v1")
        reg.increment_matches("ft-v1")
        info = reg.get_model_info("ft-v1")
        assert info["num_matches"] == 2

    def test_deactivate_model(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        reg.register_model("base", "ft-v1", "ft-v1", "v1", TriggerType.MANUAL)
        reg.deactivate_model("ft-v1")
        models = reg.list_models(active_only=True)
        assert len(models) == 0

    def test_register_model_with_metadata(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import TriggerType
        reg = self._make(tmp_path)
        meta = {"accuracy": 0.95, "notes": "test run"}
        reg.register_model("base", "ft-v1", "ft-v1", "v1", TriggerType.MANUAL, metadata=meta)
        info = reg.get_model_info("ft-v1")
        assert info["metadata"]["accuracy"] == 0.95


# ──────────────────────────────────────────────────────────────────────────────
# AutoUnslothIntegrator — init and should_finetune
# ──────────────────────────────────────────────────────────────────────────────

class TestAutoUnslothIntegrator:
    def _make(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import AutoUnslothIntegrator, FinetuneTrigger, TriggerType
        # Create a minimal DB with needed tables
        db = str(tmp_path / "arena.db")
        with sqlite3.connect(db) as cx:
            cx.execute("CREATE TABLE IF NOT EXISTS task_detail (id INTEGER PRIMARY KEY, match_id INTEGER, category TEXT, outcome TEXT)")
            cx.execute("CREATE TABLE IF NOT EXISTS match_log (id INTEGER PRIMARY KEY, model_a TEXT, model_b TEXT)")
            cx.execute("CREATE TABLE IF NOT EXISTS elo_ratings (model TEXT, category TEXT, rating REAL)")
        return AutoUnslothIntegrator(
            db_path=db,
            triggers=[
                FinetuneTrigger(trigger_type=TriggerType.LOSS_COUNT, threshold=100),
            ]
        )

    def test_init_does_not_crash(self, tmp_path):
        integrator = self._make(tmp_path)
        assert integrator is not None

    def test_default_triggers_set(self, tmp_path):
        integrator = self._make(tmp_path)
        assert len(integrator.triggers) >= 1

    def test_should_finetune_false_with_no_data(self, tmp_path):
        integrator = self._make(tmp_path)
        should, trigger, reason = integrator.should_finetune("llama3:8b")
        assert should is False
        assert trigger is None

    def test_should_finetune_false_when_trigger_disabled(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import AutoUnslothIntegrator, FinetuneTrigger, TriggerType
        db = str(tmp_path / "arena.db")
        with sqlite3.connect(db) as cx:
            cx.execute("CREATE TABLE IF NOT EXISTS task_detail (id INTEGER PRIMARY KEY, match_id INTEGER, category TEXT, outcome TEXT)")
            cx.execute("CREATE TABLE IF NOT EXISTS match_log (id INTEGER PRIMARY KEY, model_a TEXT, model_b TEXT)")
            cx.execute("CREATE TABLE IF NOT EXISTS elo_ratings (model TEXT, category TEXT, rating REAL)")
        integrator = AutoUnslothIntegrator(
            db_path=db,
            triggers=[
                FinetuneTrigger(trigger_type=TriggerType.LOSS_COUNT, threshold=0, enabled=False),
            ]
        )
        should, trigger, reason = integrator.should_finetune("llama3:8b")
        assert should is False

    def test_should_finetune_false_when_in_cooldown(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import AutoUnslothIntegrator, FinetuneTrigger, TriggerType
        db = str(tmp_path / "arena.db")
        with sqlite3.connect(db) as cx:
            cx.execute("CREATE TABLE IF NOT EXISTS task_detail (id INTEGER PRIMARY KEY, match_id INTEGER, category TEXT, outcome TEXT)")
            cx.execute("CREATE TABLE IF NOT EXISTS match_log (id INTEGER PRIMARY KEY, model_a TEXT, model_b TEXT)")
            cx.execute("CREATE TABLE IF NOT EXISTS elo_ratings (model TEXT, category TEXT, rating REAL)")
        integrator = AutoUnslothIntegrator(
            db_path=db,
            triggers=[
                FinetuneTrigger(trigger_type=TriggerType.LOSS_COUNT, threshold=0, cooldown_hours=999),
            ]
        )
        integrator._last_finetune_times["llama3:8b"] = time.time()  # Just ran
        should, trigger, reason = integrator.should_finetune("llama3:8b")
        assert should is False

    def test_get_loss_count_no_data_returns_zero(self, tmp_path):
        integrator = self._make(tmp_path)
        count = integrator._get_loss_count("llama3:8b", None)
        assert count == 0

    def test_get_win_rate_no_data_returns_zero(self, tmp_path):
        integrator = self._make(tmp_path)
        rate = integrator._get_win_rate("llama3:8b", None)
        assert rate == 0.0

    def test_get_win_rate_with_category(self, tmp_path):
        integrator = self._make(tmp_path)
        rate = integrator._get_win_rate("llama3:8b", "coding")
        assert rate == 0.0

    def test_last_finetune_times_initially_empty(self, tmp_path):
        integrator = self._make(tmp_path)
        assert integrator._last_finetune_times == {}

    def test_registry_is_model_registry(self, tmp_path):
        from ollama_arena.finetuning.unsloth_integration import ModelRegistry
        integrator = self._make(tmp_path)
        assert isinstance(integrator.registry, ModelRegistry)

    def test_get_loss_count_counts_only_actual_losses(self, tmp_path):
        """Regression test: _get_loss_count used to count every task_detail
        row touching the model (a stub that ignored outcome), which made the
        LOSS_COUNT trigger fire after N matches played, not N losses. It must
        only count rows where the model was on the losing side."""
        db = str(tmp_path / "arena.db")
        with sqlite3.connect(db) as cx:
            cx.execute("CREATE TABLE match_log (id INTEGER PRIMARY KEY, model_a TEXT, model_b TEXT)")
            cx.execute("CREATE TABLE task_detail (id INTEGER PRIMARY KEY, match_id INTEGER, category TEXT, outcome TEXT)")
            cx.execute("INSERT INTO match_log (id, model_a, model_b) VALUES (1, 'llama3:8b', 'phi3:3b')")
            # 2 losses for llama3:8b (b_wins while llama3:8b is model_a), 1 win (a_wins)
            cx.execute("INSERT INTO task_detail (match_id, category, outcome) VALUES (1, 'coding', 'b_wins')")
            cx.execute("INSERT INTO task_detail (match_id, category, outcome) VALUES (1, 'coding', 'b_wins')")
            cx.execute("INSERT INTO task_detail (match_id, category, outcome) VALUES (1, 'coding', 'a_wins')")

        from ollama_arena.finetuning.unsloth_integration import AutoUnslothIntegrator
        integrator = AutoUnslothIntegrator(db_path=db)
        assert integrator._get_loss_count("llama3:8b", None) == 2

    def test_get_elo_gap_to_leader_computes_real_gap(self, tmp_path):
        """Regression test: _get_elo_gap_to_leader queried a nonexistent
        'elo_after' column (the schema has elo_a_after/elo_b_after), which
        raised inside the try/except and was silently swallowed, always
        returning 0.0. It must compute the actual gap to the category leader."""
        db = str(tmp_path / "arena.db")
        with sqlite3.connect(db) as cx:
            cx.execute("""
                CREATE TABLE match_log (
                    id INTEGER PRIMARY KEY, model_a TEXT, model_b TEXT, category TEXT,
                    elo_a_after REAL, elo_b_after REAL, ts REAL
                )
            """)
            cx.execute(
                "INSERT INTO match_log (model_a, model_b, category, elo_a_after, elo_b_after, ts) "
                "VALUES ('llama3:8b', 'phi3:3b', 'coding', 1300, 1500, 2.0)"
            )

        from ollama_arena.finetuning.unsloth_integration import AutoUnslothIntegrator
        integrator = AutoUnslothIntegrator(db_path=db)
        gap = integrator._get_elo_gap_to_leader("llama3:8b", "coding")
        assert gap == pytest.approx(200.0)

    def test_should_finetune_type_hints_resolve(self):
        """Regression test: should_finetune's return annotation used Tuple
        without importing it from typing. With `from __future__ import
        annotations` this didn't crash at call time, but any introspection
        via typing.get_type_hints() raised NameError."""
        import typing
        from ollama_arena.finetuning.unsloth_integration import AutoUnslothIntegrator
        hints = typing.get_type_hints(AutoUnslothIntegrator.should_finetune)
        assert "return" in hints
