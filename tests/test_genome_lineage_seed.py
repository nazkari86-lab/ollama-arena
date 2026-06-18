import os
import tempfile

from ollama_arena.genome.db import GenomeStore
from ollama_arena.genome.registry import CanonicalRegistry
from ollama_arena.genome.resolver import GenomeResolver
from ollama_arena.genome.graph import GraphEngine


def test_resolver_seeds_lineage_from_registry():
    with tempfile.TemporaryDirectory() as tmp:
        store = GenomeStore(db_path=os.path.join(tmp, "genome.db"))
        registry = CanonicalRegistry()
        GenomeResolver(store=store, registry=registry)

        lineage = store.get_lineage("meta/llama-3.1-8b-instruct")
        parents = {row["parent_id"] for row in lineage}
        assert "meta/llama-3.1-8b" in parents

        relations = {row["relation"] for row in lineage}
        assert "fine_tuned_from" in relations


def test_seed_lineage_populates_graph_links():
    with tempfile.TemporaryDirectory() as tmp:
        store = GenomeStore(db_path=os.path.join(tmp, "genome.db"))
        registry = CanonicalRegistry()
        GenomeResolver(store=store, registry=registry)

        graph = GraphEngine(store)
        data = graph.to_d3()
        assert len(data["links"]) > 0
        assert any(l["target"] == "meta/llama-3.1-8b" for l in data["links"])


def test_seed_lineage_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "genome.db")
        store = GenomeStore(db_path=db)
        registry = CanonicalRegistry()
        GenomeResolver(store=store, registry=registry)
        first_count = len(store.get_lineage("meta/llama-3.1-8b-instruct"))

        GenomeResolver(store=store, registry=registry)
        second_count = len(store.get_lineage("meta/llama-3.1-8b-instruct"))
        assert first_count == second_count
