"""
Multi-language coding benchmarks — same problems across JavaScript, TypeScript,
Rust, and Go. Used to compare which models can write idiomatic code in
languages other than Python.
"""

# JavaScript (Node.js)
CODING_JS_TASKS = [
    {
        "id": "code_js_001", "difficulty": "easy", "category": "coding",
        "language": "javascript",
        "instruction":
            "Write a JavaScript function `fizzbuzz(n)` that returns an array of "
            "n strings: 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, "
            "'FizzBuzz' for both, otherwise the number as string. "
            "Print the function, then run: console.log(JSON.stringify(fizzbuzz(15))).",
        "test_code":
            "const got = fizzbuzz(15);\n"
            "const expect = ['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz'];\n"
            "if (JSON.stringify(got) !== JSON.stringify(expect)) "
            "{ console.error('FAIL'); process.exit(1); }",
    },
    {
        "id": "code_js_002", "difficulty": "easy", "category": "coding",
        "language": "javascript",
        "instruction":
            "Write `isPalindrome(s)` (case-insensitive, ignore non-alphanumeric). "
            "Print the function.",
        "test_code":
            "if (isPalindrome('A man, a plan, a canal: Panama') !== true) process.exit(1);\n"
            "if (isPalindrome('hello') !== false) process.exit(1);",
    },
    {
        "id": "code_js_003", "difficulty": "medium", "category": "coding",
        "language": "javascript",
        "instruction":
            "Write an async function `fetchAndCount(urls)` that takes an array of "
            "URL strings, simulates fetching by returning {url, length: url.length} "
            "for each in parallel using Promise.all. Print the function.",
        "test_code":
            "(async () => {\n"
            "  const r = await fetchAndCount(['a','bb','ccc']);\n"
            "  if (r.length !== 3 || r[2].length !== 3) process.exit(1);\n"
            "})();",
    },
    {
        "id": "code_js_004", "difficulty": "medium", "category": "coding",
        "language": "javascript",
        "instruction":
            "Implement an LRU cache class with `get(k)` and `put(k,v)`. "
            "Constructor takes capacity. get returns -1 if missing. Print the class.",
        "test_code":
            "const c = new LRUCache(2);\n"
            "c.put(1,1); c.put(2,2);\n"
            "if (c.get(1) !== 1) process.exit(1);\n"
            "c.put(3,3);\n"
            "if (c.get(2) !== -1) process.exit(1);",
    },
    {
        "id": "code_js_005", "difficulty": "medium", "category": "coding",
        "language": "javascript",
        "instruction":
            "Write a function `deepClone(obj)` that does a deep copy of plain "
            "objects, arrays, and nested combinations. Print the function.",
        "test_code":
            "const src = {a: 1, b: [{c: 2}]};\n"
            "const cp = deepClone(src);\n"
            "cp.b[0].c = 99;\n"
            "if (src.b[0].c === 99) process.exit(1);",
    },
]

# TypeScript
CODING_TS_TASKS = [
    {
        "id": "code_ts_001", "difficulty": "easy", "category": "coding",
        "language": "typescript",
        "instruction":
            "Write a TypeScript function `sum<T extends number>(arr: T[]): T` that "
            "sums an array of numbers with proper typing. Print the function.",
        "test_code":
            "const r: number = sum([1,2,3,4,5]);\n"
            "if (r !== 15) process.exit(1);",
    },
    {
        "id": "code_ts_002", "difficulty": "medium", "category": "coding",
        "language": "typescript",
        "instruction":
            "Define an interface `User { id: number; name: string; age: number }` "
            "and write `oldestUser(users: User[]): User | null` that returns the "
            "oldest user, or null if array is empty. Print the code.",
        "test_code":
            "const users = [{id:1,name:'A',age:20},{id:2,name:'B',age:30}];\n"
            "const top = oldestUser(users);\n"
            "if (!top || top.age !== 30) process.exit(1);",
    },
]

# Rust
CODING_RUST_TASKS = [
    {
        "id": "code_rust_001", "difficulty": "easy", "category": "coding",
        "language": "rust",
        "instruction":
            "Write a Rust program with `fn fibonacci(n: u32) -> u64` returning "
            "the nth Fibonacci number. Include `fn main()` that asserts "
            "fibonacci(10) == 55 and prints OK.",
        "test_code":
            "// supplied via main()",
    },
    {
        "id": "code_rust_002", "difficulty": "medium", "category": "coding",
        "language": "rust",
        "instruction":
            "Write a Rust program defining `fn is_prime(n: u32) -> bool` (efficient: "
            "trial division up to sqrt). Include main() that asserts is_prime(97) and "
            "!is_prime(100), then prints OK.",
        "test_code":
            "// supplied via main()",
    },
    {
        "id": "code_rust_003", "difficulty": "medium", "category": "coding",
        "language": "rust",
        "instruction":
            "Write a Rust program with `fn reverse_string(s: &str) -> String` that "
            "reverses unicode chars correctly. Include main() asserting "
            "reverse_string(\"hello\") == \"olleh\" and prints OK.",
        "test_code":
            "// supplied via main()",
    },
]

# Go
CODING_GO_TASKS = [
    {
        "id": "code_go_001", "difficulty": "easy", "category": "coding",
        "language": "go",
        "instruction":
            "Write a complete Go program (package main, imports, main func) with "
            "`func Factorial(n int) int`. main() should panic if Factorial(5) != 120, "
            "otherwise print OK.",
        "test_code": "// supplied via main()",
    },
    {
        "id": "code_go_002", "difficulty": "medium", "category": "coding",
        "language": "go",
        "instruction":
            "Write a complete Go program with `func WordCount(s string) "
            "map[string]int` that returns word frequencies (split by whitespace). "
            "main() should panic on mismatch and print OK.",
        "test_code": "// supplied via main()",
    },
]

# C++
CODING_CPP_TASKS = [
    {
        "id": "code_cpp_001", "difficulty": "easy", "category": "coding",
        "language": "cpp",
        "instruction":
            "Write a complete C++ program with `int gcd(int a, int b)`. main() must "
            "assert gcd(48, 18) == 6 and print OK.",
        "test_code": "// supplied via main()",
    },
    {
        "id": "code_cpp_002", "difficulty": "medium", "category": "coding",
        "language": "cpp",
        "instruction":
            "Write a complete C++ program defining `int longest_substring(const "
            "std::string& s)` returning length of longest substring without repeating "
            "chars. main() must assert longest_substring(\"abcabcbb\") == 3, prints OK.",
        "test_code": "// supplied via main()",
    },
]


ALL_MULTILANG_TASKS = (
    CODING_JS_TASKS + CODING_TS_TASKS + CODING_RUST_TASKS +
    CODING_GO_TASKS + CODING_CPP_TASKS
)
