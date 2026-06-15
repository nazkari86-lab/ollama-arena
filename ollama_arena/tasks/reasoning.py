"""
Reasoning Benchmarks — 15 logic/math/algorithm tasks.
Scored by: exact match or numeric tolerance check.
"""

REASONING_TASKS = [
    # ── Logic (5) ────────────────────────────────────────────────────────────
    {
        "id": "reas_001", "difficulty": "easy", "category": "logic",
        "instruction": "If all Bloops are Razzies, and all Razzies are Lazzies, are all Bloops definitely Lazzies? Answer with exactly: 'yes' or 'no', then one sentence explanation.",
        "expected_answer": "yes",
        "check": "exact_prefix",
    },
    {
        "id": "reas_002", "difficulty": "medium", "category": "logic",
        "instruction": "You have 12 balls, one is heavier. You have a balance scale and 3 weighings. Describe the minimum strategy to find the heavy ball. How many balls can you test with N weighings? Give the formula.",
        "expected_answer": "3^N",
        "check": "contains",
    },
    {
        "id": "reas_003", "difficulty": "hard", "category": "logic",
        "instruction": "100 prisoners are each assigned a number 1-100. A room has 100 boxes numbered 1-100, each containing a random prisoner number. Each prisoner may open 50 boxes. They succeed if ALL find their number. What strategy gives the highest success probability, and what is that probability approximately?",
        "expected_answer": "31",  # ~31% with cycle-following strategy
        "check": "numeric_approx",
        "tolerance": 5,
    },
    {
        "id": "reas_004", "difficulty": "medium", "category": "logic",
        "instruction": "A bat and a ball cost $1.10 total. The bat costs $1.00 more than the ball. How much does the ball cost? Give the exact answer in cents.",
        "expected_answer": "5",
        "check": "exact",
    },
    {
        "id": "reas_005", "difficulty": "hard", "category": "logic",
        "instruction": "In a village, the barber shaves all men who do not shave themselves, and only those men. Does the barber shave himself? Answer with: 'paradox' and explain Russell's paradox connection in 2 sentences.",
        "expected_answer": "paradox",
        "check": "exact_prefix",
    },
    # ── Mathematics (5) ──────────────────────────────────────────────────────
    {
        "id": "reas_006", "difficulty": "easy", "category": "math",
        "instruction": "What is the sum of all integers from 1 to 1000? Provide only the numeric answer.",
        "expected_answer": "500500",
        "check": "exact",
    },
    {
        "id": "reas_007", "difficulty": "medium", "category": "math",
        "instruction": "How many trailing zeros does 100! (100 factorial) have? Provide only the numeric answer.",
        "expected_answer": "24",
        "check": "exact",
    },
    {
        "id": "reas_008", "difficulty": "medium", "category": "math",
        "instruction": "A coin is flipped 10 times. What is the probability of getting exactly 7 heads? Give the answer as a fraction in lowest terms.",
        "expected_answer": "15/128",
        "check": "exact",
    },
    {
        "id": "reas_009", "difficulty": "hard", "category": "math",
        "instruction": "What is the smallest positive integer n such that n! is divisible by 10^10? Provide only the numeric answer.",
        "expected_answer": "25",
        "check": "exact",
    },
    {
        "id": "reas_010", "difficulty": "medium", "category": "math",
        "instruction": "Two trains start 300km apart and approach each other. Train A travels at 80 km/h, Train B at 70 km/h. A fly starts at Train A and flies at 150 km/h back and forth between the trains until they collide. How far does the fly travel? Answer in km.",
        "expected_answer": "150",
        "check": "exact",
    },
    # ── Algorithm Analysis (5) ───────────────────────────────────────────────
    {
        "id": "reas_011", "difficulty": "easy", "category": "algorithms",
        "instruction": "What is the time complexity of finding the k-th smallest element in an unsorted array using a min-heap? Give only the Big-O notation (e.g., O(n log k)).",
        "expected_answer": "O(n log k)",
        "check": "exact_normalized",
    },
    {
        "id": "reas_012", "difficulty": "medium", "category": "algorithms",
        "instruction": "You have an array of n integers. You need to find two numbers that sum to a target T. Compare three approaches: (1) brute force, (2) sorting + two pointers, (3) hash set. Give their time complexities in order, separated by commas.",
        "expected_answer": "O(n^2), O(n log n), O(n)",
        "check": "contains_all",
        "check_items": ["O(n^2)", "O(n log n)", "O(n)"],
    },
    {
        "id": "reas_013", "difficulty": "hard", "category": "algorithms",
        "instruction": "Explain why QuickSort's worst-case time complexity is O(n^2) but its average case is O(n log n). What pivot selection strategy makes worst-case extremely unlikely? Name the specific technique.",
        "expected_answer": "random pivot",
        "check": "contains_any",
        "check_items": ["random pivot", "randomized quicksort", "random selection"],
    },
    {
        "id": "reas_014", "difficulty": "medium", "category": "algorithms",
        "instruction": "Given a DAG with N nodes and E edges, what is the time complexity of topological sort using Kahn's algorithm (BFS-based)? Give only the Big-O notation.",
        "expected_answer": "O(V+E)",
        "check": "exact_normalized",
    },
    {
        "id": "reas_015", "difficulty": "hard", "category": "algorithms",
        "instruction": "You have a 32-bit signed integer. Without converting to string, how do you detect if it's a palindrome? Describe the approach in pseudocode and give the space complexity.",
        "expected_answer": "O(1)",
        "check": "contains",
    },
]

def evaluate_answer(task: dict, model_answer: str) -> float:
    """Score a model's answer against expected. Returns 0.0–1.0."""
    model_lower = model_answer.strip().lower()
    expected = str(task["expected_answer"]).lower()
    check = task.get("check", "exact")

    if check == "exact":
        return 1.0 if expected in model_lower else 0.0

    elif check == "exact_prefix":
        return 1.0 if model_lower.startswith(expected) else 0.0

    elif check == "contains":
        return 1.0 if expected in model_lower else 0.0

    elif check == "contains_any":
        items = [x.lower() for x in task.get("check_items", [expected])]
        return 1.0 if any(item in model_lower for item in items) else 0.0

    elif check == "contains_all":
        items = [x.lower() for x in task.get("check_items", [expected])]
        return 1.0 if all(item in model_lower for item in items) else 0.0

    elif check == "exact_normalized":
        # Remove spaces and compare
        return 1.0 if expected.replace(" ", "") in model_lower.replace(" ", "") else 0.0

    elif check == "numeric_approx":
        import re
        nums = re.findall(r'\d+\.?\d*', model_lower)
        if not nums:
            return 0.0
        tolerance = task.get("tolerance", 2)
        exp_val = float(expected)
        for n in nums:
            if abs(float(n) - exp_val) <= tolerance:
                return 1.0
        return 0.0

    return 0.0

