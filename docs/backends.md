# Backends Guide

`ollama-arena` supports multiple LLM inference providers.

## 1. Ollama (Default)

The default backend connects to Ollama running locally.

```bash
# Runs on default http://localhost:11434
ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b
```

If Ollama is running on a different port or host:

```bash
ollama-arena --ollama http://192.168.1.100:11434 match --models ...
```

---

## 2. OpenAI-Compatible Backends

You can hook up any provider that conforms to the OpenAI Chat Completions API standard (`/v1/chat/completions`), such as:
* **vLLM**
* **LM Studio**
* **llama.cpp**
* **OpenAI (Official)**
* **Groq**
* **Together AI**
* **OpenRouter**

Use the `--backend` and `--api-key` parameters globally:

```bash
# Example: LM Studio
ollama-arena --backend lmstudio match --models A,B

# Example: Custom endpoint with API Key
ollama-arena \
  --backend https://api.together.xyz/v1 \
  --api-key YOUR_API_KEY \
  match --models meta-llama/Llama-3-70b-chat-hf,mistralai/Mixtral-8x7B-Instruct-v0.1
```

### Supported Backend Presets
If you supply a preset name to `--backend`, it maps to these default URLs:
* `vllm` -> `http://localhost:8000/v1`
* `lmstudio` -> `http://localhost:1234/v1`
* `llamacpp` -> `http://localhost:8080/v1`
* `openai` -> `https://api.openai.com/v1`
* `groq` -> `https://api.groq.com/openai/v1`
* `together` -> `https://api.together.xyz/v1`
* `openrouter` -> `https://openrouter.ai/api/v1`

---

## 3. HuggingFace / Transformers Backend (In-process)

For direct in-process inference using PyTorch and HuggingFace Transformers, install the package with `[hf]` extra:

```bash
pip install "ollama-arena[hf]"
```

Initialize your arena programmatically with the `TransformersBackend`:

```python
from ollama_arena.arena import Arena
from ollama_arena.backends import TransformersBackend

arena = Arena(backend=TransformersBackend(device="cuda"))
```
