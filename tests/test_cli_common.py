"""Tests for CLI common utilities."""
import pytest
from ollama_arena.cli.common import (
    _trunc,
    _wrap,
    _outcome_icon,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_step,
)


class TestTrunc:
    """Test text truncation function."""

    def test_trunc_short_text(self):
        """Don't truncate short text."""
        text = "hello world"
        result = _trunc(text, 50)
        assert result == text

    def test_trunc_long_text(self):
        """Truncate long text and add ellipsis."""
        text = "a" * 150
        result = _trunc(text, 100)
        assert len(result) == 101  # 100 chars + "…"
        assert result.endswith("…")

    def test_trunc_exact_length(self):
        """Handle text exactly at truncation length."""
        text = "a" * 120
        result = _trunc(text, 120)
        assert result == text
        assert not result.endswith("…")

    def test_trunc_whitespace(self):
        """Strip whitespace before truncation."""
        text = "  hello world  "
        result = _trunc(text, 10)
        assert result == "hello worl…"  # 9 chars from "hello world" + "…"

    def test_trunc_empty_string(self):
        """Handle empty string."""
        result = _trunc("", 100)
        assert result == ""


class TestWrap:
    """Test text wrapping function."""

    def test_wrap_short_text(self):
        """Wrap short text without truncation."""
        text = "hello world"
        result = _wrap(text, 90)
        assert result == text

    def test_wrap_long_text(self):
        """Wrap and truncate long text."""
        text = "a" * 150
        result = _wrap(text, 50)
        assert len(result) <= 53  # 50 + "…"

    def test_wrap_multiline(self):
        """Wrap multiline text."""
        text = "line1\nline2\nline3"
        result = _wrap(text, 10)
        assert "line1" in result
        assert "line2" in result

    def test_wrap_many_lines(self):
        """Limit number of lines shown."""
        lines = [f"line{i}" for i in range(10)]
        text = "\n".join(lines)
        result = _wrap(text, 90)
        assert "more lines" in result

    def test_wrap_empty_string(self):
        """Handle empty string."""
        result = _wrap("", 90)
        assert "empty" in result


class TestOutcomeIcon:
    """Test outcome icon function."""

    def test_a_wins_icon(self):
        """Return green checkmark for A wins."""
        icon = _outcome_icon("a_wins")
        assert "[green" in icon
        assert "✓" in icon

    def test_b_wins_icon(self):
        """Return red checkmark for B wins."""
        icon = _outcome_icon("b_wins")
        assert "[red" in icon
        assert "✓" in icon

    def test_draw_icon(self):
        """Return dim equals for draw."""
        icon = _outcome_icon("draw")
        assert "[dim" in icon
        assert "=" in icon


class TestPrintFunctions:
    """Test print utility functions."""

    def test_print_success(self, capsys):
        """Print success message."""
        print_success("Operation completed")
        captured = capsys.readouterr()
        assert "✓" in captured.out or "completed" in captured.out

    def test_print_error(self, capsys):
        """Print error message."""
        print_error("Operation failed")
        captured = capsys.readouterr()
        assert "✗" in captured.out or "failed" in captured.out

    def test_print_warning(self, capsys):
        """Print warning message."""
        print_warning("Warning message")
        captured = capsys.readouterr()
        assert "⚠" in captured.out or "Warning" in captured.out

    def test_print_info(self, capsys):
        """Print info message."""
        print_info("Info message")
        captured = capsys.readouterr()
        assert "ℹ" in captured.out or "Info" in captured.out

    def test_print_step(self, capsys):
        """Print step indicator."""
        print_step(2, 5, "Processing data")
        captured = capsys.readouterr()
        assert "Step 2/5" in captured.out
        assert "Processing data" in captured.out


class TestContextManagers:
    """Test context managers for progress tracking."""

    def test_progress_bar_context(self):
        """Test progress bar context manager works."""
        from ollama_arena.cli.common import progress_bar

        with progress_bar("Testing", total=10) as (progress, task):
            # Should complete without error and return progress/task objects
            assert progress is not None or task is not None

    def test_spinner_context(self):
        """Test spinner context manager works."""
        from ollama_arena.cli.common import spinner

        with spinner("Processing"):
            pass  # Should complete without error


class TestConfirm:
    """Test confirmation prompt."""

    def test_confirm_function_exists(self):
        """Test that confirm function exists."""
        from ollama_arena.cli.common import confirm

        assert callable(confirm)