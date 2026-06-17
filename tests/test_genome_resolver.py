import os, tempfile
from ollama_arena.genome.registry import CanonicalRegistry


def test_registry_loads():
    reg = CanonicalRegistry()
    models = reg.all_models()
    assert len(models) >= 20


def test_normalize_alias():
    reg = CanonicalRegistry()
    cid = reg.match_by_name("llama3.1:8b")
    assert cid == "meta/llama-3.1-8b"


def test_normalize_instruct_variant():
    reg = CanonicalRegistry()
    cid = reg.match_by_name("llama3.1:8b-instruct-q4_K_M")
    assert cid == "meta/llama-3.1-8b-instruct"


def test_unknown_returns_none():
    reg = CanonicalRegistry()
    assert reg.match_by_name("totally-unknown-model:latest") is None


# ── Resolver tests (added in Task A4) ────────────────────────────────────────
from ollama_arena.genome.resolver import GenomeResolver
from ollama_arena.genome.scanner import LocalModelInfo
from ollama_arena.genome.db import GenomeStore


def _make_resolver(tmp_dir: str) -> GenomeResolver:
    store = GenomeStore(db_path=os.path.join(tmp_dir, "genome.db"))
    registry = CanonicalRegistry()
    return GenomeResolver(store=store, registry=registry)


def test_resolve_known_model_by_name():
    with tempfile.TemporaryDirectory() as tmp:
        resolver = _make_resolver(tmp)
        info = LocalModelInfo(name="llama3.1:8b", size_gb=4.7,
                              modelfile="FROM llama3.1:8b\n")
        match = resolver.resolve(info)
        assert match["genome_id"] == "meta/llama-3.1-8b"
        assert match["confidence"] in ("High", "Confirmed")


def test_resolve_via_from_chain():
    with tempfile.TemporaryDirectory() as tmp:
        resolver = _make_resolver(tmp)
        info = LocalModelInfo(name="my-custom:latest", size_gb=4.7,
                              modelfile="FROM llama3.1:8b-instruct\n",
                              from_model="llama3.1:8b-instruct")
        match = resolver.resolve(info)
        assert match["genome_id"] == "meta/llama-3.1-8b-instruct"
        assert match["confidence"] == "Medium"


def test_resolve_unknown_returns_unknown():
    with tempfile.TemporaryDirectory() as tmp:
        resolver = _make_resolver(tmp)
        info = LocalModelInfo(name="totally-private:latest", size_gb=3.0,
                              modelfile="FROM gguf-file\n")
        match = resolver.resolve(info)
        assert match["confidence"] == "Unknown"
        assert match["genome_id"] is None
