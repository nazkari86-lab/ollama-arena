"""Tests for cli/genome_cmd.py."""
from __future__ import annotations
import unittest.mock as mock
import pytest


def _mock_console():
    c = mock.MagicMock()
    return c


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.ollama = "http://localhost:11434"
    args.genome_db = "genome.db"
    args.genome_cmd = None
    args.model = None
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def _patch_genome_imports(tmp_path=None):
    """Returns context manager patching all genome internal imports."""
    mock_store = mock.MagicMock()
    mock_store.list_local.return_value = []
    mock_registry = mock.MagicMock()
    mock_resolver = mock.MagicMock()
    mock_resolver.scan_and_resolve_all.return_value = []
    mock_scanner = mock.MagicMock()
    mock_scanner.scan_local.return_value = []
    mock_engine = mock.MagicMock()
    mock_engine.to_d3.return_value = {"nodes": [], "links": []}
    mock_engine.subtree.return_value = {"nodes": [], "links": []}

    mock_GenomeStore = mock.MagicMock(return_value=mock_store)
    mock_CanonicalRegistry = mock.MagicMock(return_value=mock_registry)
    mock_GenomeResolver = mock.MagicMock(return_value=mock_resolver)
    mock_OllamaScanner = mock.MagicMock(return_value=mock_scanner)
    mock_GraphEngine = mock.MagicMock(return_value=mock_engine)

    return (
        mock.patch("ollama_arena.genome.db.GenomeStore", mock_GenomeStore),
        mock.patch("ollama_arena.genome.registry.CanonicalRegistry", mock_CanonicalRegistry),
        mock.patch("ollama_arena.genome.resolver.GenomeResolver", mock_GenomeResolver),
        mock.patch("ollama_arena.genome.scanner.OllamaScanner", mock_OllamaScanner),
        mock.patch("ollama_arena.genome.graph.GraphEngine", mock_GraphEngine),
        mock_store, mock_registry, mock_resolver, mock_scanner, mock_engine,
    )


class TestCmdGenomeNoSubcmd:
    def test_no_genome_cmd_prints_usage(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd=None)
        mock_c = _mock_console()

        p1 = mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c)
        p2 = mock.patch("ollama_arena.genome.db.GenomeStore")
        p3 = mock.patch("ollama_arena.genome.registry.CanonicalRegistry")
        p4 = mock.patch("ollama_arena.genome.resolver.GenomeResolver")

        with p1, p2, p3, p4:
            cmd_genome(args)

        mock_c.print.assert_called()
        # Should print usage hint
        call_args_list = mock_c.print.call_args_list
        printed_text = " ".join(str(c) for c in call_args_list)
        assert "Usage" in printed_text or "genome" in printed_text.lower()


class TestCmdGenomeScan:
    def test_scan_no_local_models(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="scan")
        mock_c = _mock_console()
        mock_store = mock.MagicMock()
        mock_scanner_obj = mock.MagicMock()
        mock_scanner_obj.scan_local.return_value = []

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore", return_value=mock_store), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry"), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner", return_value=mock_scanner_obj), \
             mock.patch("ollama_arena.genome.graph.GraphEngine"), \
             mock.patch.dict("sys.modules", {"rich.table": mock.MagicMock()}):
            cmd_genome(args)

        mock_c.print.assert_called()

    def test_scan_with_models(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="scan")
        mock_c = _mock_console()

        mock_local_model = mock.MagicMock()
        mock_local_model.name = "llama3:8b"
        mock_local_model.size_gb = 4.5

        mock_store = mock.MagicMock()
        mock_registry = mock.MagicMock()
        mock_resolver = mock.MagicMock()
        mock_resolver.scan_and_resolve_all.return_value = [
            {"name": "llama3:8b", "genome_id": "llama3", "confidence": "high"}
        ]
        mock_scanner_obj = mock.MagicMock()
        mock_scanner_obj.scan_local.return_value = [mock_local_model]

        mock_table = mock.MagicMock()
        mock_rich_table = mock.MagicMock()
        mock_rich_table.Table.return_value = mock_table

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore", return_value=mock_store), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry", return_value=mock_registry), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver", return_value=mock_resolver), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner", return_value=mock_scanner_obj), \
             mock.patch("ollama_arena.genome.graph.GraphEngine"), \
             mock.patch.dict("sys.modules", {"rich.table": mock_rich_table}):
            cmd_genome(args)

        mock_resolver.scan_and_resolve_all.assert_called_once()
        mock_c.print.assert_called()

    def test_scan_model_with_no_genome_id(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="scan")
        mock_c = _mock_console()

        mock_local_model = mock.MagicMock()
        mock_local_model.name = "unknown_model"
        mock_local_model.size_gb = 2.0

        mock_resolver = mock.MagicMock()
        mock_resolver.scan_and_resolve_all.return_value = [
            {"name": "unknown_model", "genome_id": None, "confidence": "low"}
        ]
        mock_scanner_obj = mock.MagicMock()
        mock_scanner_obj.scan_local.return_value = [mock_local_model]

        mock_rich_table = mock.MagicMock()
        mock_rich_table.Table.return_value = mock.MagicMock()

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore"), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry"), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver", return_value=mock_resolver), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner", return_value=mock_scanner_obj), \
             mock.patch("ollama_arena.genome.graph.GraphEngine"), \
             mock.patch.dict("sys.modules", {"rich.table": mock_rich_table}):
            cmd_genome(args)


class TestCmdGenomeTree:
    def test_tree_empty_graph(self):
        """Regression test: an empty graph used to silently print nothing at
        all, leaving the user with no feedback that the command did nothing.
        It must now print an explicit 'no lineage data' message."""
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="tree", model=None)
        mock_c = _mock_console()
        mock_engine = mock.MagicMock()
        mock_engine.to_d3.return_value = {"nodes": [], "links": []}

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore"), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry"), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner"), \
             mock.patch("ollama_arena.genome.graph.GraphEngine", return_value=mock_engine), \
             mock.patch.dict("sys.modules", {
                 "rich": mock.MagicMock(),
                 "rich.tree": mock.MagicMock(),
             }):
            cmd_genome(args)

        mock_c.print.assert_called_once()
        printed = str(mock_c.print.call_args_list[0])
        assert "No lineage data" in printed

    def test_tree_unknown_model_filter_warns_not_silent(self):
        """Regression test: `genome tree --model <unknown>` returned an empty
        subtree and printed nothing, identical to a successful empty scan.
        The user couldn't tell 'no data anywhere' apart from 'this model
        wasn't found'. It must now name the model in the warning."""
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="tree", model="totally_unknown_model")
        mock_c = _mock_console()
        mock_engine = mock.MagicMock()
        mock_engine.subtree.return_value = {"nodes": [], "links": []}
        mock_registry = mock.MagicMock()
        mock_registry.match_by_name.return_value = None

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore"), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry", return_value=mock_registry), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner"), \
             mock.patch("ollama_arena.genome.graph.GraphEngine", return_value=mock_engine), \
             mock.patch.dict("sys.modules", {
                 "rich": mock.MagicMock(),
                 "rich.tree": mock.MagicMock(),
             }):
            cmd_genome(args)

        mock_c.print.assert_called_once()
        printed = str(mock_c.print.call_args_list[0])
        assert "totally_unknown_model" in printed

    def test_tree_with_nodes(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="tree", model=None)
        mock_c = _mock_console()

        mock_engine = mock.MagicMock()
        mock_engine.to_d3.return_value = {
            "nodes": [
                {"id": "root", "name": "LLaMA", "params_b": 7.0},
                {"id": "child", "name": "LLaMA-chat", "params_b": 7.0},
            ],
            "links": [{"source": "child", "target": "root"}],
        }

        mock_rich_tree = mock.MagicMock()
        mock_tree_instance = mock.MagicMock()
        mock_tree_instance.add.return_value = mock.MagicMock()
        mock_rich_tree.Tree.return_value = mock_tree_instance

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore"), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry"), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner"), \
             mock.patch("ollama_arena.genome.graph.GraphEngine", return_value=mock_engine), \
             mock.patch.dict("sys.modules", {
                 "rich": mock.MagicMock(),
                 "rich.tree": mock_rich_tree,
             }):
            cmd_genome(args)

    def test_tree_with_model_filter(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="tree", model="llama3")
        mock_c = _mock_console()

        mock_registry = mock.MagicMock()
        mock_registry.match_by_name.return_value = "llama3-id"

        mock_engine = mock.MagicMock()
        mock_engine.subtree.return_value = {"nodes": [], "links": []}

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore"), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry", return_value=mock_registry), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner"), \
             mock.patch("ollama_arena.genome.graph.GraphEngine", return_value=mock_engine), \
             mock.patch.dict("sys.modules", {
                 "rich": mock.MagicMock(),
                 "rich.tree": mock.MagicMock(),
             }):
            cmd_genome(args)

        mock_engine.subtree.assert_called_once_with("llama3-id")


class TestCmdGenomeShow:
    def test_show_canonical_found(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="show", model="llama3:8b")
        mock_c = _mock_console()

        mock_registry = mock.MagicMock()
        mock_registry.match_by_name.return_value = "llama3-id"
        mock_registry.get.return_value = {
            "name": "LLaMA-3", "family": "llama", "org": "Meta",
            "architecture": {"params_b": 8, "n_layers": 32, "context_length": 8192},
        }

        mock_store = mock.MagicMock()
        mock_store.list_local.return_value = [
            {"name": "llama3:8b", "confidence": "high", "size_gb": 4.5}
        ]

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore", return_value=mock_store), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry", return_value=mock_registry), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner"), \
             mock.patch("ollama_arena.genome.graph.GraphEngine"):
            cmd_genome(args)

        mock_c.print.assert_called()

    def test_show_canonical_not_found(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="show", model="unknown_model")
        mock_c = _mock_console()

        mock_registry = mock.MagicMock()
        mock_registry.match_by_name.return_value = None
        mock_registry.get.return_value = None

        mock_store = mock.MagicMock()
        mock_store.list_local.return_value = []

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore", return_value=mock_store), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry", return_value=mock_registry), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner"), \
             mock.patch("ollama_arena.genome.graph.GraphEngine"):
            cmd_genome(args)

        # should print "not found" message
        mock_c.print.assert_called()

    def test_show_canonical_found_no_local(self):
        from ollama_arena.cli.genome_cmd import cmd_genome
        args = _make_args(genome_cmd="show", model="phi3:mini")
        mock_c = _mock_console()

        mock_registry = mock.MagicMock()
        mock_registry.match_by_name.return_value = "phi3-id"
        mock_registry.get.return_value = {
            "name": "Phi-3", "family": "phi", "org": "Microsoft",
            "architecture": {"params_b": 3.8, "n_layers": 32, "context_length": 4096},
        }
        mock_store = mock.MagicMock()
        mock_store.list_local.return_value = []  # No local match

        with mock.patch("ollama_arena.cli.genome_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.genome.db.GenomeStore", return_value=mock_store), \
             mock.patch("ollama_arena.genome.registry.CanonicalRegistry", return_value=mock_registry), \
             mock.patch("ollama_arena.genome.resolver.GenomeResolver"), \
             mock.patch("ollama_arena.genome.scanner.OllamaScanner"), \
             mock.patch("ollama_arena.genome.graph.GraphEngine"):
            cmd_genome(args)

        mock_c.print.assert_called()
