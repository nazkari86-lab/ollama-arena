"""Tests for cli/finetune_cmd.py."""
from __future__ import annotations
import unittest.mock as mock
import pytest


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.db = ":memory:"
    args.ollama = "http://localhost:11434"
    args.backend = None
    args.api_key = None
    args.model = None
    args.teacher = None
    args.category = "coding"
    args.format = "sft"
    args.out = None
    args.out_dir = None
    args.n_tasks = 5
    args.base_model = None
    args.epochs = 1
    args.ollama_name = None
    args.run = False
    args.analyze = False
    args.generate = False
    args.train = None
    args.skip_train = False
    args.skip_export = False
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def _mock_console():
    c = mock.MagicMock()
    c.status.return_value.__enter__ = mock.MagicMock(return_value=None)
    c.status.return_value.__exit__ = mock.MagicMock(return_value=False)
    return c


class TestCmdFinetuneNoOp:
    def test_no_flag_prints_help(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args()
        mock_c = _mock_console()
        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c):
            cmd_finetune(args)
        mock_c.print.assert_called()


class TestCmdFinetuneAnalyze:
    def test_analyze_prints_weakness_report(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(analyze=True, model=None)
        mock_c = _mock_console()
        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.finetune_cmd.cmd_finetune.__module__",
                        "ollama_arena.cli.finetune_cmd"), \
             mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=[]) as mock_aw, \
             mock.patch("ollama_arena.finetune.weakness_report", return_value="WEAK") as mock_wr, \
             mock.patch("ollama_arena.finetune.task_failure_report", return_value="TFR") as mock_tfr, \
             mock.patch("ollama_arena.finetune.build_training_dataset"), \
             mock.patch("ollama_arena.finetune.build_dpo_dataset"), \
             mock.patch("ollama_arena.finetune.save_jsonl"), \
             mock.patch("ollama_arena.finetune.unsloth_train"), \
             mock.patch("ollama_arena.finetune.UnslothConfig"), \
             mock.patch("ollama_arena.finetune.build_modelfile"), \
             mock.patch("ollama_arena.finetune.install_to_ollama"):
            cmd_finetune(args)
        mock_wr.assert_called_once()
        mock_c.print.assert_called()

    def test_analyze_with_model_shows_failure_report(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(analyze=True, model="llama3:8b")
        mock_c = _mock_console()
        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=[]), \
             mock.patch("ollama_arena.finetune.weakness_report", return_value="WR"), \
             mock.patch("ollama_arena.finetune.task_failure_report", return_value="TFR") as mock_tfr, \
             mock.patch("ollama_arena.finetune.build_training_dataset"), \
             mock.patch("ollama_arena.finetune.build_dpo_dataset"), \
             mock.patch("ollama_arena.finetune.save_jsonl"), \
             mock.patch("ollama_arena.finetune.unsloth_train"), \
             mock.patch("ollama_arena.finetune.UnslothConfig"), \
             mock.patch("ollama_arena.finetune.build_modelfile"), \
             mock.patch("ollama_arena.finetune.install_to_ollama"):
            cmd_finetune(args)
        mock_tfr.assert_called_once()


class TestCmdFinetuneTrain:
    def test_train_calls_unsloth_train(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(train="data.jsonl")
        mock_c = _mock_console()

        mock_config_instance = mock.MagicMock()
        mock_UnslothConfig = mock.MagicMock(return_value=mock_config_instance)
        mock_unsloth_train = mock.MagicMock(return_value={"adapter_dir": "/out/adapter"})

        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=[]), \
             mock.patch("ollama_arena.finetune.weakness_report", return_value=""), \
             mock.patch("ollama_arena.finetune.task_failure_report", return_value=""), \
             mock.patch("ollama_arena.finetune.build_training_dataset", return_value=[]), \
             mock.patch("ollama_arena.finetune.build_dpo_dataset", return_value=[]), \
             mock.patch("ollama_arena.finetune.save_jsonl", return_value="out.jsonl"), \
             mock.patch("ollama_arena.finetune.unsloth_train", mock_unsloth_train), \
             mock.patch("ollama_arena.finetune.UnslothConfig", mock_UnslothConfig), \
             mock.patch("ollama_arena.finetune.build_modelfile", return_value="/tmp/Modelfile"), \
             mock.patch("ollama_arena.finetune.install_to_ollama", return_value=True):
            cmd_finetune(args)

        mock_unsloth_train.assert_called_once()


class TestCmdFinetuneGenerate:
    def test_generate_missing_model_exits(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(generate=True, model=None)
        mock_c = _mock_console()
        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=[]), \
             mock.patch("ollama_arena.finetune.weakness_report", return_value=""), \
             mock.patch("ollama_arena.finetune.task_failure_report", return_value=""), \
             mock.patch("ollama_arena.finetune.build_training_dataset", return_value=[]), \
             mock.patch("ollama_arena.finetune.build_dpo_dataset", return_value=[]), \
             mock.patch("ollama_arena.finetune.save_jsonl", return_value="f.jsonl"), \
             mock.patch("ollama_arena.finetune.unsloth_train", return_value={}), \
             mock.patch("ollama_arena.finetune.UnslothConfig"), \
             mock.patch("ollama_arena.finetune.build_modelfile", return_value=""), \
             mock.patch("ollama_arena.finetune.install_to_ollama", return_value=True), \
             pytest.raises(SystemExit):
            cmd_finetune(args)

    def test_generate_sft(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(generate=True, model="llama3:8b", category="coding", format="sft")
        mock_c = _mock_console()
        mock_backend = mock.MagicMock()
        mock_ds = [{"instruction": "x", "output": "y"}]

        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend), \
             mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=[]), \
             mock.patch("ollama_arena.finetune.weakness_report", return_value=""), \
             mock.patch("ollama_arena.finetune.task_failure_report", return_value=""), \
             mock.patch("ollama_arena.finetune.build_training_dataset", return_value=mock_ds), \
             mock.patch("ollama_arena.finetune.build_dpo_dataset", return_value=mock_ds), \
             mock.patch("ollama_arena.finetune.save_jsonl", return_value="out.jsonl"), \
             mock.patch("ollama_arena.finetune.unsloth_train", return_value={}), \
             mock.patch("ollama_arena.finetune.UnslothConfig"), \
             mock.patch("ollama_arena.finetune.build_modelfile", return_value=""), \
             mock.patch("ollama_arena.finetune.install_to_ollama", return_value=True):
            cmd_finetune(args)
        mock_c.print.assert_called()

    def test_generate_dpo(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(generate=True, model="llama3:8b", category="coding", format="dpo")
        mock_c = _mock_console()
        mock_backend = mock.MagicMock()
        mock_ds = [{"prompt": "x", "chosen": "y", "rejected": "z"}]

        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend), \
             mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=[]), \
             mock.patch("ollama_arena.finetune.weakness_report", return_value=""), \
             mock.patch("ollama_arena.finetune.task_failure_report", return_value=""), \
             mock.patch("ollama_arena.finetune.build_training_dataset", return_value=[]), \
             mock.patch("ollama_arena.finetune.build_dpo_dataset", return_value=mock_ds), \
             mock.patch("ollama_arena.finetune.save_jsonl", return_value="out.jsonl"), \
             mock.patch("ollama_arena.finetune.unsloth_train", return_value={}), \
             mock.patch("ollama_arena.finetune.UnslothConfig"), \
             mock.patch("ollama_arena.finetune.build_modelfile", return_value=""), \
             mock.patch("ollama_arena.finetune.install_to_ollama", return_value=True):
            cmd_finetune(args)
        mock_c.print.assert_called()


class TestCmdFinetuneRun:
    def _common_patches(self):
        return [
            mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=[]),
            mock.patch("ollama_arena.finetune.weakness_report", return_value=""),
            mock.patch("ollama_arena.finetune.task_failure_report", return_value=""),
            mock.patch("ollama_arena.finetune.build_training_dataset", return_value=[{"x": 1}]),
            mock.patch("ollama_arena.finetune.build_dpo_dataset", return_value=[{"x": 1}]),
            mock.patch("ollama_arena.finetune.save_jsonl", return_value="out.jsonl"),
            mock.patch("ollama_arena.finetune.unsloth_train", return_value={"adapter_dir": "/out", "gguf_path": None}),
            mock.patch("ollama_arena.finetune.UnslothConfig"),
            mock.patch("ollama_arena.finetune.build_modelfile", return_value="/tmp/Modelfile"),
            mock.patch("ollama_arena.finetune.install_to_ollama", return_value=True),
        ]

    def test_run_missing_model_exits(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(run=True, model=None, category="coding")
        mock_c = _mock_console()
        with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c):
            with pytest.raises(SystemExit):
                cmd_finetune(args)

    def test_run_skip_train(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(run=True, model="llama3:8b", category="coding", skip_train=True)
        mock_c = _mock_console()
        mock_backend = mock.MagicMock()
        patchers = self._common_patches()
        for p in patchers:
            p.start()
        try:
            with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
                 mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend):
                cmd_finetune(args)
        finally:
            for p in patchers:
                p.stop()

    def test_run_export_missing_gguf_exits_nonzero(self):
        """If training produced no gguf_path (or the file doesn't exist on disk),
        --run must report the failure and exit 1 instead of silently returning
        success with no model actually installed to Ollama."""
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(run=True, model="llama3:8b", category="coding")
        mock_c = _mock_console()
        mock_backend = mock.MagicMock()
        mock_install = mock.MagicMock(return_value=True)
        patchers = self._common_patches()  # unsloth_train returns gguf_path=None
        patchers[-1] = mock.patch("ollama_arena.finetune.install_to_ollama", mock_install)
        for p in patchers:
            p.start()
        try:
            with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
                 mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend):
                with pytest.raises(SystemExit) as exc_info:
                    cmd_finetune(args)
        finally:
            for p in patchers:
                p.stop()
        assert exc_info.value.code == 1
        mock_install.assert_not_called()
        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "Export failed" in printed

    def test_run_export_install_failure_exits_nonzero(self):
        """If a gguf artifact exists but install_to_ollama() reports failure,
        --run must exit 1, not silently succeed with no model installed."""
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(run=True, model="llama3:8b", category="coding")
        mock_c = _mock_console()
        mock_backend = mock.MagicMock()
        patchers = self._common_patches()
        patchers[6] = mock.patch(
            "ollama_arena.finetune.unsloth_train",
            return_value={"adapter_dir": "/out", "gguf_path": __file__},  # any existing file
        )
        patchers[-1] = mock.patch("ollama_arena.finetune.install_to_ollama", return_value=False)
        for p in patchers:
            p.start()
        try:
            with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
                 mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend):
                with pytest.raises(SystemExit) as exc_info:
                    cmd_finetune(args)
        finally:
            for p in patchers:
                p.stop()
        assert exc_info.value.code == 1
        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "Failed to install" in printed

    def test_run_export_success(self):
        """Happy path: gguf exists and install succeeds -> no exit, success message."""
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(run=True, model="llama3:8b", category="coding")
        mock_c = _mock_console()
        mock_backend = mock.MagicMock()
        patchers = self._common_patches()
        patchers[6] = mock.patch(
            "ollama_arena.finetune.unsloth_train",
            return_value={"adapter_dir": "/out", "gguf_path": __file__},
        )
        patchers[-1] = mock.patch("ollama_arena.finetune.install_to_ollama", return_value=True)
        for p in patchers:
            p.start()
        try:
            with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
                 mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend):
                cmd_finetune(args)  # must not raise
        finally:
            for p in patchers:
                p.stop()
        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "exported to Ollama model" in printed

    def test_run_with_weakness_match(self):
        from ollama_arena.cli.finetune_cmd import cmd_finetune
        args = _make_args(run=True, model="llama3:8b", category="coding", skip_train=True)
        mock_c = _mock_console()
        mock_backend = mock.MagicMock()
        weak_data = [{"model": "llama3:8b", "category": "coding", "win_rate": 0.3, "samples": 10}]
        patchers = self._common_patches()
        patchers[0] = mock.patch("ollama_arena.finetune.analyze_weaknesses", return_value=weak_data)
        for p in patchers:
            p.start()
        try:
            with mock.patch("ollama_arena.cli.finetune_cmd._console", return_value=mock_c), \
                 mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend):
                cmd_finetune(args)
        finally:
            for p in patchers:
                p.stop()
        mock_c.print.assert_called()
