"""
Security Benchmarks — 15 CVE-pattern / vulnerability detection tasks.
Scored by: known vulnerability detection rate (precision/recall vs ground_truth).
Each task shows code and the model must identify SPECIFIC vulnerability class + severity.
"""

SECURITY_TASKS = [
    {
        "id": "sec_001", "severity": "critical", "cve_class": "CWE-78",
        "instruction": "Analyze this code for command injection vulnerabilities and explain the attack vector.",
        "code": """
import subprocess
def backup_database(db_name, output_dir):
    cmd = f'pg_dump {db_name} > {output_dir}/{db_name}.sql'
    subprocess.call(cmd, shell=True)
""",
        "expected_vulns": ["command_injection", "shell=True with user input", "CWE-78"],
        "expected_severity": "critical",
        "expected_fix": "Use subprocess.run with list args, never shell=True with user data",
    },
    {
        "id": "sec_002", "severity": "critical", "cve_class": "CWE-89",
        "instruction": "Find all SQL injection points in this authentication code.",
        "code": """
def authenticate(username, password, db):
    query = "SELECT id FROM users WHERE username='%s' AND password='%s'" % (username, password)
    result = db.execute(query)
    return result.fetchone() is not None
""",
        "expected_vulns": ["sql_injection", "string_formatting_in_query", "authentication_bypass", "CWE-89"],
        "expected_severity": "critical",
        "expected_fix": "Use parameterized queries",
    },
    {
        "id": "sec_003", "severity": "high", "cve_class": "CWE-22",
        "instruction": "Identify path traversal vulnerabilities in this file server code.",
        "code": """
from flask import Flask, request, send_file
app = Flask(__name__)
UPLOAD_DIR = '/app/uploads'
@app.route('/download')
def download():
    filename = request.args.get('file')
    return send_file(f'{UPLOAD_DIR}/{filename}')
""",
        "expected_vulns": ["path_traversal", "directory_traversal", "CWE-22"],
        "expected_severity": "high",
        "expected_fix": "Sanitize filename, use os.path.realpath and verify it starts with UPLOAD_DIR",
    },
    {
        "id": "sec_004", "severity": "critical", "cve_class": "CWE-502",
        "instruction": "Identify insecure deserialization risks in this API endpoint.",
        "code": """
import pickle, base64
from flask import Flask, request
app = Flask(__name__)
@app.route('/restore', methods=['POST'])
def restore_state():
    data = base64.b64decode(request.json['state'])
    obj = pickle.loads(data)
    return {'status': 'restored', 'type': type(obj).__name__}
""",
        "expected_vulns": ["insecure_deserialization", "arbitrary_code_execution", "CWE-502"],
        "expected_severity": "critical",
        "expected_fix": "Never unpickle user-supplied data. Use JSON or signed+encrypted formats.",
    },
    {
        "id": "sec_005", "severity": "high", "cve_class": "CWE-79",
        "instruction": "Find XSS vulnerabilities in this template rendering code.",
        "code": """
from flask import Flask, request, Markup
app = Flask(__name__)
@app.route('/greet')
def greet():
    name = request.args.get('name', 'stranger')
    html = f'<h1>Hello, {name}!</h1><p>Welcome to our site.</p>'
    return Markup(html)
""",
        "expected_vulns": ["reflected_xss", "unescaped_user_input_in_html", "CWE-79"],
        "expected_severity": "high",
        "expected_fix": "Use template engine with auto-escaping, never build HTML with f-strings from user input",
    },
    {
        "id": "sec_006", "severity": "medium", "cve_class": "CWE-330",
        "instruction": "Identify cryptographic weaknesses in this token generation code.",
        "code": """
import random, string
def generate_api_token():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(32))
""",
        "expected_vulns": ["weak_random", "predictable_token", "CWE-330"],
        "expected_severity": "medium",
        "expected_fix": "Use secrets.token_urlsafe(32) for cryptographically secure tokens",
    },
    {
        "id": "sec_007", "severity": "high", "cve_class": "CWE-798",
        "instruction": "Find hardcoded credential vulnerabilities.",
        "code": """
import boto3
def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id='AKIAIOSFODNN7EXAMPLE',
        aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        region_name='us-east-1'
    )
""",
        "expected_vulns": ["hardcoded_credentials", "hardcoded_aws_key", "CWE-798"],
        "expected_severity": "high",
        "expected_fix": "Use IAM roles, AWS_PROFILE, or environment variables. Never hardcode credentials.",
    },
    {
        "id": "sec_008", "severity": "medium", "cve_class": "CWE-307",
        "instruction": "Identify authentication brute-force vulnerabilities in this login endpoint.",
        "code": """
from flask import Flask, request, jsonify
app = Flask(__name__)
@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    if check_credentials(username, password):
        return jsonify({'token': generate_token(username)})
    return jsonify({'error': 'Invalid credentials'}), 401
""",
        "expected_vulns": ["no_rate_limiting", "brute_force_vulnerable", "no_lockout", "CWE-307"],
        "expected_severity": "medium",
        "expected_fix": "Add rate limiting, account lockout after N failures, CAPTCHA",
    },
    {
        "id": "sec_009", "severity": "high", "cve_class": "CWE-295",
        "instruction": "Find SSL/TLS certificate validation bypass.",
        "code": """
import requests
import ssl
def fetch_secure_data(url):
    return requests.get(url, verify=False, timeout=30).json()
""",
        "expected_vulns": ["ssl_verification_disabled", "mitm_vulnerable", "CWE-295"],
        "expected_severity": "high",
        "expected_fix": "Remove verify=False. Use verify=True (default) or provide CA bundle path.",
    },
    {
        "id": "sec_010", "severity": "medium", "cve_class": "CWE-601",
        "instruction": "Identify open redirect vulnerability in this authentication flow.",
        "code": """
from flask import Flask, request, redirect
app = Flask(__name__)
@app.route('/login')
def login():
    next_url = request.args.get('next', '/')
    # ... validate credentials ...
    return redirect(next_url)
""",
        "expected_vulns": ["open_redirect", "unvalidated_redirect", "CWE-601"],
        "expected_severity": "medium",
        "expected_fix": "Validate next_url is relative or matches allowed domain list",
    },
    {
        "id": "sec_011", "severity": "low", "cve_class": "CWE-209",
        "instruction": "Identify information disclosure vulnerabilities.",
        "code": """
from flask import Flask, jsonify
import traceback
app = Flask(__name__)
@app.errorhandler(Exception)
def handle_error(e):
    return jsonify({
        'error': str(e),
        'traceback': traceback.format_exc(),
        'type': type(e).__name__
    }), 500
""",
        "expected_vulns": ["information_disclosure", "traceback_exposed_to_user", "CWE-209"],
        "expected_severity": "low",
        "expected_fix": "Log full traceback server-side, return only generic error message to client",
    },
    {
        "id": "sec_012", "severity": "high", "cve_class": "CWE-352",
        "instruction": "Identify CSRF vulnerability in this state-changing endpoint.",
        "code": """
from flask import Flask, request, session
app = Flask(__name__)
@app.route('/transfer', methods=['POST'])
def transfer_money():
    if 'user_id' not in session:
        return 'Unauthorized', 401
    amount = request.form.get('amount')
    to_account = request.form.get('to')
    do_transfer(session['user_id'], to_account, float(amount))
    return 'Transfer complete'
""",
        "expected_vulns": ["csrf", "no_csrf_token", "CWE-352"],
        "expected_severity": "high",
        "expected_fix": "Add CSRF token validation (Flask-WTF, or manual token in session vs form)",
    },
    {
        "id": "sec_013", "severity": "critical", "cve_class": "CWE-94",
        "instruction": "Find code injection vulnerability via unsafe import.",
        "code": """
import importlib
def load_plugin(plugin_name: str):
    module = importlib.import_module(f'plugins.{plugin_name}')
    return module.run()
""",
        "expected_vulns": ["code_injection", "arbitrary_module_import", "CWE-94"],
        "expected_severity": "critical",
        "expected_fix": "Whitelist allowed plugin names, validate against known safe identifiers",
    },
    {
        "id": "sec_014", "severity": "medium", "cve_class": "CWE-400",
        "instruction": "Identify resource exhaustion / DoS vulnerability.",
        "code": """
import re
def validate_email(email: str) -> bool:
    pattern = r'^([a-zA-Z0-9]+(\\.[a-zA-Z0-9]+)*)+@([a-zA-Z0-9]+(\\.[a-zA-Z0-9]+)*)+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
""",
        "expected_vulns": ["redos", "catastrophic_backtracking", "CWE-400"],
        "expected_severity": "medium",
        "expected_fix": "Use re.match with timeout, limit input length, or use simple non-backtracking pattern",
    },
    {
        "id": "sec_015", "severity": "high", "cve_class": "CWE-434",
        "instruction": "Find unrestricted file upload vulnerability.",
        "code": """
import os
from flask import Flask, request
app = Flask(__name__)
UPLOAD_DIR = '/app/uploads'
@app.route('/upload', methods=['POST'])
def upload_file():
    f = request.files['file']
    filename = f.filename
    f.save(os.path.join(UPLOAD_DIR, filename))
    return f'Saved {filename}'
""",
        "expected_vulns": ["unrestricted_file_upload", "path_traversal", "no_type_validation", "CWE-434"],
        "expected_severity": "high",
        "expected_fix": "Validate extension whitelist, use secure_filename(), check MIME type",
    },
]
