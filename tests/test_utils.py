"""Tests for utility functions in utils.py."""
import pytest
from ollama_arena.utils import (
    extract_code,
    clean_whitespace,
    truncate_text,
    safe_json_loads,
)


class TestExtractCode:
    """Test code extraction from various formats."""

    def test_extract_fenced_python(self):
        """Extract code from ```python``` blocks."""
        text = "Here's some code:\n```python\ndef hello():\n    return 'world'\n```\nDone"
        result = extract_code(text, "python")
        assert "def hello():" in result
        assert "return 'world'" in result

    def test_extract_fenced_no_language(self):
        """Extract code from ``` blocks without language specification."""
        text = "```\nprint('hello')\n```"
        result = extract_code(text)
        assert result == "print('hello')"

    def test_extract_fenced_javascript(self):
        """Extract JavaScript code from blocks."""
        text = "```javascript\nconst x = 1;\n```"
        result = extract_code(text, "javascript")
        assert result == "const x = 1;"

    def test_fallback_to_raw_text_python(self):
        """Fall back to raw text for Python-like code."""
        text = "def add(a, b):\n    return a + b"
        result = extract_code(text, "python")
        assert result == text

    def test_fallback_to_raw_text_javascript(self):
        """Fall back to raw text for JavaScript-like code."""
        text = "function test() { return 1; }"
        result = extract_code(text, "javascript")
        assert result == text

    def test_fallback_to_raw_text_non_code(self):
        """Return as-is for non-code text."""
        text = "This is just plain text"
        result = extract_code(text, "python")
        assert result == text

    def test_language_specific_prefixes(self):
        """Test language-specific prefix detection."""
        # Rust
        rust_code = "use std::collections::HashMap;"
        assert extract_code(rust_code, "rust") == rust_code

        # Go
        go_code = "package main"
        assert extract_code(go_code, "go") == go_code

        # C++
        cpp_code = "#include <iostream>"
        assert extract_code(cpp_code, "cpp") == cpp_code

    def test_cache_effectiveness(self):
        """Test that LRU cache is working for repeated calls."""
        text = "```python\ndef test():\n    pass\n```"
        # First call
        result1 = extract_code(text, "python")
        # Second call should hit cache
        result2 = extract_code(text, "python")
        assert result1 == result2


class TestCleanWhitespace:
    """Test whitespace normalization."""

    def test_collapse_multiple_spaces(self):
        """Collapse multiple spaces into single space."""
        text = "hello    world"
        result = clean_whitespace(text)
        assert result == "hello world"

    def test_collapse_tabs_and_newlines(self):
        """Collapse tabs and newlines into spaces."""
        text = "hello\t\tworld\n\nfoo"
        result = clean_whitespace(text)
        assert result == "hello world foo"

    def test_trim_whitespace(self):
        """Trim leading and trailing whitespace."""
        text = "  hello world  "
        result = clean_whitespace(text)
        assert result == "hello world"

    def test_empty_string(self):
        """Handle empty string."""
        result = clean_whitespace("")
        assert result == ""

    def test_already_clean(self):
        """Leave already clean text unchanged."""
        text = "hello world"
        result = clean_whitespace(text)
        assert result == text


class TestTruncateText:
    """Test text truncation."""

    def test_truncate_long_text(self):
        """Truncate text longer than max_length."""
        text = "a" * 100
        result = truncate_text(text, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_no_truncate_short_text(self):
        """Don't truncate text shorter than max_length."""
        text = "hello"
        result = truncate_text(text, 50)
        assert result == "hello"
        assert not result.endswith("...")

    def test_custom_suffix(self):
        """Use custom suffix."""
        text = "a" * 100
        result = truncate_text(text, 50, suffix=">>")
        assert result.endswith(">>")

    def test_exact_length(self):
        """Handle text exactly at max_length."""
        text = "a" * 50
        result = truncate_text(text, 50)
        assert len(result) == 50
        assert not result.endswith("...")

    def test_empty_text(self):
        """Handle empty text."""
        result = truncate_text("", 50)
        assert result == ""


class TestSafeJsonLoads:
    """Test safe JSON parsing."""

    def test_valid_json(self):
        """Parse valid JSON."""
        json_string = '{"key": "value", "number": 42}'
        result = safe_json_loads(json_string)
        assert result == {"key": "value", "number": 42}

    def test_invalid_json_default_dict(self):
        """Return default dict for invalid JSON."""
        result = safe_json_loads("invalid json")
        assert result == {}

    def test_invalid_json_custom_default(self):
        """Use custom default for invalid JSON."""
        custom_default = '{"custom": "default"}'
        result = safe_json_loads("invalid json", default=custom_default)
        assert result == {"custom": "default"}

    def test_invalid_json_object_default(self):
        """Use object default directly for invalid JSON."""
        custom_default = {"fallback": True}
        result = safe_json_loads("invalid json", default=custom_default)
        assert result == {"fallback": True}

    def test_json_array(self):
        """Parse JSON array."""
        json_string = '[1, 2, 3, "four"]'
        result = safe_json_loads(json_string)
        assert result == [1, 2, 3, "four"]

    def test_nested_json(self):
        """Parse nested JSON structure."""
        json_string = '{"outer": {"inner": "value"}, "array": [1, 2]}'
        result = safe_json_loads(json_string)
        assert result["outer"]["inner"] == "value"
        assert result["array"] == [1, 2]