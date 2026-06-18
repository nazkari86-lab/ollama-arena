import re
from functools import lru_cache

# Code-block extraction - compiled once at module load
_FENCED = re.compile(r"```(?:python|py|javascript|js|typescript|ts|rust|rs|go|cpp|c\+\+|bash|sh)?\s*(.*?)```",
                     re.DOTALL | re.IGNORECASE)

# Language-specific prefixes for fallback detection
_PREFIXES = {
    "python": ("import ", "from ", "def ", "class ", "async ", "#!", "if ", "@"),
    "javascript": ("import ", "const ", "let ", "var ", "function ", "class ", "async "),
    "typescript": ("import ", "const ", "let ", "var ", "function ", "class ", "async "),
    "rust": ("use ", "fn ", "pub ", "struct ", "impl ", "mod ", "#["),
    "go": ("package ", "import ", "func "),
    "cpp": ("#include", "int ", "void ", "auto ", "class ", "namespace ", "using "),
}


@lru_cache(maxsize=512)
def extract_code(text: str, language: str = "python") -> str:
    """Pull the first fenced code block; fall back to raw text if it
    already looks like source in the requested language.

    Uses LRU cache for performance when extracting same text repeatedly.
    """
    m = _FENCED.search(text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    prefixes = _PREFIXES.get(language, _PREFIXES["python"])
    if any(stripped.startswith(p) for p in prefixes):
        return stripped
    return stripped


def clean_whitespace(text: str) -> str:
    """Normalize whitespace in text - collapse multiple spaces and trim."""
    return " ".join(text.split())


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_json_loads(json_string: str, default: str = "{}") -> dict:
    """Safely parse JSON string, returning default on failure."""
    try:
        import json
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return json.loads(default) if isinstance(default, str) else default
