"""Math tasks — 50 word problems and pure-math questions. All offline, no HF dependency."""

MATH_TASKS = [
    # ── Arithmetic word problems (easy) ──────────────────────────────────────
    {
        "id": "math_001", "difficulty": "easy", "category": "math",
        "instruction": "A baker makes 144 cookies and packs them equally into 12 boxes. How many cookies are in each box? Answer with just the number.",
        "expected_answer": "12", "check": "exact",
    },
    {
        "id": "math_002", "difficulty": "easy", "category": "math",
        "instruction": "A store has 240 items. It sells 75% of them on Monday. How many items remain? Answer with just the number.",
        "expected_answer": "60", "check": "exact",
    },
    {
        "id": "math_003", "difficulty": "easy", "category": "math",
        "instruction": "A train travels at 90 km/h. How far does it travel in 2.5 hours? Answer in km with just the number.",
        "expected_answer": "225", "check": "exact",
    },
    {
        "id": "math_004", "difficulty": "easy", "category": "math",
        "instruction": "If 8 workers can complete a job in 15 days, how many days would 12 workers take? Answer with just the number.",
        "expected_answer": "10", "check": "exact",
    },
    {
        "id": "math_005", "difficulty": "easy", "category": "math",
        "instruction": "A rectangle has length 14 cm and width 8 cm. What is its area in cm²? Answer with just the number.",
        "expected_answer": "112", "check": "exact",
    },
    {
        "id": "math_006", "difficulty": "easy", "category": "math",
        "instruction": "Sarah earns $2,400 per month. She saves 30% of her income. How much does she save each month? Answer in dollars with just the number.",
        "expected_answer": "720", "check": "exact",
    },
    {
        "id": "math_007", "difficulty": "easy", "category": "math",
        "instruction": "A shop buys a jacket for $80 and sells it for $120. What is the profit percentage? Answer with just the number (no % sign).",
        "expected_answer": "50", "check": "exact",
    },
    {
        "id": "math_008", "difficulty": "easy", "category": "math",
        "instruction": "How many prime numbers are between 1 and 30? Answer with just the number.",
        "expected_answer": "10", "check": "exact",
    },
    {
        "id": "math_009", "difficulty": "easy", "category": "math",
        "instruction": "A car uses 8 liters of fuel per 100 km. How many liters does it need to travel 350 km? Answer with just the number.",
        "expected_answer": "28", "check": "exact",
    },
    {
        "id": "math_010", "difficulty": "easy", "category": "math",
        "instruction": "What is the sum of interior angles of a hexagon in degrees? Answer with just the number.",
        "expected_answer": "720", "check": "exact",
    },
    # ── Percentages and ratios (easy–medium) ────────────────────────────────
    {
        "id": "math_011", "difficulty": "easy", "category": "math",
        "instruction": "A price was $200 and increased by 15%. What is the new price? Answer with just the number.",
        "expected_answer": "230", "check": "exact",
    },
    {
        "id": "math_012", "difficulty": "medium", "category": "math",
        "instruction": "In a class of 40 students, the ratio of boys to girls is 3:5. How many girls are in the class? Answer with just the number.",
        "expected_answer": "25", "check": "exact",
    },
    {
        "id": "math_013", "difficulty": "medium", "category": "math",
        "instruction": "A mixture is 40% alcohol. If you add 10 liters of pure alcohol to 40 liters of the mixture, what percentage of the new mixture is alcohol? Answer with just the number.",
        "expected_answer": "48", "check": "exact",
    },
    {
        "id": "math_014", "difficulty": "medium", "category": "math",
        "instruction": "After a 20% discount, a laptop costs $960. What was its original price? Answer with just the number.",
        "expected_answer": "1200", "check": "exact",
    },
    {
        "id": "math_015", "difficulty": "medium", "category": "math",
        "instruction": "A container holds 120 liters. It is 2/3 full. Then 15 liters are removed. How many liters remain? Answer with just the number.",
        "expected_answer": "65", "check": "exact",
    },
    # ── Algebra (medium) ─────────────────────────────────────────────────────
    {
        "id": "math_016", "difficulty": "medium", "category": "math",
        "instruction": "Solve for x: 3x + 17 = 2x + 29. Answer with just the number.",
        "expected_answer": "12", "check": "exact",
    },
    {
        "id": "math_017", "difficulty": "medium", "category": "math",
        "instruction": "Two numbers have a sum of 84 and a difference of 18. What is the larger number? Answer with just the number.",
        "expected_answer": "51", "check": "exact",
    },
    {
        "id": "math_018", "difficulty": "medium", "category": "math",
        "instruction": "A taxi charges $2.50 base fare plus $0.40 per km. A ride costs $10.90. How many km was the ride? Answer with just the number.",
        "expected_answer": "21", "check": "exact",
    },
    {
        "id": "math_019", "difficulty": "medium", "category": "math",
        "instruction": "Find the value: if f(x) = x² - 3x + 2, what is f(5)? Answer with just the number.",
        "expected_answer": "12", "check": "exact",
    },
    {
        "id": "math_020", "difficulty": "medium", "category": "math",
        "instruction": "The sum of three consecutive even numbers is 78. What is the largest of the three? Answer with just the number.",
        "expected_answer": "28", "check": "exact",
    },
    # ── Speed/distance/time (medium) ────────────────────────────────────────
    {
        "id": "math_021", "difficulty": "medium", "category": "math",
        "instruction": "Two cars start from the same point. Car A goes north at 60 km/h, Car B goes south at 40 km/h. After how many hours are they 300 km apart? Answer with just the number.",
        "expected_answer": "3", "check": "exact",
    },
    {
        "id": "math_022", "difficulty": "medium", "category": "math",
        "instruction": "A boat travels 120 km downstream in 4 hours and returns upstream in 6 hours. What is the speed of the current in km/h? Answer with just the number.",
        "expected_answer": "5", "check": "exact",
    },
    {
        "id": "math_023", "difficulty": "medium", "category": "math",
        "instruction": "A cyclist rides at 15 km/h. A runner runs at 10 km/h. The runner starts 2 hours earlier. In how many hours after the cyclist starts will the cyclist catch the runner? Answer with just the number.",
        "expected_answer": "4", "check": "exact",
    },
    # ── Geometry (medium–hard) ──────────────────────────────────────────────
    {
        "id": "math_024", "difficulty": "medium", "category": "math",
        "instruction": "A circle has a circumference of 31.4 cm. What is its area in cm²? Use π ≈ 3.14. Answer with just the number.",
        "expected_answer": "78.5", "check": "numeric_approx", "tolerance": 1,
    },
    {
        "id": "math_025", "difficulty": "medium", "category": "math",
        "instruction": "A right triangle has legs of length 9 and 12. What is the length of the hypotenuse? Answer with just the number.",
        "expected_answer": "15", "check": "exact",
    },
    {
        "id": "math_026", "difficulty": "medium", "category": "math",
        "instruction": "A sphere has radius 3. What is its volume? Use π ≈ 3.14159. Round to 1 decimal. Answer with just the number.",
        "expected_answer": "113.1", "check": "numeric_approx", "tolerance": 1,
    },
    {
        "id": "math_027", "difficulty": "hard", "category": "math",
        "instruction": "A cone has base radius 5 and height 12. What is the total surface area (base + lateral)? Use π ≈ 3.14159. Round to nearest integer. Answer with just the number.",
        "expected_answer": "283", "check": "numeric_approx", "tolerance": 2,
    },
    # ── Combinatorics and probability (hard) ─────────────────────────────────
    {
        "id": "math_028", "difficulty": "hard", "category": "math",
        "instruction": "In how many ways can 5 people be arranged in a row? Answer with just the number.",
        "expected_answer": "120", "check": "exact",
    },
    {
        "id": "math_029", "difficulty": "hard", "category": "math",
        "instruction": "A committee of 3 people is chosen from 8 candidates. How many different committees are possible? Answer with just the number.",
        "expected_answer": "56", "check": "exact",
    },
    {
        "id": "math_030", "difficulty": "hard", "category": "math",
        "instruction": "A bag has 4 red, 3 blue, and 5 green balls. What is the probability of drawing a red or blue ball in one draw? Express as a fraction in lowest terms.",
        "expected_answer": "7/12", "check": "exact",
    },
    {
        "id": "math_031", "difficulty": "hard", "category": "math",
        "instruction": "Two dice are rolled. What is the probability that the sum is exactly 8? Express as a fraction in lowest terms.",
        "expected_answer": "5/36", "check": "exact",
    },
    {
        "id": "math_032", "difficulty": "hard", "category": "math",
        "instruction": "How many 4-digit numbers can be formed from digits 1–9 (no repetition) that are divisible by 5? Answer with just the number.",
        "expected_answer": "168", "check": "exact",
    },
    # ── Number theory (hard) ─────────────────────────────────────────────────
    {
        "id": "math_033", "difficulty": "hard", "category": "math",
        "instruction": "What is the LCM of 12, 18, and 24? Answer with just the number.",
        "expected_answer": "72", "check": "exact",
    },
    {
        "id": "math_034", "difficulty": "hard", "category": "math",
        "instruction": "What is the GCD of 252 and 105? Answer with just the number.",
        "expected_answer": "21", "check": "exact",
    },
    {
        "id": "math_035", "difficulty": "hard", "category": "math",
        "instruction": "What is 2^10? Answer with just the number.",
        "expected_answer": "1024", "check": "exact",
    },
    {
        "id": "math_036", "difficulty": "hard", "category": "math",
        "instruction": "Find the sum of the arithmetic series: 3 + 7 + 11 + ... + 99. Answer with just the number.",
        "expected_answer": "1275", "check": "exact",
    },
    {
        "id": "math_037", "difficulty": "hard", "category": "math",
        "instruction": "A geometric series has first term 2 and common ratio 3. What is the sum of the first 5 terms? Answer with just the number.",
        "expected_answer": "242", "check": "exact",
    },
    # ── Statistics (medium–hard) ─────────────────────────────────────────────
    {
        "id": "math_038", "difficulty": "medium", "category": "math",
        "instruction": "Find the mean of: 4, 7, 13, 2, 9. Answer with just the number.",
        "expected_answer": "7", "check": "exact",
    },
    {
        "id": "math_039", "difficulty": "medium", "category": "math",
        "instruction": "Find the median of: 3, 1, 9, 7, 5, 11, 2. Answer with just the number.",
        "expected_answer": "5", "check": "exact",
    },
    {
        "id": "math_040", "difficulty": "hard", "category": "math",
        "instruction": "The mean of 5 numbers is 12. Four of the numbers are 8, 15, 10, and 14. What is the fifth number? Answer with just the number.",
        "expected_answer": "13", "check": "exact",
    },
    # ── Applied / finance (medium) ───────────────────────────────────────────
    {
        "id": "math_041", "difficulty": "medium", "category": "math",
        "instruction": "$1,000 is invested at 5% simple interest per year. How much interest is earned after 4 years? Answer in dollars with just the number.",
        "expected_answer": "200", "check": "exact",
    },
    {
        "id": "math_042", "difficulty": "hard", "category": "math",
        "instruction": "$1,000 is invested at 10% annual compound interest. What is the value after 3 years? Round to nearest dollar. Answer with just the number.",
        "expected_answer": "1331", "check": "numeric_approx", "tolerance": 1,
    },
    {
        "id": "math_043", "difficulty": "medium", "category": "math",
        "instruction": "A product was $150 and is now on sale for $120. What is the percentage discount? Answer with just the number.",
        "expected_answer": "20", "check": "exact",
    },
    {
        "id": "math_044", "difficulty": "medium", "category": "math",
        "instruction": "Three people invest in a business: A puts in $3,000, B puts in $4,000, C puts in $5,000. The profit is $6,000. How much does B receive? Answer with just the number.",
        "expected_answer": "2000", "check": "exact",
    },
    # ── Logic / puzzle (medium–hard) ────────────────────────────────────────
    {
        "id": "math_045", "difficulty": "medium", "category": "math",
        "instruction": "If today is Wednesday, what day of the week will it be 100 days from now? Answer with just the day name.",
        "expected_answer": "Friday", "check": "exact",
    },
    {
        "id": "math_046", "difficulty": "hard", "category": "math",
        "instruction": "A clock shows 3:15. What is the angle between the hour and minute hands in degrees? Answer with just the number.",
        "expected_answer": "7.5", "check": "numeric_approx", "tolerance": 0.5,
    },
    {
        "id": "math_047", "difficulty": "hard", "category": "math",
        "instruction": "What is the 10th term of the Fibonacci sequence (starting 1, 1, 2, 3, 5, ...)? Answer with just the number.",
        "expected_answer": "55", "check": "exact",
    },
    {
        "id": "math_048", "difficulty": "hard", "category": "math",
        "instruction": "If log₂(x) = 5, what is x? Answer with just the number.",
        "expected_answer": "32", "check": "exact",
    },
    {
        "id": "math_049", "difficulty": "hard", "category": "math",
        "instruction": "Solve: x² - 5x + 6 = 0. Give both solutions separated by a comma, smaller first.",
        "expected_answer": "2, 3", "check": "contains_all",
        "check_items": ["2", "3"],
    },
    {
        "id": "math_050", "difficulty": "hard", "category": "math",
        "instruction": "In a room of 23 people, what is the probability that at least two share a birthday? Give a rough percentage. Is it above or below 50%? Answer 'above' or 'below'.",
        "expected_answer": "above", "check": "contains",
    },
]
