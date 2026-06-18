# ADR 001: Security Enhancements in Sandbox

## Status
Accepted

## Context
The original sandbox security system in `ollama_arena/sandboxes/security.py` provided AST-based validation but had limited coverage of escape patterns. The system needed enhancement to catch more sophisticated escape attempts while maintaining performance.

## Decision
Implemented a multi-layered security approach:

1. **Suspicious Pattern Detection:** Added regex-based pre-checking for common escape patterns before AST parsing
2. **Expanded Dangerous Modules:** Increased the blocklist of dangerous modules (platform, uuid, hashlib, etc.)
3. **Enhanced Function Blocking:** Added resource exhaustion functions (memoryview, bytearray, etc.)
4. **Layered Validation:** Pattern matching → Size limits → Syntax check → AST validation

### Changes Made

**File:** `ollama_arena/sandboxes/security.py`

1. Added `SUSPICIOUS_PATTERNS` list with regex patterns for common escape attempts
2. Added `check_suspicious_patterns()` function for pre-AST validation
3. Expanded `DANGEROUS_MODULES` with additional modules
4. Expanded `DANGEROUS_FUNCTIONS` with resource-related functions
5. Updated `is_safe_python()` to include pattern pre-check

**File:** `tests/test_suspicious_patterns.py`

1. Created comprehensive test suite for new security features
2. Added 22 test cases covering:
   - Suspicious pattern detection
   - Additional dangerous modules/functions
   - Security layering validation
   - Safe code still passes

## Consequences

### Positive
- **Enhanced Security:** Catches more escape attempts before execution
- **Performance:** Pattern pre-checking is faster than full AST parsing
- **Maintainability:** Layered approach is easier to debug and extend
- **Testing:** Comprehensive test coverage for security features

### Negative
- **Conservative Blocking:** Some legitimate code may be blocked (acceptable trade-off)
- **Pattern Maintenance:** Regex patterns need updates for new escape techniques
- **Performance Overhead:** Additional validation step (minimal impact)

## Alternatives Considered

1. **Machine Learning Detection:** Rejected due to complexity and false positives
2. **Allowlist Approach:** Rejected due to maintenance burden
3. **Docker-Only Security:** Rejected due to need for defense-in-depth

## References
- Original security implementation in `ollama_arena/sandboxes/security.py`
- Test suite in `tests/test_suspicious_patterns.py`
- Python sandbox escape techniques research