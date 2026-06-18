"""Speculative Decoding backend — wraps llama-server OpenAI-compat API.

Each spec server runs llama.cpp with --spec-draft-model, exposing port 8888-8897.
Model names use the "spec:<name>" prefix (e.g. "spec:qwen3-14b").
"""
from __future__ import annotations
import json, logging, os, re, subprocess, time
from pathlib import Path
import requests

from .base import GenResult, strip_thinking, inject_system

log = logging.getLogger("arena.backend.spec")

HOME = Path.home()

# Registry: spec model name → server config
SPEC_SERVERS: dict[str, dict] = {
    "spec:qwen3-14b":  {"port": 8888, "main": "qwen3:14b",           "draft": "qwen3:1.7b",           "ctx": 8192,  "script": str(HOME / "llama-spec-serve.sh")},
    "spec:coder":      {"port": 8889, "main": "qwen2.5-coder:14b",   "draft": "qwen2.5-coder:1.5b",   "ctx": 16384, "script": str(HOME / "llama-spec-serve-coder.sh")},
    "spec:qwen3-8b":   {"port": 8890, "main": "qwen3:8b",            "draft": "qwen3:1.7b",           "ctx": 8192,  "script": str(HOME / "llama-spec-serve-qwen3-8b.sh")},
    "spec:deepseek":   {"port": 8891, "main": "deepseek-r1:ctx32k",  "draft": "deepseek-r1:1.5b",     "ctx": 32768, "script": str(HOME / "llama-spec-serve-deepseek.sh")},
    "spec:hermes":     {"port": 8892, "main": "hermes3:8b",          "draft": "llama3.2:1b",          "ctx": 8192,  "script": str(HOME / "llama-spec-serve-hermes.sh")},
    "spec:codestral":  {"port": 8893, "main": "codestral:22b",       "draft": "mistral:7b",           "ctx": 32768, "script": str(HOME / "llama-spec-serve-codestral.sh")},
    "spec:gemma4-26b": {"port": 8894, "main": "gemma4-26b-fast",     "draft": "gemma4:12b",           "ctx": 8192,  "script": str(HOME / "llama-spec-serve-gemma4-26b.sh")},
    "spec:dolphin":    {"port": 8895, "main": "dolphin3:8b",         "draft": "llama3.2:1b",          "ctx": 8192,  "script": str(HOME / "llama-spec-serve-dolphin.sh")},
    "spec:llama31":    {"port": 8896, "main": "llama3.1:8b",         "draft": "llama3.2:1b",          "ctx": 8192,  "script": str(HOME / "llama-spec-serve-llama31.sh")},
    "spec:granite":    {"port": 8897, "main": "granite3.1-dense:8b", "draft": "granite3.1-dense:2b",  "ctx": 8192,  "script": str(HOME / "llama-spec-serve-granite.sh")},
}

# Reverse port → spec name
_PORT_TO_SPEC: dict[int, str] = {cfg["port"]: name for name, cfg in SPEC_SERVERS.items()}


def is_spec_model(model: str) -> bool:
    return model.startswith("spec:")


def spec_name_from_port(port: int) -> str | None:
    return _PORT_TO_SPEC.get(port)


class SpeculativeBackend:
    """OpenAI-compat client targeting a llama-server speculative decoding instance."""

    name = "speculative"

    def __init__(self, spec_name: str, timeout: int = 300):
        if spec_name not in SPEC_SERVERS:
            raise ValueError(f"Unknown spec server: {spec_name}. Available: {list(SPEC_SERVERS)}")
        self.spec_name = spec_name
        self.cfg = SPEC_SERVERS[spec_name]
        self.port = self.cfg["port"]
        self.base = f"http://localhost:{self.port}/v1"
        self.timeout = timeout
        self._headers = {"Authorization": "Bearer EMPTY", "Content-Type": "application/json"}
        self._model_id: str | None = None  # cached model ID from /v1/models

    def _get_model_id(self) -> str:
        if self._model_id:
            return self._model_id
        try:
            r = requests.get(f"{self.base}/models", headers=self._headers, timeout=3)
            models = r.json().get("data", [])
            if models:
                self._model_id = models[0]["id"]
                return self._model_id
        except Exception:
            pass
        return self.cfg["main"]

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        messages = inject_system([{"role": "user", "content": prompt}])
        return self.generate_with_tools(model, messages, tools=[], **opts)

    def generate_with_tools(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult:
        server_model = self._get_model_id()
        # Use a generous default — thinking models need tokens for CoT before output
        max_tokens = opts.get("num_predict", opts.get("max_tokens", 2048))
        body = {
            "model":          server_model,
            "messages":       inject_system(messages),
            "temperature":    opts.get("temperature", 0.0),
            "max_tokens":     max_tokens,
            "stream":         True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = tools

        t0 = time.time()
        ttft = 0.0
        text = ""
        first = True
        tokens_in = tokens_out = 0
        timings: dict = {}
        try:
            r = requests.post(
                f"{self.base}/chat/completions",
                json=body, headers=self._headers, stream=True, timeout=self.timeout,
            )
            
            tool_calls = []

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
                if (t := chunk.get("timings")):
                    timings = t
                
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                
                # Check for tool_calls delta
                if "tool_calls" in delta:
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        while len(tool_calls) <= idx:
                            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
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
            
            if tool_calls:
                text = json.dumps(tool_calls)

            text = strip_thinking(text)

            # TPS from timings (llama-server provides predicted_ms)
            if timings.get("predicted_ms") and tokens_out:
                tps = round(tokens_out / (timings["predicted_ms"] / 1000), 1)
            elif latency > 0 and tokens_out:
                tps = round(tokens_out / latency, 1)
            else:
                tps = round(len(text.split()) * 1.3 / latency, 1) if latency > 0 else 0.0

            # Speculative decoding acceptance rate (if available)
            accept_rate = 0.0
            if timings.get("predicted_n") and timings.get("predicted_n_spec"):
                accept_rate = round(timings["predicted_n_spec"] / timings["predicted_n"], 3)

            return GenResult(
                text=text,
                model=f"{self.spec_name}",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_s=round(latency, 3),
                tps=tps,
                time_to_first=round(ttft, 3),
                spec_accept_rate=accept_rate,
                backend_type="speculative",
            )
        except Exception as e:
            return GenResult(text="", model=self.spec_name, error=str(e),
                             latency_s=round(time.time() - t0, 3))

    def list_models(self) -> list[str]:
        if self.is_alive():
            return [self.spec_name]
        return []

    def is_alive(self) -> bool:
        try:
            r = requests.get(f"http://localhost:{self.port}/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def health(self) -> dict:
        """Return detailed health/status dict for the web dashboard."""
        alive = self.is_alive()
        return {
            "name": self.spec_name,
            "port": self.port,
            "main": self.cfg["main"],
            "draft": self.cfg["draft"],
            "ctx": self.cfg["ctx"],
            "running": alive,
            "model_id": self._get_model_id() if alive else None,
        }


class SpecManager:
    """Start/stop speculative decoding servers and check their status."""

    def __init__(self):
        self._procs: dict[str, subprocess.Popen] = {}

    def status(self) -> list[dict]:
        out = []
        for name, cfg in SPEC_SERVERS.items():
            port = cfg["port"]
            running = self._is_port_open(port)
            pid = None
            if name in self._procs:
                p = self._procs[name]
                if p.poll() is None:
                    pid = p.pid
                else:
                    del self._procs[name]
            out.append({
                "name": name,
                "port": port,
                "main": cfg["main"],
                "draft": cfg["draft"],
                "ctx": cfg["ctx"],
                "running": running,
                "pid": pid,
                "script": cfg["script"],
            })
        return out

    def start(self, name: str) -> dict:
        if name not in SPEC_SERVERS:
            return {"ok": False, "error": f"Unknown: {name}"}
        cfg = SPEC_SERVERS[name]
        if self._is_port_open(cfg["port"]):
            return {"ok": True, "message": f"{name} already running on :{cfg['port']}"}
        script = cfg["script"]
        if not Path(script).exists():
            return {"ok": False, "error": f"Script not found: {script}"}
        try:
            proc = subprocess.Popen(
                ["bash", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._procs[name] = proc
            # Wait up to 30s for server to come up
            for _ in range(30):
                time.sleep(1)
                if self._is_port_open(cfg["port"]):
                    log.info(f"[spec] {name} started on :{cfg['port']}")
                    return {"ok": True, "pid": proc.pid, "port": cfg["port"]}
            return {"ok": False, "error": "Server did not start within 30s"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stop(self, name: str) -> dict:
        cfg = SPEC_SERVERS.get(name)
        if not cfg:
            return {"ok": False, "error": f"Unknown: {name}"}
        port = cfg["port"]
        killed = False
        # Kill by port
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=3,
            )
            for pid_str in result.stdout.strip().split():
                subprocess.run(["kill", "-9", pid_str], timeout=2)
                killed = True
        except Exception:
            pass
        # Kill tracked proc
        if name in self._procs:
            try:
                self._procs[name].kill()
            except Exception:
                pass
            del self._procs[name]
        return {"ok": True, "killed": killed}

    def stop_all(self) -> dict:
        results = {}
        for name in list(SPEC_SERVERS.keys()):
            results[name] = self.stop(name)
        return results

    @staticmethod
    def _is_port_open(port: int) -> bool:
        import socket
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except OSError:
            return False
