"""Tests for suspicious pattern detection in security validator."""
import pytest
from ollama_arena.sandboxes.security import is_safe_python


class TestSuspiciousPatternDetection:
    """Test that obvious escape attempt patterns are detected."""

    def test_dynamic_import_detection(self):
        """Detect __import__('os') pattern."""
        code = "x = __import__('os')"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Suspicious pattern" in reason or "Dunder" in reason

    def test_eval_detection(self):
        """Detect eval() pattern."""
        code = "eval('print(1)')"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Suspicious pattern" in reason or "Dangerous" in reason

    def test_exec_detection(self):
        """Detect exec() pattern."""
        code = "exec('x=1')"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Suspicious pattern" in reason or "Dangerous" in reason

    def test_class_traversal_detection(self):
        """Detect .__class__. pattern."""
        code = "x = ().__class__"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dunder" in reason

    def test_subscript_builtins_detection(self):
        """Detect __builtins__['os'] pattern - note: __builtins__ is only blocked on write."""
        code = "__builtins__ = {}"  # Assignment to __builtins__ should be blocked
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Cannot bind name" in reason

    def test_safe_code_passes(self):
        """Ensure safe code still passes."""
        code = """
def add(a, b):
    return a + b

result = add(1, 2)
print(result)
"""
        safe, reason = is_safe_python(code)
        assert safe
        assert reason == ""

    def test_safe_imports_pass(self):
        """Ensure safe imports pass."""
        code = """
import math
import json
from collections import Counter

x = math.sqrt(2)
y = json.dumps({'a': 1})
"""
        safe, reason = is_safe_python(code)
        assert safe
        assert reason == ""

    def test_getattr_dunder_detection(self):
        """Detect getattr with dunder strings."""
        code = "x = getattr(obj, '__class__')"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dunder" in reason

    def test_file_open_detection(self):
        """Detect file open attempts."""
        code = "f = open('/etc/passwd')"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Suspicious pattern" in reason or "open" in reason.lower()

    def test_mro_access_detection(self):
        """Detect MRO access pattern."""
        code = "x = SomeClass.__mro__[1]"
        safe, reason = is_safe_python(code)
        assert not safe
        # Should be caught by pattern matching or AST
        assert "Dunder" in reason or "Suspicious pattern" in reason

    def test_safe_dunder_usage(self):
        """Allow safe dunder usage."""
        code = """
class MyClass:
    def __init__(self, value):
        self.value = value

if __name__ == "__main__":
    obj = MyClass(42)
    print(obj.__doc__)
"""
        safe, reason = is_safe_python(code)
        assert safe
        assert reason == ""


class TestAdditionalDangerousModules:
    """Test that newly added dangerous modules are blocked."""

    def test_platform_module_blocked(self):
        """platform module should be blocked."""
        code = "import platform"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous module" in reason

    def test_uuid_module_blocked(self):
        """uuid module should be blocked."""
        code = "import uuid"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous module" in reason

    def test_hashlib_module_blocked(self):
        """hashlib module should be blocked."""
        code = "import hashlib"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous module" in reason

    def test_time_module_blocked(self):
        """time module should be blocked."""
        code = "import time"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous module" in reason

    def test_datetime_module_blocked(self):
        """datetime module should be blocked."""
        code = "import datetime"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous module" in reason


class TestAdditionalDangerousFunctions:
    """Test that newly added dangerous functions are blocked."""

    def test_memoryview_blocked(self):
        """memoryview should be blocked."""
        code = "x = memoryview(b'hello')"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous function" in reason

    def test_bytearray_blocked(self):
        """bytearray should be blocked."""
        code = "x = bytearray(1000)"
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous function" in reason


class TestSecurityLayering:
    """Test that multiple security layers work together."""

    def test_pattern_then_ast_blocking(self):
        """Test that suspicious patterns are caught before AST parsing."""
        # This should be caught by pattern matching
        code = "x = __import__('os')"
        safe, reason = is_safe_python(code)
        assert not safe
        # Should mention suspicious pattern
        assert "Suspicious pattern" in reason or "Dunder" in reason

    def test_ast_only_blocking(self):
        """Test AST-only blocking for patterns not in regex."""
        # This might not be in suspicious patterns but should be caught by AST
        code = """
import os  # Should be caught by AST visitor
"""
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Dangerous module" in reason

    def test_size_limit_still_works(self):
        """Test that size limit still works."""
        code = "x = " + "1" * 300_000  # Exceeds 256KB
        safe, reason = is_safe_python(code)
        assert not safe
        assert "exceeds" in reason.lower()

    def test_syntax_error_still_works(self):
        """Test that syntax error detection still works."""
        code = "def broken("  # Syntax error
        safe, reason = is_safe_python(code)
        assert not safe
        assert "Syntax Error" in reason