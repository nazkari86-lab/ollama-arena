"""Tests for finetune/unsloth_runner.py."""
from __future__ import annotations
import json
import sys
import unittest.mock as mock
import pytest


class TestUnslothConfig:
    def test_defaults(self):
        from ollama_arena.finetune.unsloth_runner import UnslothConfig
        cfg = UnslothConfig()
        assert cfg.base_model == "unsloth/llama-3.2-3b-instruct-bnb-4bit"
        assert cfg.max_seq_length == 2048
        assert cfg.load_in_4bit is True
        assert cfg.lora_r == 16
        assert cfg.lora_alpha == 32
        assert cfg.lora_dropout == 0.0
        assert cfg.learning_rate == pytest.approx(2e-4)
        assert cfg.epochs == 2
        assert cfg.batch_size == 2
        assert cfg.output_dir == "outputs/lora"
        assert cfg.save_merged is True
        assert cfg.save_gguf is True
        assert cfg.quant_method == "q4_k_m"

    def test_custom_config(self):
        from ollama_arena.finetune.unsloth_runner import UnslothConfig
        cfg = UnslothConfig(
            base_model="phi3:mini",
            epochs=5,
            batch_size=4,
            output_dir="/tmp/output",
        )
        assert cfg.base_model == "phi3:mini"
        assert cfg.epochs == 5
        assert cfg.output_dir == "/tmp/output"


class TestAlpacaTemplate:
    def test_template_has_placeholders(self):
        from ollama_arena.finetune.unsloth_runner import _ALPACA_TEMPLATE
        assert "{instruction}" in _ALPACA_TEMPLATE
        assert "{output}" in _ALPACA_TEMPLATE
        assert "Instruction" in _ALPACA_TEMPLATE
        assert "Response" in _ALPACA_TEMPLATE


class TestMacosFallbackTrain:
    def test_no_transformers_raises(self, tmp_path):
        from ollama_arena.finetune.unsloth_runner import macos_fallback_train
        with mock.patch.dict(sys.modules, {
            "datasets": None,
            "transformers": None,
            "peft": None,
        }):
            with pytest.raises(RuntimeError, match="macOS fallback requires"):
                macos_fallback_train(str(tmp_path / "data.jsonl"))

    def test_no_datasets_raises(self, tmp_path):
        from ollama_arena.finetune.unsloth_runner import macos_fallback_train
        with mock.patch.dict(sys.modules, {
            "datasets": None,
            "transformers": mock.MagicMock(),
            "peft": mock.MagicMock(),
        }):
            with pytest.raises(RuntimeError, match="macOS fallback requires"):
                macos_fallback_train(str(tmp_path / "data.jsonl"))

    def test_success_with_mocked_deps(self, tmp_path):
        from ollama_arena.finetune.unsloth_runner import macos_fallback_train, UnslothConfig

        # Create a minimal JSONL dataset file
        data_file = tmp_path / "data.jsonl"
        data_file.write_text(
            '{"instruction": "add 1+1", "output": "2"}\n'
            '{"prompt": "subtract 3-1", "chosen": "2"}\n'
        )

        # Mock all heavy ML deps
        mock_datasets = mock.MagicMock()
        mock_transformers = mock.MagicMock()
        mock_peft = mock.MagicMock()

        mock_tokenizer = mock.MagicMock()
        mock_tokenizer.pad_token = None
        mock_tokenizer.eos_token = "<eos>"
        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer

        mock_model = mock.MagicMock()
        mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model
        mock_peft.get_peft_model.return_value = mock_model

        mock_ds = mock.MagicMock()
        mock_ds.column_names = ["instruction", "output"]
        mock_datasets.load_dataset.return_value = mock_ds

        mock_trainer = mock.MagicMock()
        mock_transformers.Trainer.return_value = mock_trainer

        cfg = UnslothConfig(output_dir=str(tmp_path / "output"), epochs=1, batch_size=1)

        with mock.patch.dict(sys.modules, {
            "datasets": mock_datasets,
            "transformers": mock_transformers,
            "peft": mock_peft,
        }):
            # Also need to mock TrainingArguments to not use mps
            mock_transformers.TrainingArguments.return_value = mock.MagicMock()
            result = macos_fallback_train(str(data_file), cfg)

        assert "adapter_dir" in result
        assert "config" in result
        assert result.get("fallback") == "macos_cpu"


class TestUnslothTrain:
    def test_no_unsloth_macos_uses_fallback(self, tmp_path):
        """On macOS, when unsloth is unavailable, uses macos_fallback_train."""
        from ollama_arena.finetune.unsloth_runner import unsloth_train, UnslothConfig

        data_file = tmp_path / "data.jsonl"
        data_file.write_text('{"instruction": "test", "output": "result"}\n')
        cfg = UnslothConfig(output_dir=str(tmp_path / "out"))

        with mock.patch.dict(sys.modules, {
            "unsloth": None,
            "datasets": None,
            "trl": None,
        }), mock.patch("sys.platform", "darwin"), \
           mock.patch("ollama_arena.finetune.unsloth_runner.macos_fallback_train") as mock_fallback:
            mock_fallback.return_value = {"adapter_dir": str(tmp_path / "out" / "adapter"), "fallback": "macos_cpu"}
            result = unsloth_train(str(data_file), cfg)

        mock_fallback.assert_called_once_with(str(data_file), cfg)
        assert result["fallback"] == "macos_cpu"

    def test_no_unsloth_non_macos_raises(self, tmp_path):
        """On non-macOS, missing unsloth raises RuntimeError."""
        from ollama_arena.finetune.unsloth_runner import unsloth_train

        data_file = tmp_path / "data.jsonl"
        data_file.write_text('{"instruction": "test", "output": "result"}\n')

        with mock.patch.dict(sys.modules, {
            "unsloth": None,
            "datasets": None,
            "trl": None,
        }), mock.patch("sys.platform", "linux"):
            with pytest.raises(RuntimeError, match="finetune"):
                unsloth_train(str(data_file))

    def test_full_training_with_mocks(self, tmp_path):
        """Test the full happy path with all dependencies mocked."""
        from ollama_arena.finetune.unsloth_runner import unsloth_train, UnslothConfig

        data_file = tmp_path / "data.jsonl"
        data_file.write_text('{"instruction": "test", "output": "42"}\n')
        cfg = UnslothConfig(
            output_dir=str(tmp_path / "out"),
            save_merged=True,
            save_gguf=True,
            epochs=1,
            batch_size=1,
        )

        mock_model = mock.MagicMock()
        mock_tokenizer = mock.MagicMock()
        mock_ds = mock.MagicMock()
        mock_ds.__len__ = mock.MagicMock(return_value=1)
        mock_ds.map.return_value = mock_ds

        mock_unsloth = mock.MagicMock()
        mock_unsloth.FastLanguageModel.from_pretrained.return_value = (mock_model, mock_tokenizer)
        mock_unsloth.FastLanguageModel.get_peft_model.return_value = mock_model
        mock_unsloth.is_bfloat16_supported.return_value = False

        mock_datasets = mock.MagicMock()
        mock_datasets.load_dataset.return_value = mock_ds

        mock_trl = mock.MagicMock()
        mock_trainer = mock.MagicMock()
        mock_trl.SFTTrainer.return_value = mock_trainer

        with mock.patch.dict(sys.modules, {
            "unsloth": mock_unsloth,
            "datasets": mock_datasets,
            "trl": mock_trl,
        }):
            result = unsloth_train(str(data_file), cfg)

        assert "adapter_dir" in result
        assert "merged_dir" in result
        assert "gguf_path" in result
        assert "config" in result
        mock_trainer.train.assert_called_once()

    def test_no_save_merged_no_gguf(self, tmp_path):
        """When save_merged=False and save_gguf=False, those keys are absent."""
        from ollama_arena.finetune.unsloth_runner import unsloth_train, UnslothConfig

        data_file = tmp_path / "data.jsonl"
        data_file.write_text('{"instruction": "q", "output": "a"}\n')
        cfg = UnslothConfig(
            output_dir=str(tmp_path / "out"),
            save_merged=False,
            save_gguf=False,
        )

        mock_model = mock.MagicMock()
        mock_tokenizer = mock.MagicMock()
        mock_ds = mock.MagicMock()
        mock_ds.__len__ = mock.MagicMock(return_value=1)
        mock_ds.map.return_value = mock_ds

        mock_unsloth = mock.MagicMock()
        mock_unsloth.FastLanguageModel.from_pretrained.return_value = (mock_model, mock_tokenizer)
        mock_unsloth.FastLanguageModel.get_peft_model.return_value = mock_model
        mock_unsloth.is_bfloat16_supported.return_value = True

        mock_datasets = mock.MagicMock()
        mock_datasets.load_dataset.return_value = mock_ds
        mock_trl = mock.MagicMock()
        mock_trl.SFTTrainer.return_value = mock.MagicMock()

        with mock.patch.dict(sys.modules, {
            "unsloth": mock_unsloth,
            "datasets": mock_datasets,
            "trl": mock_trl,
        }):
            result = unsloth_train(str(data_file), cfg)

        assert "merged_dir" not in result
        assert "gguf_path" not in result
        assert "adapter_dir" in result

    def test_config_file_written(self, tmp_path):
        """Verify config.json is written to output directory."""
        from ollama_arena.finetune.unsloth_runner import unsloth_train, UnslothConfig

        data_file = tmp_path / "data.jsonl"
        data_file.write_text('{"instruction": "q", "output": "a"}\n')
        cfg = UnslothConfig(
            output_dir=str(tmp_path / "out"),
            save_merged=False,
            save_gguf=False,
        )

        mock_ds = mock.MagicMock()
        mock_ds.map.return_value = mock_ds
        mock_model = mock.MagicMock()
        mock_tokenizer = mock.MagicMock()

        mock_unsloth = mock.MagicMock()
        mock_unsloth.FastLanguageModel.from_pretrained.return_value = (mock_model, mock_tokenizer)
        mock_unsloth.FastLanguageModel.get_peft_model.return_value = mock_model
        mock_unsloth.is_bfloat16_supported.return_value = False

        mock_datasets = mock.MagicMock()
        mock_datasets.load_dataset.return_value = mock_ds
        mock_trl = mock.MagicMock()
        mock_trl.SFTTrainer.return_value = mock.MagicMock()

        with mock.patch.dict(sys.modules, {
            "unsloth": mock_unsloth,
            "datasets": mock_datasets,
            "trl": mock_trl,
        }):
            result = unsloth_train(str(data_file), cfg)

        config_file = tmp_path / "out" / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["base_model"] == cfg.base_model
