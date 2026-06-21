import os, tempfile, pytest
from ollama_arena.genome.db import GenomeStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        yield GenomeStore(db_path=os.path.join(tmp, "genome.db"))


def test_upsert_and_get_canonical(store):
    store.upsert_canonical({
        "id": "meta/llama-3.1-8b",
        "name": "Llama 3.1 8B",
        "family": "Llama 3",
        "org": "Meta",
        "license": "Llama 3.1",
        "source_url": "https://huggingface.co/meta-llama/Meta-Llama-3.1-8B",
        "architecture": {"n_layers": 32, "hidden_size": 4096, "n_heads": 32,
                         "n_kv_heads": 8, "context_length": 131072,
                         "vocab_size": 128256, "params_b": 8.0},
        "lineage": {"trained_from": None, "fine_tuned_from": None},
    })
    row = store.get_canonical("meta/llama-3.1-8b")
    assert row["name"] == "Llama 3.1 8B"
    assert row["architecture"]["n_layers"] == 32


def test_upsert_local_model(store):
    store.upsert_local("llama3.1:8b", genome_id="meta/llama-3.1-8b",
                        confidence="High", quant="q4_K_M", size_gb=4.7,
                        modelfile="FROM llama3.1:8b\n")
    rows = store.list_local()
    assert len(rows) == 1
    assert rows[0]["genome_id"] == "meta/llama-3.1-8b"


def test_add_lineage(store):
    store.upsert_canonical({"id": "a", "name": "A", "family": "", "org": "",
                             "license": "", "source_url": "", "architecture": {},
                             "lineage": {}})
    store.upsert_canonical({"id": "b", "name": "B", "family": "", "org": "",
                             "license": "", "source_url": "", "architecture": {},
                             "lineage": {}})
    store.add_lineage(child_id="b", parent_id="a",
                      relation="fine_tuned_from", confidence=0.9,
                      evidence_source="modelfile")
    edges = store.get_lineage("b")
    assert edges[0]["parent_id"] == "a"
    assert edges[0]["relation"] == "fine_tuned_from"


def test_upsert_canonical_updates_license_and_source_url(store):
    """Regression test: the ON CONFLICT DO UPDATE clause previously omitted
    license and source_url, so re-seeding a canonical model with updated
    metadata silently kept the original (possibly stale) values forever.
    """
    store.upsert_canonical({
        "id": "a", "name": "A", "family": "F", "org": "O",
        "license": "MIT", "source_url": "https://old",
        "architecture": {}, "lineage": {},
    })
    store.upsert_canonical({
        "id": "a", "name": "A2", "family": "F2", "org": "O2",
        "license": "Apache-2.0", "source_url": "https://new",
        "architecture": {}, "lineage": {},
    })
    row = store.get_canonical("a")
    assert row["license"] == "Apache-2.0"
    assert row["source_url"] == "https://new"
