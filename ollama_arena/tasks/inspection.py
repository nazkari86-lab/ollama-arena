"""
Inspection Benchmarks — 20 code samples with ground truth.
10 clean (no bugs), 10 buggy. Scored by precision/recall vs ground_truth.
"""

INSPECTION_TASKS = [
    # Buggy samples (10)
    {
        "id": "insp_001", "has_bug": True, "bug_type": "command_injection",
        "code": """
import os
def delete_file(filename):
    os.system(f'rm {filename}')
""",
        "expected_issues": ["command_injection", "unsanitized_input", "os.system"],
        "safe_alternative": "Use os.remove(filename) after validating the path.",
    },
    {
        "id": "insp_002", "has_bug": True, "bug_type": "sql_injection",
        "code": """
import sqlite3
def get_user(username):
    conn = sqlite3.connect('users.db')
    cur = conn.execute(f"SELECT * FROM users WHERE name = '{username}'")
    return cur.fetchall()
""",
        "expected_issues": ["sql_injection", "string_formatting_in_query"],
        "safe_alternative": "Use parameterized queries: conn.execute('SELECT * FROM users WHERE name = ?', (username,))",
    },
    {
        "id": "insp_003", "has_bug": True, "bug_type": "path_traversal",
        "code": """
import os
def read_file(filename, base_dir='/var/www/files'):
    path = os.path.join(base_dir, filename)
    with open(path) as f:
        return f.read()
""",
        "expected_issues": ["path_traversal"],
        "safe_alternative": "Validate: os.path.realpath(path).startswith(base_dir) before opening.",
    },
    {
        "id": "insp_004", "has_bug": True, "bug_type": "hardcoded_secret",
        "code": """
import requests
def get_data():
    API_KEY = 'sk-prod-9f3b2a1c4d5e6f7g8h9i0j'
    return requests.get('https://api.example.com/data',
                        headers={'Authorization': f'Bearer {API_KEY}'})
""",
        "expected_issues": ["hardcoded_secret", "hardcoded_api_key"],
        "safe_alternative": "Load from environment: os.environ.get('API_KEY')",
    },
    {
        "id": "insp_005", "has_bug": True, "bug_type": "infinite_loop_risk",
        "code": """
import requests
def fetch_with_retry(url):
    while True:
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
""",
        "expected_issues": ["infinite_loop_risk", "missing_retry_limit", "missing_timeout"],
        "safe_alternative": "Add max_retries counter and requests.get(url, timeout=30).",
    },
    {
        "id": "insp_006", "has_bug": True, "bug_type": "use_of_eval",
        "code": """
def calculate(expression, user_input):
    result = eval(f'{expression} {user_input}')
    return result
""",
        "expected_issues": ["unsafe_eval", "code_injection", "user_input_in_eval"],
        "safe_alternative": "Use ast.literal_eval() or a safe expression parser.",
    },
    {
        "id": "insp_007", "has_bug": True, "bug_type": "missing_error_handling",
        "code": """
import json, requests
def load_config(url):
    r = requests.get(url)
    config = json.loads(r.text)
    return config['settings']
""",
        "expected_issues": ["missing_error_handling", "no_timeout", "missing_key_check"],
        "safe_alternative": "Wrap in try/except, add timeout, check status_code, use config.get('settings').",
    },
    {
        "id": "insp_008", "has_bug": True, "bug_type": "race_condition",
        "code": """
import os
def safe_write(filename, content):
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            f.write(content)
""",
        "expected_issues": ["race_condition", "toctou"],
        "safe_alternative": "Use open(filename, 'x') for atomic exclusive create, or file locks.",
    },
    {
        "id": "insp_009", "has_bug": True, "bug_type": "integer_overflow_risk",
        "code": """
def factorial(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result % (2**31 - 1)
""",
        "expected_issues": ["missing_input_validation", "negative_input_unhandled"],
        "safe_alternative": "Validate n >= 0, add n > 1000 guard for performance.",
    },
    {
        "id": "insp_010", "has_bug": True, "bug_type": "insecure_deserialization",
        "code": """
import pickle, base64
def load_session(session_data: str):
    return pickle.loads(base64.b64decode(session_data))
""",
        "expected_issues": ["insecure_deserialization", "arbitrary_code_execution_risk"],
        "safe_alternative": "Use JSON for session data. Never unpickle untrusted input.",
    },
    # Clean samples (10)
    {
        "id": "insp_011", "has_bug": False, "bug_type": None,
        "code": """
import os, re
def read_user_file(filename: str, base_dir: str = '/var/www/uploads') -> str:
    if not re.match(r'^[a-zA-Z0-9_.-]+$', filename):
        raise ValueError('Invalid filename')
    path = os.path.realpath(os.path.join(base_dir, filename))
    if not path.startswith(os.path.realpath(base_dir)):
        raise PermissionError('Path traversal detected')
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
""",
        "expected_issues": [],
    },
    {
        "id": "insp_012", "has_bug": False, "bug_type": None,
        "code": """
import sqlite3
from contextlib import closing
def get_user_by_id(db_path: str, user_id: int) -> dict:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        return dict(row) if row else {}
""",
        "expected_issues": [],
    },
    {
        "id": "insp_013", "has_bug": False, "bug_type": None,
        "code": """
import os, requests
def call_api(endpoint: str) -> dict:
    api_key = os.environ.get('API_KEY')
    if not api_key:
        raise EnvironmentError('API_KEY not set')
    try:
        r = requests.get(endpoint, headers={'Authorization': f'Bearer {api_key}'}, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise RuntimeError(f'API call failed: {e}') from e
""",
        "expected_issues": [],
    },
    {
        "id": "insp_014", "has_bug": False, "bug_type": None,
        "code": """
import hashlib, secrets
def hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000)
    return f'{salt}:{h.hex()}'
def verify_password(password: str, stored: str) -> bool:
    salt, hx = stored.split(':', 1)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000)
    return secrets.compare_digest(h.hex(), hx)
""",
        "expected_issues": [],
    },
    {
        "id": "insp_015", "has_bug": False, "bug_type": None,
        "code": """
import subprocess, shlex
def run_command(cmd: str, allowed_cmds: list) -> str:
    parts = shlex.split(cmd)
    if not parts or parts[0] not in allowed_cmds:
        raise ValueError(f'Command not allowed: {parts[0] if parts else "empty"}')
    result = subprocess.run(parts, capture_output=True, text=True, timeout=30)
    return result.stdout
""",
        "expected_issues": [],
    },
    {
        "id": "insp_016", "has_bug": False, "bug_type": None,
        "code": """
import json, os, tempfile
def atomic_write(filepath: str, data: dict) -> None:
    dir_path = os.path.dirname(os.path.abspath(filepath))
    fd, tmp = tempfile.mkstemp(dir=dir_path)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, filepath)
    except Exception:
        os.unlink(tmp)
        raise
""",
        "expected_issues": [],
    },
    {
        "id": "insp_017", "has_bug": False, "bug_type": None,
        "code": """
from functools import wraps
import time, logging
logger = logging.getLogger(__name__)
def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            attempt, wait = 0, delay
            while attempt < max_attempts:
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    logger.warning(f'Retry {attempt}/{max_attempts}: {e}')
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator
""",
        "expected_issues": [],
    },
    {
        "id": "insp_018", "has_bug": False, "bug_type": None,
        "code": """
import threading
class SafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    def increment(self) -> int:
        with self._lock:
            self._value += 1
            return self._value
    def reset(self) -> None:
        with self._lock:
            self._value = 0
    @property
    def value(self) -> int:
        with self._lock:
            return self._value
""",
        "expected_issues": [],
    },
    {
        "id": "insp_019", "has_bug": False, "bug_type": None,
        "code": """
import ast
def safe_eval_expr(expr: str) -> float:
    allowed_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num,
                     ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub)
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError(f'Invalid expression: {e}')
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f'Disallowed node type: {type(node).__name__}')
    return eval(compile(tree, '<string>', 'eval'))
""",
        "expected_issues": [],
    },
    {
        "id": "insp_020", "has_bug": False, "bug_type": None,
        "code": """
import json
def load_config(path: str, schema: dict) -> dict:
    try:
        with open(path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON in {path}: {e}')
    for key in schema.get('required', []):
        if key not in config:
            raise ValueError(f'Missing required key: {key}')
    return config
""",
        "expected_issues": [],
    },
]
