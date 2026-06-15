from .coding import CODING_TASKS
from .reasoning import REASONING_TASKS
from .security import SECURITY_TASKS
from .planning import PLANNING_TASKS
from .inspection import INSPECTION_TASKS

ALL_TASKS: dict[str, list] = {
    "coding":     CODING_TASKS,
    "reasoning":  REASONING_TASKS,
    "security":   SECURITY_TASKS,
    "planning":   PLANNING_TASKS,
    "inspection": INSPECTION_TASKS,
}


def get_tasks(category: str | None = None, limit: int | None = None,
              difficulty: str | None = None) -> list[dict]:
    tasks = []
    if category:
        tasks = list(ALL_TASKS.get(category, []))
    else:
        for v in ALL_TASKS.values():
            tasks.extend(v)
    if difficulty:
        tasks = [t for t in tasks if t.get("difficulty") == difficulty]
    return tasks[:limit] if limit else tasks


def list_categories() -> list[str]:
    return list(ALL_TASKS.keys())


def task_stats() -> dict:
    return {cat: len(tasks) for cat, tasks in ALL_TASKS.items()}
