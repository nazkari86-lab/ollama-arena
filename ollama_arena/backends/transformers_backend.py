"""
Direct HuggingFace Transformers backend — runs models in-process via PyTorch.

Skips the HTTP round-trip required by Ollama/vLLM. Useful for:
  - Models not yet packaged for Ollama
  - Quick local A/B testing of HF checkpoints
  - GPU-rich machines where the HTTP layer is the bottleneck

Install:  pip install 'ollama-arena[hf]'   →  transformers, torch, accelerate
"""
from __future__ import annotations
import logging, time
from typing import Optional

from .base import GenResult

log = logging.getLogger("arena.backend.hf")


class TransformersBackend:
    name = "transformers"

    def __init__(self, default_model: str | None = None,
                 device: str = "auto", torch_dtype: str = "auto",
                 cache_dir: Optional[str] = None):
        self.default_model = default_model
        self.device = device
        self.torch_dtype = torch_dtype
        self.cache_dir = cache_dir
        self._cache: dict[str, tuple] = {}     # model_id -> (model, tokenizer)

    def _load(self, model_id: str):
        if model_id in self._cache:
            return self._cache[model_id]
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            raise RuntimeError(
                "Install: pip install 'ollama-arena[hf]'"
            )
        dtype = self.torch_dtype
        if dtype == "auto":
            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        log.info(f"[hf] loading {model_id} on {self.device} ({dtype})")
        tok = AutoTokenizer.from_pretrained(model_id, cache_dir=self.cache_dir)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=dtype, device_map=self.device,
            cache_dir=self.cache_dir,
        )
        model.eval()
        self._cache[model_id] = (model, tok)
        return model, tok

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        try:
            import torch
            model_obj, tok = self._load(model)
        except Exception as e:
            return GenResult(text="", model=model, error=str(e))

        max_new = opts.get("num_predict", opts.get("max_tokens", 1024))
        temperature = opts.get("temperature", 0.0)
        do_sample = temperature > 0.0

        # Try chat template first; fall back to raw prompt
        try:
            messages = [{"role": "user", "content": prompt}]
            inputs_text = tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        except Exception:
            inputs_text = prompt

        inputs = tok(inputs_text, return_tensors="pt").to(model_obj.device)
        tokens_in = inputs["input_ids"].shape[1]

        t0 = time.time()
        with torch.inference_mode():
            out = model_obj.generate(
                **inputs,
                max_new_tokens=max_new,
                do_sample=do_sample,
                temperature=max(temperature, 1e-3) if do_sample else 1.0,
                pad_token_id=tok.pad_token_id,
            )
        latency = time.time() - t0
        tokens_out = out.shape[1] - tokens_in
        text = tok.decode(out[0, tokens_in:], skip_special_tokens=True).strip()
        tps = tokens_out / latency if latency > 0 else 0.0

        return GenResult(
            text=text, model=model,
            tokens_in=tokens_in, tokens_out=tokens_out,
            latency_s=round(latency, 3), tps=round(tps, 1),
        )

    def list_models(self) -> list[str]:
        return list(self._cache.keys()) + ([self.default_model] if self.default_model else [])

    def is_alive(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            return True
        except ImportError:
            return False
