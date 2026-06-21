"""Tests for re-export modules (migrations.py and genome_store.py)."""


class TestMigrationsReexport:
    def test_apply_migrations_importable(self):
        from ollama_arena.migrations import apply_migrations
        assert callable(apply_migrations)

    def test_migrations_list_importable(self):
        from ollama_arena.migrations import MIGRATIONS
        assert isinstance(MIGRATIONS, list)

    def test_current_version_importable(self):
        from ollama_arena.migrations import current_version
        assert callable(current_version)


class TestGenomeStoreReexport:
    def test_genome_store_importable(self):
        from ollama_arena.storage.genome_store import GenomeStore
        assert GenomeStore is not None
