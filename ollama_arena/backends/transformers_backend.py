"""In-process generation via HuggingFace Transformers.

Slower than a dedicated server like vLLM (no batching, no continuous
batching, no FlashAttention by default) but useful for one-off checks of
checkpoints that aren't packaged for Ollama yet.

Requires the [hf] extra: transformers, torch, accelerate.
"""
from __future__ import annotations
import logging, time
from typing import Optional

from .base import GenResult, ChatTurnResult, inject_system

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
        images = opts.pop("images", None)
        msg: dict = {"role": "user", "content": prompt}
        if images:
            msg["images"] = images
        return self.generate_with_tools(model, [msg], tools=[], **opts)

    def chat_turn(
        self, model: str, messages: list[dict], tools: list[dict], **opts,
    ) -> ChatTurnResult:
        """Single-turn chat completion (no native tool calling in HF path)."""
        try:
            import torch
            model_obj, tok = self._load(model)
        except Exception as e:
            return ChatTurnResult(error=str(e))

        max_new = opts.get("num_predict", opts.get("max_tokens", 1024))
        temperature = opts.get("temperature", 0.0)
        do_sample = temperature > 0.0
        normalized = inject_system(messages)

        try:
            inputs_text = tok.apply_chat_template(
                normalized, tokenize=False, add_generation_prompt=True,
            )
        except Exception:
            inputs_text = "\n\n".join(
                f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
                for m in normalized
            )

        t0 = time.time()
        try:
            inputs = tok(inputs_text, return_tensors="pt").to(model_obj.device)
            tokens_in = inputs["input_ids"].shape[1]
            with torch.inference_mode():
                out = model_obj.generate(
                    **inputs,
                    max_new_tokens=max_new,
                    do_sample=do_sample,
                    temperature=max(temperature, 1e-3) if do_sample else 1.0,
                    pad_token_id=tok.pad_token_id,
                )
            tokens_out = out.shape[1] - tokens_in
            text = tok.decode(out[0, tokens_in:], skip_special_tokens=True).strip()
        except Exception as e:
            # Mirrors every other backend's contract: generation failures
            # (e.g. CUDA OOM, tokenizer mismatch) come back as an error
            # result instead of an uncaught exception killing the caller
            # (agent loops, benchmark runs, etc.).
            return ChatTurnResult(error=str(e), latency_s=round(time.time() - t0, 3))

        latency = time.time() - t0
        return ChatTurnResult(
            text=text,
            tool_calls=[],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_s=round(latency, 3),
            time_to_first=round(latency, 3),
            finish_reason="stop",
        )

    def generate_with_tools(
        self, model: str, messages: list[dict], tools: list[dict], **opts,
    ) -> GenResult:
        turn = self.chat_turn(model, messages, tools, **opts)
        if turn.error:
            return GenResult(text="", model=model, error=turn.error, latency_s=turn.latency_s)
        tps = turn.tokens_out / turn.latency_s if turn.latency_s > 0 else 0.0
        return GenResult(
            text=turn.text,
            model=model,
            tokens_in=turn.tokens_in,
            tokens_out=turn.tokens_out,
            latency_s=turn.latency_s,
            tps=round(tps, 1),
            time_to_first=turn.time_to_first,
            finish_reason=turn.finish_reason,
            backend_type=self.name,
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
