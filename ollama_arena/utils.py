import re

# Code-block extraction
_FENCED = re.compile(r"```(?:python|py|javascript|js|typescript|ts|rust|rs|go|cpp|c\+\+|bash|sh)?\s*(.*?)```",
                     re.DOTALL | re.IGNORECASE)


def extract_code(text: str, language: str = "python") -> str:
    """Pull the first fenced code block; fall back to raw text if it
    already looks like source in the requested language."""
    m = _FENCED.search(text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    py_prefixes = ("import ", "from ", "def ", "class ", "async ", "#!", "if ", "@")
    js_prefixes = ("import ", "const ", "let ", "var ", "function ", "class ", "async ")
    rust_prefixes = ("use ", "fn ", "pub ", "struct ", "impl ", "mod ", "#[")
    go_prefixes = ("package ", "import ", "func ")
    cpp_prefixes = ("#include", "int ", "void ", "auto ", "class ", "namespace ", "using ")
    prefix_map = {
        "python": py_prefixes, "javascript": js_prefixes, "typescript": js_prefixes,
        "rust": rust_prefixes, "go": go_prefixes, "cpp": cpp_prefixes,
    }
    prefixes = prefix_map.get(language, py_prefixes)
    if any(stripped.startswith(p) for p in prefixes):
        return stripped
    return stripped
