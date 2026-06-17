"""Knowledge tasks — 50 offline trivia and factual questions across science, history, geography, and CS."""

KNOWLEDGE_TASKS = [
    # ── Science — Physics ─────────────────────────────────────────────────────
    {
        "id": "know_001", "difficulty": "easy", "category": "knowledge",
        "instruction": "What is the speed of light in a vacuum in km/s? Answer with just the number.",
        "expected_answer": "300000", "check": "contains",
    },
    {
        "id": "know_002", "difficulty": "easy", "category": "knowledge",
        "instruction": "What unit measures electrical resistance? Answer with just the unit name.",
        "expected_answer": "ohm", "check": "contains",
    },
    {
        "id": "know_003", "difficulty": "medium", "category": "knowledge",
        "instruction": "What is Newton's second law of motion? Answer in one sentence.",
        "expected_answer": "force", "check": "contains",
    },
    {
        "id": "know_004", "difficulty": "medium", "category": "knowledge",
        "instruction": "What particle has no electric charge and is found in the nucleus of an atom? Answer with just the particle name.",
        "expected_answer": "neutron", "check": "contains",
    },
    {
        "id": "know_005", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the SI unit of frequency? Answer with just the unit name.",
        "expected_answer": "hertz", "check": "contains",
    },
    # ── Science — Chemistry ───────────────────────────────────────────────────
    {
        "id": "know_006", "difficulty": "easy", "category": "knowledge",
        "instruction": "What is the chemical symbol for gold? Answer with just the symbol.",
        "expected_answer": "Au", "check": "exact",
    },
    {
        "id": "know_007", "difficulty": "easy", "category": "knowledge",
        "instruction": "How many elements are in the periodic table (as of 2023)? Answer with just the number.",
        "expected_answer": "118", "check": "exact",
    },
    {
        "id": "know_008", "difficulty": "medium", "category": "knowledge",
        "instruction": "What is the pH of pure water at 25°C? Answer with just the number.",
        "expected_answer": "7", "check": "exact",
    },
    {
        "id": "know_009", "difficulty": "medium", "category": "knowledge",
        "instruction": "What gas makes up approximately 78% of Earth's atmosphere? Answer with just the gas name.",
        "expected_answer": "nitrogen", "check": "contains",
    },
    {
        "id": "know_010", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the atomic number of carbon? Answer with just the number.",
        "expected_answer": "6", "check": "exact",
    },
    # ── Science — Biology ────────────────────────────────────────────────────
    {
        "id": "know_011", "difficulty": "easy", "category": "knowledge",
        "instruction": "What is the powerhouse of the cell? Answer with just the organelle name.",
        "expected_answer": "mitochondria", "check": "contains",
    },
    {
        "id": "know_012", "difficulty": "easy", "category": "knowledge",
        "instruction": "How many pairs of chromosomes do humans have? Answer with just the number.",
        "expected_answer": "23", "check": "exact",
    },
    {
        "id": "know_013", "difficulty": "medium", "category": "knowledge",
        "instruction": "What molecule carries genetic information in living cells? Answer with just the molecule name.",
        "expected_answer": "DNA", "check": "contains",
    },
    {
        "id": "know_014", "difficulty": "medium", "category": "knowledge",
        "instruction": "What process do plants use to convert sunlight into energy? Answer with just the process name.",
        "expected_answer": "photosynthesis", "check": "contains",
    },
    {
        "id": "know_015", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the name of the protein that carries oxygen in red blood cells? Answer with just the protein name.",
        "expected_answer": "hemoglobin", "check": "contains",
    },
    # ── History ──────────────────────────────────────────────────────────────
    {
        "id": "know_016", "difficulty": "easy", "category": "knowledge",
        "instruction": "In what year did World War II end? Answer with just the year.",
        "expected_answer": "1945", "check": "exact",
    },
    {
        "id": "know_017", "difficulty": "easy", "category": "knowledge",
        "instruction": "Who was the first president of the United States? Answer with just the full name.",
        "expected_answer": "George Washington", "check": "contains",
    },
    {
        "id": "know_018", "difficulty": "easy", "category": "knowledge",
        "instruction": "In what year did the Berlin Wall fall? Answer with just the year.",
        "expected_answer": "1989", "check": "exact",
    },
    {
        "id": "know_019", "difficulty": "medium", "category": "knowledge",
        "instruction": "Which ancient wonder of the world still stands today? Answer with just the name.",
        "expected_answer": "Great Pyramid", "check": "contains",
    },
    {
        "id": "know_020", "difficulty": "medium", "category": "knowledge",
        "instruction": "In what year did the French Revolution begin? Answer with just the year.",
        "expected_answer": "1789", "check": "exact",
    },
    {
        "id": "know_021", "difficulty": "medium", "category": "knowledge",
        "instruction": "Who invented the telephone? Answer with just the inventor's name.",
        "expected_answer": "Alexander Graham Bell", "check": "contains",
    },
    {
        "id": "know_022", "difficulty": "hard", "category": "knowledge",
        "instruction": "What year did the Roman Empire officially fall (Western Roman Empire)? Answer with just the year.",
        "expected_answer": "476", "check": "exact",
    },
    {
        "id": "know_023", "difficulty": "hard", "category": "knowledge",
        "instruction": "Who wrote 'The Art of War'? Answer with just the author's name.",
        "expected_answer": "Sun Tzu", "check": "contains",
    },
    # ── Geography ────────────────────────────────────────────────────────────
    {
        "id": "know_024", "difficulty": "easy", "category": "knowledge",
        "instruction": "What is the largest continent by area? Answer with just the continent name.",
        "expected_answer": "Asia", "check": "contains",
    },
    {
        "id": "know_025", "difficulty": "easy", "category": "knowledge",
        "instruction": "What is the capital of Australia? Answer with just the city name.",
        "expected_answer": "Canberra", "check": "contains",
    },
    {
        "id": "know_026", "difficulty": "easy", "category": "knowledge",
        "instruction": "What is the longest river in the world? Answer with just the river name.",
        "expected_answer": "Nile", "check": "contains",
    },
    {
        "id": "know_027", "difficulty": "medium", "category": "knowledge",
        "instruction": "How many countries are in Africa? Answer with just the number.",
        "expected_answer": "54", "check": "exact",
    },
    {
        "id": "know_028", "difficulty": "medium", "category": "knowledge",
        "instruction": "What is the smallest country in the world by area? Answer with just the country name.",
        "expected_answer": "Vatican", "check": "contains",
    },
    {
        "id": "know_029", "difficulty": "medium", "category": "knowledge",
        "instruction": "What is the highest mountain in the world? Answer with just the mountain name.",
        "expected_answer": "Everest", "check": "contains",
    },
    {
        "id": "know_030", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the capital of Kazakhstan? Answer with just the city name.",
        "expected_answer": "Astana", "check": "contains",
    },
    {
        "id": "know_031", "difficulty": "hard", "category": "knowledge",
        "instruction": "Which country has the most time zones? Answer with just the country name.",
        "expected_answer": "France", "check": "contains",
    },
    # ── Computer Science ─────────────────────────────────────────────────────
    {
        "id": "know_032", "difficulty": "easy", "category": "knowledge",
        "instruction": "What does CPU stand for? Answer with just the full phrase.",
        "expected_answer": "Central Processing Unit", "check": "contains",
    },
    {
        "id": "know_033", "difficulty": "easy", "category": "knowledge",
        "instruction": "What does HTTP stand for? Answer with the full phrase.",
        "expected_answer": "HyperText Transfer Protocol", "check": "contains",
    },
    {
        "id": "know_034", "difficulty": "easy", "category": "knowledge",
        "instruction": "In binary, what is 1 + 1? Answer with just the binary result.",
        "expected_answer": "10", "check": "exact",
    },
    {
        "id": "know_035", "difficulty": "medium", "category": "knowledge",
        "instruction": "What is the time complexity of binary search? Answer in Big-O notation.",
        "expected_answer": "O(log n)", "check": "contains",
    },
    {
        "id": "know_036", "difficulty": "medium", "category": "knowledge",
        "instruction": "What does SQL stand for? Answer with the full phrase.",
        "expected_answer": "Structured Query Language", "check": "contains",
    },
    {
        "id": "know_037", "difficulty": "medium", "category": "knowledge",
        "instruction": "What design pattern does 'publish-subscribe' implement? Answer with the pattern name.",
        "expected_answer": "Observer", "check": "contains",
    },
    {
        "id": "know_038", "difficulty": "medium", "category": "knowledge",
        "instruction": "What does ACID stand for in database transactions? Name all four words.",
        "expected_answer": "atomicity", "check": "contains",
    },
    {
        "id": "know_039", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the name of the algorithm used to find the shortest path in a weighted graph? Answer with just the algorithm name.",
        "expected_answer": "Dijkstra", "check": "contains",
    },
    {
        "id": "know_040", "difficulty": "hard", "category": "knowledge",
        "instruction": "What does TCP/IP stand for? Answer with the full phrase.",
        "expected_answer": "Transmission Control Protocol/Internet Protocol", "check": "contains",
    },
    {
        "id": "know_041", "difficulty": "hard", "category": "knowledge",
        "instruction": "In machine learning, what does 'overfitting' mean? Answer in one sentence.",
        "expected_answer": "training", "check": "contains",
    },
    # ── General Knowledge ────────────────────────────────────────────────────
    {
        "id": "know_042", "difficulty": "easy", "category": "knowledge",
        "instruction": "How many sides does a hexagon have? Answer with just the number.",
        "expected_answer": "6", "check": "exact",
    },
    {
        "id": "know_043", "difficulty": "easy", "category": "knowledge",
        "instruction": "What is the largest planet in our solar system? Answer with just the planet name.",
        "expected_answer": "Jupiter", "check": "contains",
    },
    {
        "id": "know_044", "difficulty": "easy", "category": "knowledge",
        "instruction": "Who painted the Mona Lisa? Answer with just the artist's name.",
        "expected_answer": "Leonardo da Vinci", "check": "contains",
    },
    {
        "id": "know_045", "difficulty": "medium", "category": "knowledge",
        "instruction": "What is the chemical formula for table salt? Answer with just the formula.",
        "expected_answer": "NaCl", "check": "contains",
    },
    {
        "id": "know_046", "difficulty": "medium", "category": "knowledge",
        "instruction": "What is the square root of 144? Answer with just the number.",
        "expected_answer": "12", "check": "exact",
    },
    {
        "id": "know_047", "difficulty": "medium", "category": "knowledge",
        "instruction": "What year was the first iPhone released? Answer with just the year.",
        "expected_answer": "2007", "check": "exact",
    },
    {
        "id": "know_048", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the most spoken language in the world by number of native speakers? Answer with just the language name.",
        "expected_answer": "Mandarin", "check": "contains",
    },
    {
        "id": "know_049", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the name of the economic principle stating that 80% of effects come from 20% of causes? Answer with just the name.",
        "expected_answer": "Pareto", "check": "contains",
    },
    {
        "id": "know_050", "difficulty": "hard", "category": "knowledge",
        "instruction": "What is the term for the study of flags? Answer with just the term.",
        "expected_answer": "vexillology", "check": "contains",
    },
]
