"""Built-in benchmark tasks."""
from .coding              import CODING_TASKS
from .reasoning           import REASONING_TASKS
from .security            import SECURITY_TASKS
from .planning            import PLANNING_TASKS
from .inspection          import INSPECTION_TASKS
from .coding_multilang    import (
    CODING_JS_TASKS, CODING_TS_TASKS, CODING_RUST_TASKS,
    CODING_GO_TASKS, CODING_CPP_TASKS, ALL_MULTILANG_TASKS,
)

# Combine Python + multi-language coding tasks under the same category.
_ALL_CODING = CODING_TASKS + ALL_MULTILANG_TASKS

ALL_TASKS: dict[str, list] = {
    "coding":     _ALL_CODING,
    "reasoning":  REASONING_TASKS,
    "security":   SECURITY_TASKS,
    "planning":   PLANNING_TASKS,
    "inspection": INSPECTION_TASKS,
}


def get_tasks(category: str | None = None, limit: int | None = None,
              difficulty: str | None = None,
              language: str | None = None) -> list[dict]:
    """
    Fetch built-in tasks. Filters: category, difficulty, language.
    """
    if category and category != "all":
        tasks = list(ALL_TASKS.get(category, []))
    else:
        tasks = []
        for v in ALL_TASKS.values():
            tasks.extend(v)
    if difficulty:
        tasks = [t for t in tasks if t.get("difficulty") == difficulty]
    if language:
        tasks = [t for t in tasks if t.get("language", "python") == language]
    return tasks[:limit] if limit else tasks


def list_categories() -> list[str]:
    return list(ALL_TASKS.keys())


def list_languages() -> list[str]:
    langs: set[str] = set()
    for v in ALL_TASKS.values():
        for t in v:
            langs.add(t.get("language", "python"))
    return sorted(langs)


def task_stats() -> dict[str, int]:
    return {cat: len(tasks) for cat, tasks in ALL_TASKS.items()}
