"""
JSON conformance tasks with expected schema validation.
Each task defines an expected schema of keys and types to evaluate structured format outputs.
"""

JSON_TASKS = [
    {
        "id": "json_001", "difficulty": "easy", "category": "json_format", "role": "coder",
        "instruction": "Extract the city, temperature in Celsius, and wind speed from: 'It is a sunny day in Paris with 22°C temperature and wind blowing at 15 km/h.' Output only as a JSON object.",
        "expected_schema": {"city": "string", "temperature": "number", "wind_speed": "number"}
    },
    {
        "id": "json_002", "difficulty": "easy", "category": "json_format", "role": "coder",
        "instruction": "Output a JSON object representing a user profile with fields: username, is_admin (boolean), and age (integer). Make up any dummy values.",
        "expected_schema": {"username": "string", "is_admin": "boolean", "age": "integer"}
    },
    {
        "id": "json_003", "difficulty": "easy", "category": "json_format", "role": "coder",
        "instruction": "Format product information for a laptop costing 999.99 with rating 4.8 and model 'X-500' into a JSON object with keys: name, price, rating, model.",
        "expected_schema": {"name": "string", "price": "number", "rating": "number", "model": "string"}
    },
    {
        "id": "json_004", "difficulty": "easy", "category": "json_format", "role": "coder",
        "instruction": "Extract book details from: 'To Kill a Mockingbird by Harper Lee, published in 1960.' Output a JSON object with keys: title, author, and year.",
        "expected_schema": {"title": "string", "author": "string", "year": "integer"}
    },
    {
        "id": "json_005", "difficulty": "easy", "category": "json_format", "role": "coder",
        "instruction": "Format a coordinate point (x=10, y=-25.5, label='Origin') into a JSON object with keys: x, y, label.",
        "expected_schema": {"x": "number", "y": "number", "label": "string"}
    },
    {
        "id": "json_006", "difficulty": "medium", "category": "json_format", "role": "coder",
        "instruction": "Analyze this movie log: 'Inception (2010), directed by Christopher Nolan, starring Leonardo DiCaprio, Joseph Gordon-Levitt. Genres: Sci-Fi, Action.' Output a JSON object with keys: title, year, director, cast (list of strings), and genres (list of strings).",
        "expected_schema": {"title": "string", "year": "integer", "director": "string", "cast": "list", "genres": "list"}
    },
    {
        "id": "json_007", "difficulty": "medium", "category": "json_format", "role": "coder",
        "instruction": "Create a JSON receipt representation for 3 items: Apple ($1.20), Bread ($2.50), Milk ($3.00). Include keys: item_count (integer), items (list of strings), and total_price (number).",
        "expected_schema": {"item_count": "integer", "items": "list", "total_price": "number"}
    },
    {
        "id": "json_008", "difficulty": "medium", "category": "json_format", "role": "coder",
        "instruction": "Extract the server log information: 'ERROR 2026-06-15 22:45:10 - Database timeout occurred on db-01 after 30 seconds.' Output a JSON object with keys: level, timestamp, message, source, and timeout_seconds.",
        "expected_schema": {"level": "string", "timestamp": "string", "message": "string", "source": "string", "timeout_seconds": "integer"}
    },
    {
        "id": "json_009", "difficulty": "medium", "category": "json_format", "role": "coder",
        "instruction": "Generate a todo item object with keys: task (string), due_date (string), tags (list of strings), and completed (boolean). Use dummy values.",
        "expected_schema": {"task": "string", "due_date": "string", "tags": "list", "completed": "boolean"}
    },
    {
        "id": "json_010", "difficulty": "medium", "category": "json_format", "role": "coder",
        "instruction": "Parse: 'Flight BA249 to New York departs from Gate 14 at 15:30.' Output a JSON object with keys: flight_number, destination, gate (integer), and departure_time.",
        "expected_schema": {"flight_number": "string", "destination": "string", "gate": "integer", "departure_time": "string"}
    },
    {
        "id": "json_011", "difficulty": "medium", "category": "json_format", "role": "coder",
        "instruction": "Create a real estate profile JSON for a house at 123 Maple St: 3 bedrooms, 2.5 bathrooms, price 450000, has_garage (boolean True). Keys: address, bedrooms, bathrooms, price, has_garage.",
        "expected_schema": {"address": "string", "bedrooms": "integer", "bathrooms": "number", "price": "number", "has_garage": "boolean"}
    },
    {
        "id": "json_012", "difficulty": "hard", "category": "json_format", "role": "coder",
        "instruction": "Categorize this customer email: 'Hey support, my order #99482 hasn't arrived yet. It was supposed to be delivered last Tuesday.' Output a JSON object with keys: order_id (string), category (string), sentiment (string: positive/neutral/negative), and urgent (boolean).",
        "expected_schema": {"order_id": "string", "category": "string", "sentiment": "string", "urgent": "boolean"}
    },
    {
        "id": "json_013", "difficulty": "hard", "category": "json_format", "role": "coder",
        "instruction": "Perform a code review of a script: 'def add(a, b): return a - b'. Output a JSON object with keys: bug_found (boolean), line_number (integer), severity (string: low/medium/high), and suggestion (string).",
        "expected_schema": {"bug_found": "boolean", "line_number": "integer", "severity": "string", "suggestion": "string"}
    },
    {
        "id": "json_014", "difficulty": "hard", "category": "json_format", "role": "coder",
        "instruction": "Extract medical prescription details from: 'Take Amoxicillin 500mg twice daily for 7 days.' Output a JSON object with keys: drug_name, dosage, frequency, duration_days (integer).",
        "expected_schema": {"drug_name": "string", "dosage": "string", "frequency": "string", "duration_days": "integer"}
    },
    {
        "id": "json_015", "difficulty": "hard", "category": "json_format", "role": "coder",
        "instruction": "Format git commit analysis: 'feat: add user login endpoint (commit hash: abc1234, changes: 3 files, 150 lines).' Output a JSON object with keys: type, description, hash, files_changed (integer), and lines_added (integer).",
        "expected_schema": {"type": "string", "description": "string", "hash": "string", "files_changed": "integer", "lines_added": "integer"}
    }
]
