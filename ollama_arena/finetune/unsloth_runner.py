"""Unsloth LoRA training, GGUF export. Requires the [finetune] extra and CUDA."""
from __future__ import annotations
import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

log = logging.getLogger("arena.finetune.unsloth")


@dataclass
class UnslothConfig:
    base_model:        str  = "unsloth/llama-3.2-3b-instruct-bnb-4bit"
    max_seq_length:    int  = 2048
    load_in_4bit:      bool = True
    lora_r:            int  = 16
    lora_alpha:        int  = 32
    lora_dropout:      float = 0.0
    learning_rate:     float = 2e-4
    epochs:            int  = 2
    batch_size:        int  = 2
    grad_accumulation: int  = 4
    warmup_steps:      int  = 5
    output_dir:        str  = "outputs/lora"
    save_merged:       bool = True
    save_gguf:         bool = True             # ready to import to Ollama
    quant_method:      str  = "q4_k_m"


_ALPACA_TEMPLATE = (
    "Below is an instruction that describes a task. "
    "Write a response that appropriately completes the request.\n\n"
    "### Instruction:\n{instruction}\n\n### Response:\n{output}"
)


def macos_fallback_train(jsonl_path: str, config: UnslothConfig | None = None) -> dict:
    """CPU/MPS-friendly training path when Unsloth/bitsandbytes is unavailable (macOS)."""
    try:
        from datasets import load_dataset as hf_load
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
        from peft import LoraConfig, get_peft_model, TaskType
    except ImportError as e:
        raise RuntimeError(
            "macOS fallback requires: pip install transformers peft datasets\n"
            f"({e})"
        )

    cfg = config or UnslothConfig()
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    adapter_dir = out / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)

    log.warning("[unsloth] macOS/CPU fallback — training without bitsandbytes")
    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        trust_remote_code=True,
        torch_dtype="auto",
    )
    lora = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora)

    ds = hf_load("json", data_files=jsonl_path, split="train")

    def fmt(rec):
        text = _ALPACA_TEMPLATE.format(
            instruction=rec.get("instruction") or rec.get("prompt", ""),
            output=rec.get("output") or rec.get("chosen", ""),
        )
        return tokenizer(text, truncation=True, max_length=cfg.max_seq_length)

    ds = ds.map(fmt, remove_columns=ds.column_names)

    args = TrainingArguments(
        output_dir=str(out),
        per_device_train_batch_size=max(1, cfg.batch_size),
        gradient_accumulation_steps=cfg.grad_accumulation,
        num_train_epochs=cfg.epochs,
        learning_rate=cfg.learning_rate,
        logging_steps=10,
        save_strategy="epoch",
        report_to="none",
    )
    trainer = Trainer(model=model, args=args, train_dataset=ds)
    trainer.train()
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    meta = out / "config.json"
    meta.write_text(json.dumps({**asdict(cfg), "fallback": "macos_cpu"}, indent=2))
    artifacts = {
        "adapter_dir": str(adapter_dir),
        "config": str(meta),
        "fallback": "macos_cpu",
    }
    log.info(f"[unsloth] macOS fallback done → {artifacts}")
    return artifacts


def unsloth_train(jsonl_path: str, config: UnslothConfig | None = None) -> dict:
    """
    Fine-tune `config.base_model` on the dataset at `jsonl_path` using Unsloth.

    Returns a dict describing where artifacts ended up:
        {"adapter_dir": ..., "merged_dir": ..., "gguf_path": ...}
    """
    try:
        from unsloth import FastLanguageModel, is_bfloat16_supported
        from datasets import load_dataset as hf_load
        from trl import SFTTrainer, SFTConfig
    except ImportError as e:
        if sys.platform == "darwin":
            log.warning("[unsloth] Unsloth unavailable on macOS — using CPU/MPS fallback")
            return macos_fallback_train(jsonl_path, config)
        raise RuntimeError(
            "Install fine-tune dependencies first:\n"
            "    pip install 'ollama-arena[finetune]'\n"
            f"({e})"
        )

    cfg = config or UnslothConfig()
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    log.info(f"[unsloth] loading {cfg.base_model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name      = cfg.base_model,
        max_seq_length  = cfg.max_seq_length,
        load_in_4bit    = cfg.load_in_4bit,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r              = cfg.lora_r,
        target_modules = ["q_proj","k_proj","v_proj","o_proj",
                          "gate_proj","up_proj","down_proj"],
        lora_alpha     = cfg.lora_alpha,
        lora_dropout   = cfg.lora_dropout,
        bias           = "none",
        use_gradient_checkpointing = "unsloth",
    )

    ds = hf_load("json", data_files=jsonl_path, split="train")

    def fmt(rec):
        return {"text": _ALPACA_TEMPLATE.format(
            instruction=rec["instruction"], output=rec["output"]
        )}
    ds = ds.map(fmt)

    sft_cfg = SFTConfig(
        output_dir                  = str(out),
        per_device_train_batch_size = cfg.batch_size,
        gradient_accumulation_steps = cfg.grad_accumulation,
        warmup_steps                = cfg.warmup_steps,
        num_train_epochs            = cfg.epochs,
        learning_rate               = cfg.learning_rate,
        logging_steps               = 10,
        save_strategy               = "epoch",
        fp16                        = not is_bfloat16_supported(),
        bf16                        = is_bfloat16_supported(),
        max_seq_length              = cfg.max_seq_length,
        dataset_text_field          = "text",
        report_to                   = "none",
    )

    log.info(f"[unsloth] training on {len(ds)} examples → {out}")
    trainer = SFTTrainer(
        model = model, tokenizer = tokenizer,
        train_dataset = ds, args = sft_cfg,
    )
    trainer.train()

    adapter_dir = out / "adapter"
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    artifacts: dict[str, str] = {"adapter_dir": str(adapter_dir)}

    if cfg.save_merged:
        merged = out / "merged"
        model.save_pretrained_merged(str(merged), tokenizer, save_method="merged_16bit")
        artifacts["merged_dir"] = str(merged)

    if cfg.save_gguf:
        gguf_path = out / f"model-{cfg.quant_method}.gguf"
        model.save_pretrained_gguf(str(out), tokenizer, quantization_method=cfg.quant_method)
        artifacts["gguf_path"] = str(gguf_path)

    meta = out / "config.json"
    meta.write_text(json.dumps(asdict(cfg), indent=2))
    artifacts["config"] = str(meta)
    log.info(f"[unsloth] done → {artifacts}")
    return artifacts
