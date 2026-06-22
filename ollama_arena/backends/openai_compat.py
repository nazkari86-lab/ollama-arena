"""OpenAI /v1/chat/completions client.

Works against vLLM, LM Studio, llama.cpp server, OpenAI, Groq, Together,
OpenRouter, Fireworks, DeepInfra, or any provider that implements the
same surface.
"""
from __future__ import annotations
import json, logging, os, re, time
import requests

from .base import GenResult, ChatTurnResult, strip_thinking, inject_system

log = logging.getLogger("arena.backend.openai")


def _secrets_store():
    """Lazily imported so importing this module never requires the
    `cryptography` package -- only actually reading/writing a stored key
    does. Indirected through a function (not imported at module scope)
    so tests can monkeypatch it to a tmp-path store."""
    from .. import secrets_store
    return secrets_store


def _image_url(image_data: str) -> str:
    """Normalize base64 or data-URL image payloads for OpenAI vision APIs."""
    if image_data.startswith("data:"):
        return image_data
    return f"data:image/jpeg;base64,{image_data}"


def prepare_messages_for_api(messages: list[dict]) -> list[dict]:
    """Convert arena message dicts (with optional images) to OpenAI content-parts."""
    out: list[dict] = []
    for msg in messages:
        images = msg.get("images")
        if images:
            parts: list[dict] = []
            content = msg.get("content", "")
            if content:
                parts.append({"type": "text", "text": content})
            for img in images:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": _image_url(img)},
                })
            new_msg = {k: v for k, v in msg.items() if k != "images"}
            new_msg["content"] = parts
            out.append(new_msg)
        else:
            out.append(dict(msg))
    return out


class OpenAICompatBackend:
    name = "openai-compat"

    # Convenience presets — every value is an OpenAI-/chat-completions-compatible
    # endpoint. Pair with an env var named like the key in upper-case +
    # "_API_KEY" (e.g. DEEPSEEK_API_KEY, XAI_API_KEY, ANTHROPIC_API_KEY) and
    # the backend will pick it up automatically.
    PRESETS: dict[str, str] = {
        # Local runtimes
        "vllm":       "http://localhost:8000/v1",
        "lmstudio":   "http://localhost:1234/v1",
        "llamacpp":   "http://localhost:8080/v1",
        # Hosted, OpenAI-compatible
        "openai":     "https://api.openai.com/v1",
        "groq":       "https://api.groq.com/openai/v1",
        "together":   "https://api.together.xyz/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "deepinfra":  "https://api.deepinfra.com/v1/openai",
        "fireworks":  "https://api.fireworks.ai/inference/v1",
        # ── Added: top cloud models so you can A/B local vs frontier ──
        "deepseek":   "https://api.deepseek.com/v1",         # DEEPSEEK_API_KEY
        "xai":        "https://api.x.ai/v1",                 # XAI_API_KEY (Grok)
        "grok":       "https://api.x.ai/v1",                 # alias
        "cerebras":   "https://api.cerebras.ai/v1",          # CEREBRAS_API_KEY
        "anthropic":  "https://api.anthropic.com/v1",        # ANTHROPIC_API_KEY
        "mistral":    "https://api.mistral.ai/v1",           # MISTRAL_API_KEY
        "perplexity": "https://api.perplexity.ai",           # PERPLEXITY_API_KEY
        "sambanova":  "https://api.sambanova.ai/v1",         # SAMBANOVA_API_KEY
        "novita":     "https://api.novita.ai/v3/openai",     # NOVITA_API_KEY
        # ── Additional named sources for the simulation model registry ──
        # Each base URL was verified live against the provider's own docs
        # (not guessed) -- see tests/test_openai_compat_presets.py.
        "google-gemini": "https://generativelanguage.googleapis.com/v1beta/openai",  # GEMINI_API_KEY
        "github-models": "https://models.github.ai/inference",                      # GITHUB_TOKEN (PAT)
        "nvidia-nim":    "https://integrate.api.nvidia.com/v1",                     # NVIDIA_API_KEY
        "huggingface-inference-providers": "https://router.huggingface.co/v1",      # HF_TOKEN
        "cohere":        "https://api.cohere.ai/compatibility/v1",                  # COHERE_API_KEY
        "opencode":      "https://opencode.ai/zen/v1",                              # OPENCODE_API_KEY
        # Cloudflare's URL embeds the account id -- {account_id} is filled in
        # from CLOUDFLARE_ACCOUNT_ID at construction time (see __init__).
        "cloudflare-workers-ai": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        # ── Second wave: paid/niche sources, also live-verified ──
        "moonshot":    "https://api.moonshot.ai/v1",                  # MOONSHOT_API_KEY (Kimi)
        "zhipu":       "https://open.bigmodel.cn/api/paas/v4",        # ZHIPU_API_KEY (GLM)
        "dashscope":   "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",  # DASHSCOPE_API_KEY (Qwen)
        "baseten":     "https://inference.baseten.co/v1",             # BASETEN_API_KEY
        "hyperbolic":  "https://api.hyperbolic.xyz/v1",                # HYPERBOLIC_API_KEY
        "friendli":    "https://api.friendli.ai/serverless/v1",        # FRIENDLI_TOKEN
        "lambda":      "https://api.lambda.ai/v1",                    # LAMBDA_API_KEY
        "siliconflow": "https://api.siliconflow.cn/v1",                # SILICONFLOW_API_KEY
        "upstage":     "https://api.upstage.ai/v1",                   # UPSTAGE_API_KEY
        "vercel-ai-gateway": "https://ai-gateway.vercel.sh/v1",        # AI_GATEWAY_API_KEY
        # Databricks' URL is per-workspace -- {workspace_url} is filled in
        # from DATABRICKS_WORKSPACE_URL at construction time (see __init__).
        "databricks":  "{workspace_url}/serving-endpoints",
    }

    # Per-preset env-var override (if the standard `<KEY>_API_KEY` doesn't fit)
    _ENV_KEY_MAP: dict[str, str] = {
        "openai":     "OPENAI_API_KEY",
        "groq":       "GROQ_API_KEY",
        "together":   "TOGETHER_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "deepinfra":  "DEEPINFRA_API_KEY",
        "fireworks":  "FIREWORKS_API_KEY",
        "deepseek":   "DEEPSEEK_API_KEY",
        "xai":        "XAI_API_KEY",
        "grok":       "XAI_API_KEY",
        "cerebras":   "CEREBRAS_API_KEY",
        "anthropic":  "ANTHROPIC_API_KEY",
        "mistral":    "MISTRAL_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "sambanova":  "SAMBANOVA_API_KEY",
        "novita":     "NOVITA_API_KEY",
        "google-gemini": "GEMINI_API_KEY",
        "github-models": "GITHUB_TOKEN",
        "nvidia-nim":    "NVIDIA_API_KEY",
        "huggingface-inference-providers": "HF_TOKEN",
        "cohere":        "COHERE_API_KEY",
        "opencode":      "OPENCODE_API_KEY",
        "cloudflare-workers-ai": "CLOUDFLARE_API_TOKEN",
        "moonshot":    "MOONSHOT_API_KEY",
        "zhipu":       "ZHIPU_API_KEY",
        "dashscope":   "DASHSCOPE_API_KEY",
        "baseten":     "BASETEN_API_KEY",
        "hyperbolic":  "HYPERBOLIC_API_KEY",
        "friendli":    "FRIENDLI_TOKEN",
        "lambda":      "LAMBDA_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY",
        "upstage":     "UPSTAGE_API_KEY",
        "vercel-ai-gateway": "AI_GATEWAY_API_KEY",
        "databricks":  "DATABRICKS_TOKEN",
    }

    def __init__(self, base_url: str = "http://localhost:8000/v1",
                 api_key: str | None = None, timeout: int = 180):
        # Remember the preset name so we can resolve the right env-var key
        preset = base_url if base_url in self.PRESETS else None
        if preset:
            base_url = self.PRESETS[preset]
            if preset == "cloudflare-workers-ai":
                account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
                if account_id:
                    base_url = base_url.format(account_id=account_id)
            elif preset == "databricks":
                workspace_url = os.environ.get("DATABRICKS_WORKSPACE_URL")
                if workspace_url:
                    base_url = base_url.format(workspace_url=workspace_url.rstrip("/"))
        self.base = base_url.rstrip("/")
        # If the caller didn't pass an API key, look in the preset-specific
        # env var first, then fall back to OPENAI_API_KEY for backward compat.
        env_key = self._ENV_KEY_MAP.get(preset or "", "OPENAI_API_KEY")
        stored_key = None
        if preset:
            try:
                stored_key = _secrets_store().get_key(preset)
            except Exception:
                stored_key = None
        self.api_key = (
            api_key
            or os.environ.get(env_key)
            or os.environ.get("OPENAI_API_KEY")
            or stored_key
            or "EMPTY"
        )
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        images = opts.pop("images", None)
        msg: dict = {"role": "user", "content": prompt}
        if images:
            msg["images"] = images
        messages = inject_system([msg])
        return self.generate_with_tools(model, messages, tools=[], **opts)

    def chat_turn(
        self, model: str, messages: list[dict], tools: list[dict], **opts
    ) -> ChatTurnResult:
        """One chat completion turn; returns content and/or tool_calls separately."""
        body = {
            "model":       model,
            "messages":    prepare_messages_for_api(inject_system(messages, tools)),
            "temperature": opts.get("temperature", 0.0),
            "max_tokens":  opts.get("num_predict", opts.get("max_tokens", 16384)),
            "stream":      True,
        }
        if tools:
            body["tools"] = tools

        t0 = time.time()
        ttft = 0.0
        text = ""
        first = True
        tokens_in = tokens_out = 0
        tool_calls: list[dict] = []
        finish_reason = "stop"
        r = None
        try:
            r = requests.post(
                f"{self.base}/chat/completions",
                json=body, headers=self._headers, stream=True, timeout=self.timeout,
            )
            if r.status_code != 200:
                return ChatTurnResult(
                    error=r.text, latency_s=round(time.time() - t0, 3),
                )

            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if (usage := chunk.get("usage")):
                    tokens_in  = usage.get("prompt_tokens", tokens_in)
                    tokens_out = usage.get("completion_tokens", tokens_out)

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                if fr := choice.get("finish_reason"):
                    finish_reason = fr
                delta = choice.get("delta", {})

                if "tool_calls" in delta:
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        while len(tool_calls) <= idx:
                            tool_calls.append({
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            })
                        if tc.get("id"):
                            tool_calls[idx]["id"] = tc["id"]
                        if tc.get("function", {}).get("name"):
                            tool_calls[idx]["function"]["name"] += tc["function"]["name"]
                        if tc.get("function", {}).get("arguments"):
                            tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]

                piece = delta.get("content", "") or ""
                if first and (piece or tool_calls):
                    ttft = time.time() - t0
                    first = False
                text += piece

            latency = time.time() - t0
            text = strip_thinking(text)
            return ChatTurnResult(
                text=text,
                tool_calls=tool_calls,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_s=round(latency, 3),
                time_to_first=round(ttft, 3),
                finish_reason=finish_reason,
            )
        except Exception as e:
            return ChatTurnResult(
                error=str(e), latency_s=round(time.time() - t0, 3),
            )
        finally:
            if r is not None:
                r.close()

    def generate_with_tools(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult:
        """Single-turn completion; legacy path for backends without AgentLoop."""
        turn = self.chat_turn(model, messages, tools, **opts)
        if turn.error:
            return GenResult(
                text="", model=model, error=turn.error, latency_s=turn.latency_s,
            )
        text = turn.text
        if turn.tool_calls and not text:
            text = json.dumps(turn.tool_calls)
        tps = (
            turn.tokens_out / turn.latency_s
            if turn.latency_s > 0 and turn.tokens_out > 0
            else (len(text.split()) * 1.3 / turn.latency_s if turn.latency_s > 0 else 0.0)
        )
        return GenResult(
            text=text,
            model=model,
            tokens_in=turn.tokens_in,
            tokens_out=turn.tokens_out,
            latency_s=turn.latency_s,
            tps=round(tps, 1),
            time_to_first=turn.time_to_first,
            finish_reason=turn.finish_reason,
            tool_calls=turn.tool_calls,
            backend_type=self.name,
        )

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base}/models", headers=self._headers, timeout=5)
            data = r.json().get("data", [])
            return [m["id"] for m in data]
        except Exception:
            return []

    def is_alive(self) -> bool:
        try:
            r = requests.get(f"{self.base}/models", headers=self._headers, timeout=3)
            return r.status_code < 500
        except Exception:
            return False
