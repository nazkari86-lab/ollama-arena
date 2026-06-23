"""Adversarial Dataset Generation for targeted fine-tuning."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple
from collections import defaultdict

log = logging.getLogger("arena.finetuning.adversarial")


class DifficultyLevel(Enum):
    """Difficulty levels for adversarial tasks."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass
class WeaknessTarget:
    """A specific weakness area to target with adversarial tasks."""
    model: str
    category: str
    subcategory: Optional[str]
    win_rate: float
    sample_count: int
    gap_to_target: float  # How far from target win rate
    priority: float  # Computed priority score


@dataclass
class AdversarialTask:
    """An adversarially generated training task."""
    task_id: str
    instruction: str
    category: str
    difficulty: DifficultyLevel
    target_model: str
    metadata: Dict = field(default_factory=dict)


class TaskDifficultyAnalyzer:
    """Analyze task difficulty and model performance."""

    def __init__(self, db_path: str = "arena.db"):
        self.db_path = db_path

    def analyze_difficulty_distribution(
        self,
        category: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze the distribution of task difficulties for a model/category.

        Returns statistics about easy, medium, hard tasks.
        """
        query = """
            SELECT
                d.difficulty,
                COUNT(*) as count,
                AVG(CASE WHEN (m.model_a = ? AND d.outcome = 'a_wins')
                              OR (m.model_b = ? AND d.outcome = 'b_wins')
                              THEN 1.0 ELSE 0.0 END) as win_rate
            FROM task_detail d
            JOIN match_log m ON m.id = d.match_id
            WHERE 1=1
        """
        params = []

        if model:
            params.extend([model, model])
        else:
            # Use placeholder when no model specified
            params.extend(["", ""])

        if category:
            query += " AND d.category = ?"
            params.append(category)

        query += " GROUP BY d.difficulty"

        try:
            with sqlite3.connect(self.db_path) as cx:
                rows = cx.execute(query, params).fetchall()

                distribution = {}
                total_tasks = 0
                for row in rows:
                    difficulty, count, win_rate = row
                    distribution[difficulty or "unknown"] = {
                        "count": count,
                        "win_rate": round(win_rate or 0.0, 3),
                    }
                    total_tasks += count

                # Calculate overall statistics
                avg_win_rate = sum(
                    d["win_rate"] * d["count"] for d in distribution.values()
                ) / total_tasks if total_tasks > 0 else 0.0

                return {
                    "distribution": distribution,
                    "total_tasks": total_tasks,
                    "avg_win_rate": round(avg_win_rate, 3),
                }
        except Exception as e:
            log.error(f"Failed to analyze difficulty distribution: {e}")
            return {"distribution": {}, "total_tasks": 0, "avg_win_rate": 0.0}

    def find_too_easy_tasks(
        self,
        model: str,
        category: Optional[str] = None,
        win_rate_threshold: float = 0.9,
        min_samples: int = 3,
    ) -> List[Dict]:
        """
        Find tasks where the model performs too well (win rate > threshold).

        These are candidates for generating harder variants.
        """
        query = """
            SELECT
                d.task_id,
                d.instruction,
                d.difficulty,
                d.category,
                COUNT(*) as attempts,
                AVG(CASE WHEN (m.model_a = ? AND d.outcome = 'a_wins')
                              OR (m.model_b = ? AND d.outcome = 'b_wins')
                              THEN 1.0 ELSE 0.0 END) as win_rate
            FROM task_detail d
            JOIN match_log m ON m.id = d.match_id
            WHERE m.model_a = ? OR m.model_b = ?
        """
        params: List[Any] = [model, model, model, model]

        if category:
            query += " AND d.category = ?"
            params.append(category)

        query += """
            GROUP BY d.task_id
            HAVING attempts >= ? AND win_rate >= ?
            ORDER BY win_rate DESC, attempts DESC
        """
        params.extend([min_samples, win_rate_threshold])

        try:
            with sqlite3.connect(self.db_path) as cx:
                rows = cx.execute(query, params).fetchall()

                return [
                    {
                        "task_id": row[0],
                        "instruction": row[1],
                        "difficulty": row[2],
                        "category": row[3],
                        "attempts": row[4],
                        "win_rate": round(row[5], 3),
                    }
                    for row in rows
                ]
        except Exception as e:
            log.error(f"Failed to find too-easy tasks: {e}")
            return []

    def identify_weaknesses(
        self,
        model: str,
        min_samples: int = 10,
    ) -> List[WeaknessTarget]:
        """
        Identify category/subcategory weaknesses for a model.

        Returns prioritized list of weakness targets.
        """
        # Get category-level weaknesses
        query = """
            SELECT
                d.category,
                COUNT(*) as total,
                SUM(CASE WHEN (m.model_a = ? AND d.outcome = 'a_wins')
                              OR (m.model_b = ? AND d.outcome = 'b_wins')
                              THEN 1 ELSE 0 END) as wins
            FROM task_detail d
            JOIN match_log m ON m.id = d.match_id
            WHERE m.model_a = ? OR m.model_b = ?
            GROUP BY d.category
            HAVING total >= ?
        """
        params = [model, model, model, model, min_samples]

        weaknesses = []
        try:
            with sqlite3.connect(self.db_path) as cx:
                rows = cx.execute(query, params).fetchall()

                for category, total, wins in rows:
                    win_rate = wins / total if total > 0 else 0.0
                    gap = 0.5 - win_rate  # Gap to 50% baseline

                    if win_rate < 0.5:  # Only consider actual weaknesses
                        priority = gap * (total / min_samples)  # Weight by sample count
                        weaknesses.append(WeaknessTarget(
                            model=model,
                            category=category,
                            subcategory=None,
                            win_rate=round(win_rate, 3),
                            sample_count=total,
                            gap_to_target=round(gap, 3),
                            priority=round(priority, 3),
                        ))

        except Exception as e:
            log.error(f"Failed to identify weaknesses: {e}")

        # Sort by priority (highest first)
        return sorted(weaknesses, key=lambda w: w.priority, reverse=True)


class AdversarialGenerator:
    """Generate adversarial tasks based on model weaknesses."""

    def __init__(
        self,
        db_path: str = "arena.db",
        backend=None,
    ):
        self.db_path = db_path
        self.analyzer = TaskDifficultyAnalyzer(db_path=db_path)
        if backend is None:
            from ..backends.auto import auto_backend
            self.backend = auto_backend()
        else:
            self.backend = backend

    def generate_harder_variant(
        self,
        base_task: Dict,
        difficulty_increase: int = 1,
    ) -> AdversarialTask:
        """
        Generate a harder variant of a base task using AI.

        Args:
            base_task: The base task to make harder
            difficulty_increase: How many levels to increase difficulty

        Returns:
            AdversarialTask with harder instruction
        """
        # Map difficulty levels
        difficulty_order = [DifficultyLevel.EASY, DifficultyLevel.MEDIUM,
                          DifficultyLevel.HARD, DifficultyLevel.EXPERT]

        current_diff = base_task.get("difficulty", "medium").lower()
        try:
            current_idx = next(
                i for i, d in enumerate(difficulty_order)
                if d.value == current_diff
            )
        except StopIteration:
            current_idx = 1  # Default to MEDIUM

        target_idx = min(len(difficulty_order) - 1, current_idx + difficulty_increase)
        target_difficulty = difficulty_order[target_idx]

        # Use AI to generate a harder variant
        prompt = f"""You are tasked with creating a harder variant of the following problem.

Original problem:
{base_task['instruction']}

Category: {base_task['category']}
Current difficulty: {base_task.get('difficulty', 'medium')}

Create a harder version that tests the same core skills but adds:
- Additional complexity or constraints
- More subtle requirements
- Edge cases or corner cases
- Requires deeper reasoning

Output ONLY the new problem instruction, nothing else."""

        generation_ok = False
        try:
            result = self.backend.generate("llama3.1:8b", prompt)  # Use a capable model
            if result.ok and result.text.strip():
                new_instruction = result.text.strip()
                generation_ok = True
            else:
                # Fallback: add complexity manually
                new_instruction = self._add_complexity_manually(base_task['instruction'])
        except Exception as e:
            log.warning(f"AI generation failed, using manual fallback: {e}")
            new_instruction = self._add_complexity_manually(base_task['instruction'])

        # Generate task ID
        task_hash = hashlib.sha256(
            f"{base_task['task_id']}_{target_difficulty.value}".encode()
        ).hexdigest()[:12]
        task_id = f"adv_{task_hash}"

        return AdversarialTask(
            task_id=task_id,
            instruction=new_instruction,
            category=base_task['category'],
            difficulty=target_difficulty,
            target_model="",  # To be filled when used
            metadata={
                "base_task_id": base_task['task_id'],
                "generation_method": "ai" if generation_ok else "manual",
                "difficulty_increase": difficulty_increase,
            },
        )

    def _add_complexity_manually(self, instruction: str) -> str:
        """Manually add complexity to an instruction (fallback)."""
        additions = [
            "\n\nAdditional constraint: Ensure your solution handles edge cases and considers all possible inputs.",
            "\n\nRequirement: Provide a detailed explanation of your approach and verify your solution.",
            "\n\nNote: The solution should be efficient and avoid unnecessary computations.",
            "\n\nMake sure to handle error cases gracefully and provide meaningful error messages.",
        ]
        # Simple hash-based selection for determinism
        import random
        random.seed(hash(instruction))
        return instruction + random.choice(additions)

    def generate_for_weakness(
        self,
        weakness: WeaknessTarget,
        num_tasks: int = 10,
    ) -> List[AdversarialTask]:
        """
        Generate adversarial tasks targeting a specific weakness.

        Args:
            weakness: The weakness target
            num_tasks: Number of tasks to generate

        Returns:
            List of generated adversarial tasks
        """
        # Find related tasks in the category
        query = """
            SELECT DISTINCT task_id, instruction, difficulty
            FROM task_detail
            WHERE category = ?
            LIMIT 50
        """

        base_tasks = []
        try:
            with sqlite3.connect(self.db_path) as cx:
                rows = cx.execute(query, (weakness.category,)).fetchall()
                base_tasks = [
                    {
                        "task_id": row[0],
                        "instruction": row[1],
                        "difficulty": row[2],
                        "category": weakness.category,
                    }
                    for row in rows
                ]
        except Exception as e:
            log.error(f"Failed to fetch base tasks: {e}")

        # Generate harder variants
        tasks = []
        for i in range(min(num_tasks, len(base_tasks))):
            base_task = base_tasks[i]
            variant = self.generate_harder_variant(base_task)
            variant.target_model = weakness.model
            tasks.append(variant)

        log.info(
            f"[adversarial] Generated {len(tasks)} tasks for {weakness.model} "
            f"in category {weakness.category}"
        )
        return tasks

    def generate_adversarial_dataset(
        self,
        model: str,
        num_tasks_per_weakness: int = 10,
        max_weaknesses: int = 3,
    ) -> List[AdversarialTask]:
        """
        Generate a comprehensive adversarial dataset for a model.

        Args:
            model: The target model
            num_tasks_per_weakness: Tasks to generate per weakness area
            max_weaknesses: Maximum number of weakness areas to target

        Returns:
            List of adversarial tasks
        """
        # Identify weaknesses
        weaknesses = self.analyzer.identify_weaknesses(model)
        top_weaknesses = weaknesses[:max_weaknesses]

        all_tasks = []
        for weakness in top_weaknesses:
            tasks = self.generate_for_weakness(
                weakness,
                num_tasks=num_tasks_per_weakness,
            )
            all_tasks.extend(tasks)

        log.info(
            f"[adversarial] Generated {len(all_tasks)} adversarial tasks "
            f"for {model} across {len(top_weaknesses)} weakness areas"
        )
        return all_tasks

    def save_adversarial_tasks(
        self,
        tasks: List[AdversarialTask],
        output_path: str = "data/adversarial_tasks.jsonl",
    ) -> str:
        """Save adversarial tasks to a file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            for task in tasks:
                f.write(json.dumps({
                    "task_id": task.task_id,
                    "instruction": task.instruction,
                    "category": task.category,
                    "difficulty": task.difficulty.value,
                    "target_model": task.target_model,
                    "metadata": task.metadata,
                }, ensure_ascii=False) + "\n")

        log.info(f"[adversarial] Saved {len(tasks)} tasks to {path}")
        return str(path)


def calibrate_difficulty(
    tasks: List[AdversarialTask],
    db_path: str = "arena.db",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calibrate task difficulty based on actual model performance.

    Analyzes how models performed on similar tasks to estimate difficulty.
    """
    if not tasks:
        return {"calibrated": False, "reason": "No tasks to calibrate"}

    # For each task, find similar tasks and check performance
    difficulty_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"wins": 0, "total": 0})

    try:
        with sqlite3.connect(db_path) as cx:
            for task in tasks:
                # Find similar tasks by category
                query = """
                    SELECT outcome
                    FROM task_detail d
                    JOIN match_log m ON m.id = d.match_id
                    WHERE d.category = ?
                """
                params = [task.category]

                if model:
                    query += " AND (m.model_a = ? OR m.model_b = ?)"
                    params.extend([model, model])

                rows = cx.execute(query, params).fetchall()

                for row in rows:
                    outcome = row[0]
                    difficulty_stats[task.difficulty.value]["total"] += 1
                    if outcome in ["a_wins", "b_wins"]:
                        difficulty_stats[task.difficulty.value]["wins"] += 1

    except Exception as e:
        log.error(f"Failed to calibrate difficulty: {e}")
        return {"calibrated": False, "reason": str(e)}

    # Calculate win rates
    calibration = {}
    for diff, stats in difficulty_stats.items():
        win_rate = stats["wins"] / stats["total"] if stats["total"] > 0 else 0.0
        calibration[diff] = {
            "win_rate": round(win_rate, 3),
            "sample_count": stats["total"],
        }

    return {
        "calibrated": True,
        "difficulty_calibration": calibration,
    }


def generate_harder_tasks(
    model: str,
    db_path: str = "arena.db",
    num_tasks: int = 30,
    output_path: Optional[str] = None,
) -> Tuple[List[AdversarialTask], str]:
    """
    Convenience function to generate harder tasks for a model.

    Args:
        model: Target model
        db_path: Arena database path
        num_tasks: Number of tasks to generate
        output_path: Optional output file path

    Returns:
        Tuple of (tasks, output_file_path)
    """
    generator = AdversarialGenerator(db_path=db_path)
    tasks = generator.generate_adversarial_dataset(
        model=model,
        num_tasks_per_weakness=num_tasks // 3,  # Distribute across weaknesses
        max_weaknesses=3,
    )

    if output_path is None:
        output_path = f"data/adversarial_{model.replace(':', '_')}.jsonl"

    output_file = generator.save_adversarial_tasks(tasks, output_path)
    return tasks, output_file
