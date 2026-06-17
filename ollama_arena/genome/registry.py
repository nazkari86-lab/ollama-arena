"""Canonical LLM registry loaded from bundled seed_registry.json."""
from __future__ import annotations
import json, re
from pathlib import Path

_SEED = Path(__file__).parent / "data" / "seed_registry.json"


def _normalize(name: str) -> str:
    """Strip quantization suffixes and normalize to lowercase."""
    name = name.strip().lower()
    name = re.sub(r"[-_](q\d[_k]*[msq]*|fp16|f16|f32|bf16|int4|int8|gguf).*$", "", name)
    name = re.sub(r":latest$", "", name)
    return name.strip("-_").strip()


class CanonicalRegistry:
    def __init__(self, seed_path: str | None = None):
        path = Path(seed_path) if seed_path else _SEED
        data = json.loads(path.read_text())
        self._models: dict[str, dict] = {m["id"]: m for m in data["models"]}
        self._alias_map: dict[str, str] = {}
        for m in data["models"]:
            for alias in m.get("aliases", []):
                self._alias_map[_normalize(alias)] = m["id"]
            self._alias_map[_normalize(m["id"].split("/")[-1])] = m["id"]

    def all_models(self) -> list[dict]:
        return list(self._models.values())

    def get(self, model_id: str) -> dict | None:
        return self._models.get(model_id)

    def match_by_name(self, local_name: str) -> str | None:
        """Return canonical id or None."""
        key = _normalize(local_name)
        if key in self._alias_map:
            return self._alias_map[key]
        short = key.split("/")[-1] if "/" in key else key
        return self._alias_map.get(short)
