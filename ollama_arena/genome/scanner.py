"""Scan local Ollama models and extract metadata."""
from __future__ import annotations
import re, subprocess, logging
from dataclasses import dataclass, field

log = logging.getLogger("arena.genome.scanner")


@dataclass
class LocalModelInfo:
    name: str
    size_gb: float = 0.0
    modelfile: str = ""
    from_model: str | None = None
    parameters: dict = field(default_factory=dict)


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


class OllamaScanner:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url

    def _parse_list_output(self, raw: str) -> list[str]:
        names = []
        for line in raw.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                names.append(parts[0])
        return names

    def _get_list(self) -> list[str]:
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True,
                               timeout=10)
            return self._parse_list_output(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.warning(f"ollama list failed: {e}")
            return []

    def _get_modelfile(self, name: str) -> tuple[str, float]:
        """Returns (modelfile_content, size_gb)."""
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
                if line.startswith(name):
                    parts = line.split()
                    if len(parts) >= 4:
                        size_gb = _parse_size(parts[2] + " " + parts[3])
                    break
        except Exception:
            pass
        return content, size_gb

    def scan_local(self) -> list[LocalModelInfo]:
        """Return list of LocalModelInfo for all local Ollama models."""
        names = self._get_list()
        results = []
        for name in names:
            mf_content, size_gb = self._get_modelfile(name)
            parsed = parse_modelfile(mf_content)
            results.append(LocalModelInfo(
                name=name,
                size_gb=size_gb,
                modelfile=mf_content,
                from_model=parsed["from"],
                parameters=parsed["parameters"],
            ))
        return results
