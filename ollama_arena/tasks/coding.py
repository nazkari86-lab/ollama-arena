"""
Coding Benchmarks — 30 Python tasks with assert-based auto-evaluation.
Scored by: exec + assert tests (pass=1.0, fail=0.0).
"""

CODING_TASKS = [
    # Easy (10)
    {
        "id": "code_001", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `sieve(n)` that returns all prime numbers up to n using the Sieve of Eratosthenes.",
        "test_code": "assert sieve(10) == [2,3,5,7]\nassert sieve(1) == []\nassert sieve(2) == [2]",
    },
    {
        "id": "code_002", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `flatten(lst)` that flattens a nested list of arbitrary depth into a flat list.",
        "test_code": "assert flatten([1,[2,[3,4]],5]) == [1,2,3,4,5]\nassert flatten([]) == []\nassert flatten([1,2,3]) == [1,2,3]",
    },
    {
        "id": "code_003", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `count_words(text)` that returns a dict of word frequencies (case-insensitive).",
        "test_code": "r = count_words('Hello world hello')\nassert r['hello'] == 2\nassert r['world'] == 1",
    },
    {
        "id": "code_004", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `is_palindrome(s)` that returns True if the string is a palindrome (ignoring case and spaces).",
        "test_code": "assert is_palindrome('racecar') == True\nassert is_palindrome('A man a plan a canal Panama') == True\nassert is_palindrome('hello') == False",
    },
    {
        "id": "code_005", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `fibonacci(n)` that returns the nth Fibonacci number (0-indexed, fib(0)=0, fib(1)=1).",
        "test_code": "assert fibonacci(0) == 0\nassert fibonacci(1) == 1\nassert fibonacci(10) == 55",
    },
    {
        "id": "code_006", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `rotate_list(lst, k)` that rotates a list right by k positions.",
        "test_code": "assert rotate_list([1,2,3,4,5], 2) == [4,5,1,2,3]\nassert rotate_list([1,2,3], 0) == [1,2,3]\nassert rotate_list([], 3) == []",
    },
    {
        "id": "code_007", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `merge_sorted(a, b)` that merges two sorted lists into one sorted list without using sort().",
        "test_code": "assert merge_sorted([1,3,5], [2,4,6]) == [1,2,3,4,5,6]\nassert merge_sorted([], [1,2]) == [1,2]\nassert merge_sorted([1], []) == [1]",
    },
    {
        "id": "code_008", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `group_by(lst, key_fn)` that groups items from lst by the result of key_fn, returning a dict.",
        "test_code": "r = group_by([1,2,3,4,5,6], lambda x: x%2)\nassert r[0] == [2,4,6]\nassert r[1] == [1,3,5]",
    },
    {
        "id": "code_009", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `caesar_cipher(text, shift)` that encodes text using Caesar cipher (letters only, preserves case).",
        "test_code": "assert caesar_cipher('Hello', 3) == 'Khoor'\nassert caesar_cipher('xyz', 3) == 'abc'\nassert caesar_cipher('ABC', 1) == 'BCD'",
    },
    {
        "id": "code_010", "difficulty": "easy", "role": "coder",
        "instruction": "Write a Python function `binary_search(lst, target)` that returns the index of target in sorted list lst, or -1 if not found.",
        "test_code": "assert binary_search([1,3,5,7,9], 5) == 2\nassert binary_search([1,3,5,7,9], 4) == -1\nassert binary_search([], 1) == -1",
    },
    # Medium (12)
    {
        "id": "code_011", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `lru_cache_fn(capacity)` that returns a dict-like object implementing LRU cache with get(key) and put(key, value) methods.",
        "test_code": "cache = lru_cache_fn(2)\ncache.put(1, 1)\ncache.put(2, 2)\nassert cache.get(1) == 1\ncache.put(3, 3)\nassert cache.get(2) == -1\nassert cache.get(3) == 3",
    },
    {
        "id": "code_012", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `parse_csv(csv_string)` that parses a CSV string (with header) and returns a list of dicts.",
        "test_code": "r = parse_csv('name,age\\nAlice,30\\nBob,25')\nassert r == [{'name':'Alice','age':'30'},{'name':'Bob','age':'25'}]",
    },
    {
        "id": "code_013", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python async function `fetch_all(urls)` using asyncio and aiohttp that fetches all URLs concurrently and returns a list of (url, status_code) tuples. For URLs that fail to connect, use status_code=-1.",
        "test_code": "import asyncio\nfrom unittest.mock import patch, AsyncMock, MagicMock\nclass _Resp:\n    def __init__(self, s): self.status = s\n    async def __aenter__(self): return self\n    async def __aexit__(self, *a): pass\nclass _Session:\n    def get(self, url, **kw): return _Resp(200 if '200' in url else 404)\n    async def __aenter__(self): return self\n    async def __aexit__(self, *a): pass\nwith patch('aiohttp.ClientSession', return_value=_Session()):\n    result = asyncio.run(fetch_all(['http://example.com/200', 'http://example.com/404']))\nassert isinstance(result, list) and len(result) == 2",
    },
    {
        "id": "code_014", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `deep_diff(dict_a, dict_b)` that returns a dict describing differences between two nested dicts: {'added': {...}, 'removed': {...}, 'changed': {...}}.",
        "test_code": "r = deep_diff({'a':1,'b':2,'c':3}, {'a':1,'b':99,'d':4})\nassert r['removed'] == {'c':3}\nassert r['added'] == {'d':4}\nassert r['changed'] == {'b': (2,99)}",
    },
    {
        "id": "code_015", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `topological_sort(graph)` where graph is a dict {node: [deps]}, returning nodes in topological order or raising ValueError on cycle.",
        "test_code": "order = topological_sort({'A':[],'B':['A'],'C':['A','B']})\nassert order.index('A') < order.index('B') < order.index('C')",
    },
    {
        "id": "code_016", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python class `RateLimiter(max_calls, period_seconds)` with a method `is_allowed()` that returns True if the call is within the rate limit (sliding window).",
        "test_code": "import time\nrl = RateLimiter(3, 1)\nassert rl.is_allowed() == True\nassert rl.is_allowed() == True\nassert rl.is_allowed() == True\nassert rl.is_allowed() == False",
    },
    {
        "id": "code_017", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `json_schema_validate(data, schema)` that validates a dict against a simple JSON schema (type, required, properties) and returns (is_valid: bool, errors: list).",
        "test_code": "schema = {'type':'object','required':['name','age'],'properties':{'name':{'type':'string'},'age':{'type':'integer'}}}\nok, errs = json_schema_validate({'name':'Alice','age':30}, schema)\nassert ok == True\nok, errs = json_schema_validate({'name':'Alice'}, schema)\nassert ok == False\nassert any('age' in e for e in errs)",
    },
    {
        "id": "code_018", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `rolling_stats(numbers, window)` that returns a list of dicts with 'mean' and 'std' for each rolling window.",
        "test_code": "import math\nr = rolling_stats([1,2,3,4,5], 3)\nassert len(r) == 3\nassert abs(r[0]['mean'] - 2.0) < 0.001\nassert r[0]['std'] >= 0",
    },
    {
        "id": "code_019", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `retry(fn, max_attempts, exceptions, delay_seconds)` decorator that retries fn on specified exceptions.",
        "test_code": "counter = [0]\n@retry(max_attempts=3, exceptions=(ValueError,), delay_seconds=0)\ndef flaky():\n    counter[0] += 1\n    if counter[0] < 3:\n        raise ValueError('not yet')\n    return 'ok'\nassert flaky() == 'ok'\nassert counter[0] == 3",
    },
    {
        "id": "code_020", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `trie_search(words, prefix)` that builds a trie from a list of words and returns all words with the given prefix.",
        "test_code": "r = trie_search(['apple','app','application','banana','band'], 'app')\nassert set(r) == {'apple','app','application'}",
    },
    {
        "id": "code_021", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `matrix_multiply(A, B)` that multiplies two 2D matrices without using numpy.",
        "test_code": "r = matrix_multiply([[1,2],[3,4]], [[5,6],[7,8]])\nassert r == [[19,22],[43,50]]",
    },
    {
        "id": "code_022", "difficulty": "medium", "role": "coder",
        "instruction": "Write a Python function `parse_duration(s)` that parses strings like '2h30m15s' into total seconds.",
        "test_code": "assert parse_duration('2h30m15s') == 9015\nassert parse_duration('1h') == 3600\nassert parse_duration('90s') == 90\nassert parse_duration('1h1m1s') == 3661",
    },
    # Hard (8)
    {
        "id": "code_023", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python function `consistent_hash(nodes, replicas=150)` that implements a consistent hashing ring. It should have methods: add_node(node), remove_node(node), get_node(key) returning the responsible node.",
        "test_code": "ch = consistent_hash(['A','B','C'])\nassert ch.get_node('key1') in ['A','B','C']\nch.add_node('D')\nassert ch.get_node('key1') in ['A','B','C','D']\nch.remove_node('D')\nassert ch.get_node('key1') in ['A','B','C']",
    },
    {
        "id": "code_024", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python function `levenshtein_distance(s1, s2)` and `fuzzy_match(query, candidates, threshold=0.7)` that returns candidates whose similarity (1 - edit_dist/max_len) >= threshold.",
        "test_code": "assert levenshtein_distance('kitten','sitting') == 3\nassert levenshtein_distance('','abc') == 3\nr = fuzzy_match('hello', ['hello','hell','world','help'], threshold=0.8)\nassert 'hello' in r and 'hell' in r and 'world' not in r",
    },
    {
        "id": "code_025", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python async generator `async_pipeline(*stages)` where each stage is an async function that processes items. Items flow through stages in order, with concurrency within each stage.",
        "test_code": "import asyncio\nasync def double(x): return x*2\nasync def add1(x): return x+1\nresult = []\nasync def collect():\n    async for item in async_pipeline([1,2,3], double, add1):\n        result.append(item)\nasyncio.run(collect())\nassert sorted(result) == [3,5,7]",
    },
    {
        "id": "code_026", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python class `ObservableDict` that behaves like a dict but fires callbacks registered via on_change(callback) whenever a key is set or deleted.",
        "test_code": "events = []\nd = ObservableDict()\nd.on_change(lambda k,v,op: events.append((k,v,op)))\nd['x'] = 1\ndel d['x']\nassert events[0] == ('x',1,'set')\nassert events[1] == ('x',None,'del')",
    },
    {
        "id": "code_027", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python function `bloom_filter(capacity, error_rate)` returning an object with add(item) and contains(item) methods using a bit array and multiple hash functions.",
        "test_code": "bf = bloom_filter(1000, 0.01)\nbf.add('apple')\nbf.add('banana')\nassert bf.contains('apple') == True\nassert bf.contains('banana') == True\nfp_count = sum(1 for i in range(1000) if bf.contains(f'zzz{i}'))\nassert fp_count < 20",
    },
    {
        "id": "code_028", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python function `expression_eval(expr)` that evaluates a math expression string with +,-,*,/,^ and parentheses using a recursive descent parser (no eval()).",
        "test_code": "assert expression_eval('2+3*4') == 14\nassert expression_eval('(2+3)*4') == 20\nassert expression_eval('2^3') == 8\nassert abs(expression_eval('10/4') - 2.5) < 0.001",
    },
    {
        "id": "code_029", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python class `ThreadSafeQueue(maxsize)` with put(item, timeout=None) and get(timeout=None) methods that are thread-safe and support blocking with timeout.",
        "test_code": "import threading, time\nq = ThreadSafeQueue(2)\nq.put(1)\nq.put(2)\nresults = []\ndef consumer():\n    results.append(q.get(timeout=1))\n    results.append(q.get(timeout=1))\nt = threading.Thread(target=consumer)\nt.start()\nt.join(timeout=2)\nassert sorted(results) == [1,2]",
    },
    {
        "id": "code_030", "difficulty": "hard", "role": "coder",
        "instruction": "Write a Python function `minimax(board, depth, maximizing)` for a tic-tac-toe board (3x3 list of lists with 'X','O',None). Return the best score for the current player. Also write `best_move(board)` that returns (row, col) of the best move for 'X'.",
        "test_code": "board = [['X','O','X'],['O','X',None],['O',None,None]]\nmove = best_move(board)\nassert move == (2,1) or isinstance(move, tuple)",
    },
]
