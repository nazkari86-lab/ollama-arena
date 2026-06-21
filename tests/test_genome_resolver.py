import json, os, tempfile
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


def test_alias_collision_logs_warning_instead_of_silent_overwrite(caplog):
    """Regression test: two different models whose aliases normalize to the
    same key previously caused a silent dict overwrite in _alias_map, with
    no signal that one model's alias became unreachable. The collision must
    now be logged so it's visible rather than silently swallowed.
    """
    with tempfile.TemporaryDirectory() as tmp:
        seed_path = os.path.join(tmp, "seed.json")
        with open(seed_path, "w") as f:
            json.dump({
                "version": "1.0",
                "models": [
                    {"id": "org-a/model-one", "name": "Model One",
                     "aliases": ["shared-alias"]},
                    {"id": "org-b/model-two", "name": "Model Two",
                     "aliases": ["shared-alias"]},
                ],
            }, f)
        import logging
        with caplog.at_level(logging.WARNING, logger="arena.genome.registry"):
            reg = CanonicalRegistry(seed_path=seed_path)
        assert any("shared-alias" in rec.message for rec in caplog.records)
        # last-seeded model wins the lookup (documented, now-visible behavior)
        assert reg.match_by_name("shared-alias") == "org-b/model-two"


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
