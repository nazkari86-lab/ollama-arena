import os, tempfile
from ollama_arena.genome.db import GenomeStore
from ollama_arena.genome.graph import GraphEngine


def _seeded_store(tmp: str) -> GenomeStore:
    store = GenomeStore(db_path=os.path.join(tmp, "genome.db"))
    for mid, name, parent, relation in [
        ("meta/llama-3.1-8b", "Llama 3.1 8B", None, None),
        ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B Instruct",
         "meta/llama-3.1-8b", "fine_tuned_from"),
        ("NousResearch/hermes-3-llama-3.1-8b", "Hermes 3",
         "meta/llama-3.1-8b-instruct", "fine_tuned_from"),
    ]:
        store.upsert_canonical({"id": mid, "name": name, "family": "Llama",
                                 "org": "", "license": "", "source_url": "",
                                 "architecture": {}, "lineage": {}})
        if parent:
            store.add_lineage(mid, parent, relation, 1.0, "registry")
    return store


def test_graph_nodes_and_edges():
    with tempfile.TemporaryDirectory() as tmp:
        store = _seeded_store(tmp)
        g = GraphEngine(store)
        data = g.to_d3()
        node_ids = {n["id"] for n in data["nodes"]}
        assert "meta/llama-3.1-8b" in node_ids
        assert "NousResearch/hermes-3-llama-3.1-8b" in node_ids
        links = data["links"]
        assert any(l["source"] == "NousResearch/hermes-3-llama-3.1-8b"
                   and l["target"] == "meta/llama-3.1-8b-instruct" for l in links)


def test_graph_subtree():
    with tempfile.TemporaryDirectory() as tmp:
        store = _seeded_store(tmp)
        g = GraphEngine(store)
        sub = g.subtree("meta/llama-3.1-8b")
        ids = {n["id"] for n in sub["nodes"]}
        assert "meta/llama-3.1-8b" in ids
        assert "NousResearch/hermes-3-llama-3.1-8b" in ids


def test_to_d3_does_not_duplicate_edges():
    """Regression test: get_lineage(id) matches rows where id is either the
    child or the parent, so to_d3() previously iterated every canonical
    model and re-appended the same edge once while visiting the child's row
    and again while visiting the parent's row, doubling every link.
    """
    with tempfile.TemporaryDirectory() as tmp:
        store = _seeded_store(tmp)
        g = GraphEngine(store)
        data = g.to_d3()
        # exactly 2 edges were seeded: instruct->base and hermes->instruct
        assert len(data["links"]) == 2
        edge_keys = [(l["source"], l["target"], l["relation"]) for l in data["links"]]
        assert len(edge_keys) == len(set(edge_keys))


def test_subtree_does_not_duplicate_edges():
    with tempfile.TemporaryDirectory() as tmp:
        store = _seeded_store(tmp)
        g = GraphEngine(store)
        sub = g.subtree("meta/llama-3.1-8b")
        edge_keys = [(l["source"], l["target"], l["relation"]) for l in sub["links"]]
        assert len(edge_keys) == len(set(edge_keys))
