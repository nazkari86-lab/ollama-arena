"""Scan local Ollama models and extract metadata."""
from __future__ import annotations
import re
import subprocess
import logging
from dataclasses import dataclass, field

log = logging.getLogger("arena.genome.scanner")

_QUANT_RE = re.compile(
    r"(?:^|[-_:])(q\d[_k]*[msq]*|fp16|f16|f32|bf16|int4|int8|gguf)(?:$|[-_:])",
    re.IGNORECASE,
)


@dataclass
class LocalModelInfo:
    name: str
    size_gb: float = 0.0
    modelfile: str = ""
    from_model: str | None = None
    parameters: dict = field(default_factory=dict)
    quant: str = ""


def extract_quant(name: str) -> str:
    """Extract quantization tag from a model name (e.g. llama3.1:8b-q4_K_M → q4_K_M)."""
    if not name:
        return ""
    for part in reversed(re.split(r"[:/]", name)):
        m = _QUANT_RE.search(f"-{part}")
        if m:
            return m.group(1)
    m = _QUANT_RE.search(name.replace(":", "-"))
    return m.group(1) if m else ""


def parse_modelfile(content: str) -> dict:
    """Extract FROM and PARAMETER directives from a Modelfile string."""
    result: dict = {"from": None, "parameters": {}}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if not parts:
            continue
        directive = parts[0].upper()
        if directive == "FROM" and len(parts) >= 2:
            result["from"] = parts[1]
        elif directive == "PARAMETER" and len(parts) >= 3:
            result["parameters"][parts[1].lower()] = parts[2]
    return result


def _parse_size(s: str) -> float:
    """'4.7 GB' → 4.7, '512 MB' → 0.5"""
    s = s.strip()
    m = re.match(r"([\d.]+)\s*(GB|MB|KB)", s, re.IGNORECASE)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "MB":
        val /= 1024
    elif unit == "KB":
        val /= 1024 * 1024
    return round(val, 2)


def _size_bytes_to_gb(n: int) -> float:
    if not n:
        return 0.0
    return round(n / (1024 ** 3), 2)


class OllamaScanner:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url.rstrip("/")

    def _parse_list_output(self, raw: str) -> list[str]:
        names = []
        for line in raw.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                names.append(parts[0])
        return names

    def _get_list_api(self) -> list[str]:
        try:
            import requests
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            r.raise_for_status()
            models = r.json().get("models", [])
        except Exception as e:
            log.warning(f"ollama /api/tags failed ({self.ollama_url}): {e}")
            return []
        # The Ollama API is an external trust boundary — one malformed entry
        # (e.g. missing "name") must not blank out every other valid model
        # in the response, so skip bad entries individually instead of
        # letting a single KeyError discard the whole list.
        names = []
        for m in models:
            name = m.get("name") if isinstance(m, dict) else None
            if name:
                names.append(name)
            else:
                log.warning(f"ollama /api/tags returned a model entry without a name: {m!r}")
        return names

    def _get_list_cli(self) -> list[str]:
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True,
                               timeout=10)
            return self._parse_list_output(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.warning(f"ollama list failed: {e}")
            return []

    def _get_list(self) -> list[str]:
        names = self._get_list_api()
        if names:
            return names
        if self.ollama_url in ("http://localhost:11434", "http://127.0.0.1:11434"):
            return self._get_list_cli()
        return []

    def _get_modelfile_api(self, name: str) -> tuple[str, float]:
        try:
            import requests
            r = requests.post(
                f"{self.ollama_url}/api/show",
                json={"name": name},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            modelfile = data.get("modelfile") or ""
            size_gb = _size_bytes_to_gb(int(data.get("size", 0) or 0))
            return modelfile, size_gb
        except Exception as e:
            log.warning(f"ollama /api/show failed for {name}: {e}")
            return "", 0.0

    def _get_modelfile_cli(self, name: str) -> tuple[str, float]:
        try:
            r = subprocess.run(["ollama", "show", name, "--modelfile"],
                               capture_output=True, text=True, timeout=15)
            content = r.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            content = ""
        size_gb = 0.0
        try:
            r2 = subprocess.run(["ollama", "list"], capture_output=True, text=True,
                                timeout=5)
            for line in r2.stdout.splitlines():
                parts = line.split()
                # Match on the exact first column, not line.startswith(name) —
                # a substring/prefix match would also match e.g. "llama3:8b"
                # against the row for "llama3:8b-instruct" and report the
                # wrong model's size.
                if parts and parts[0] == name:
                    if len(parts) >= 4:
                        size_gb = _parse_size(parts[2] + " " + parts[3])
                    break
        except Exception:
            pass
        return content, size_gb

    def _get_modelfile(self, name: str) -> tuple[str, float]:
        content, size_gb = self._get_modelfile_api(name)
        if content or size_gb:
            return content, size_gb
        if self.ollama_url in ("http://localhost:11434", "http://127.0.0.1:11434"):
            return self._get_modelfile_cli(name)
        return "", 0.0

    def scan_local(self, on_progress=None) -> list[LocalModelInfo]:
        """Return list of LocalModelInfo for all local Ollama models.

        ``on_progress(current, total, name)`` is called after each model when provided.
        """
        names = self._get_list()
        results = []
        total = len(names)
        for i, name in enumerate(names, 1):
            mf_content, size_gb = self._get_modelfile(name)
            parsed = parse_modelfile(mf_content)
            quant = extract_quant(name)
            results.append(LocalModelInfo(
                name=name,
                size_gb=size_gb,
                modelfile=mf_content,
                from_model=parsed["from"],
                parameters=parsed["parameters"],
                quant=quant,
            ))
            if on_progress:
                on_progress(i, total, name)
        return results
