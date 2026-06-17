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
    {
        "id": "code_js_006", "difficulty": "easy", "category": "coding",
        "language": "javascript",
        "instruction":
            "Write a JavaScript function `chunkArray(arr, size)` that splits an array "
            "into chunks of a given size. Print the function.",
        "test_code":
            "const got = chunkArray([1, 2, 3, 4, 5], 2);\n"
            "const expect = [[1, 2], [3, 4], [5]];\n"
            "if (JSON.stringify(got) !== JSON.stringify(expect)) process.exit(1);",
    },
    {
        "id": "code_js_007", "difficulty": "medium", "category": "coding",
        "language": "javascript",
        "instruction":
            "Write a JavaScript function `debounce(func, wait)` that returns a debounced "
            "version of the function. Print the function.",
        "test_code":
            "let count = 0;\n"
            "const fn = debounce(() => count++, 10);\n"
            "fn(); fn(); fn();\n"
            "setTimeout(() => {\n"
            "  if (count !== 1) process.exit(1);\n"
            "}, 20);",
    },
    {
        "id": "code_js_008", "difficulty": "hard", "category": "coding",
        "language": "javascript",
        "instruction":
            "Write a JavaScript class `EventEmitter` with methods `on(event, listener)`, "
            "`off(event, listener)`, and `emit(event, ...args)`. Print the class.",
        "test_code":
            "const ee = new EventEmitter();\n"
            "let got = 0;\n"
            "const cb = (x) => got = x;\n"
            "ee.on('test', cb);\n"
            "ee.emit('test', 42);\n"
            "ee.off('test', cb);\n"
            "ee.emit('test', 99);\n"
            "if (got !== 42) process.exit(1);",
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
    {
        "id": "code_ts_003", "difficulty": "easy", "category": "coding",
        "language": "typescript",
        "instruction":
            "Write a TypeScript function `isAnagram(s1: string, s2: string): boolean` "
            "that checks if two strings are anagrams (case-insensitive). Print the function.",
        "test_code":
            "if (isAnagram('silent', 'listen') !== true) process.exit(1);\n"
            "if (isAnagram('hello', 'world') !== false) process.exit(1);",
    },
    {
        "id": "code_ts_004", "difficulty": "medium", "category": "coding",
        "language": "typescript",
        "instruction":
            "Write a generic TypeScript class `Stack<T>` with methods `push(val: T): void`, "
            "`pop(): T | undefined`, `peek(): T | undefined`, `isEmpty(): boolean`, "
            "and `size(): number`. Print the class.",
        "test_code":
            "const s = new Stack<number>();\n"
            "s.push(1); s.push(2);\n"
            "if (s.pop() !== 2) process.exit(1);\n"
            "if (s.peek() !== 1) process.exit(1);\n"
            "if (s.isEmpty() !== false) process.exit(1);",
    },
    {
        "id": "code_ts_005", "difficulty": "hard", "category": "coding",
        "language": "typescript",
        "instruction":
            "Write a TypeScript function `deepMerge<T extends object, U extends object>(target: T, source: U): T & U` "
            "that recursively merges two objects. Print the function.",
        "test_code":
            "const a = { x: 1, y: { z: 2 } };\n"
            "const b = { y: { w: 3 }, v: 4 };\n"
            "const r = deepMerge(a, b);\n"
            "if (r.x !== 1 || r.v !== 4 || r.y.z !== 2 || r.y.w !== 3) process.exit(1);",
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
    {
        "id": "code_rust_004", "difficulty": "easy", "category": "coding",
        "language": "rust",
        "instruction":
            "Write a Rust program with `fn count_words(s: &str) -> std::collections::HashMap<String, u32>` "
            "returning word frequency counts (case-sensitive). Include `fn main()` that asserts "
            "count_words(\"hello world hello\")[\"hello\"] == 2 and prints OK.",
        "test_code":
            "// supplied via main()",
    },
    {
        "id": "code_rust_005", "difficulty": "medium", "category": "coding",
        "language": "rust",
        "instruction":
            "Write a Rust program with `fn bubble_sort(arr: &mut [i32])` that sorts an array in-place. "
            "Include `fn main()` that asserts a sorted slice [1, 5, 2, 8] becomes [1, 2, 5, 8], "
            "then prints OK.",
        "test_code":
            "// supplied via main()",
    },
    {
        "id": "code_rust_006", "difficulty": "hard", "category": "coding",
        "language": "rust",
        "instruction":
            "Write a Rust program defining a struct `Graph` representing a directed graph using an adjacency list, "
            "with methods `new(n: usize)`, `add_edge(&mut self, u: usize, v: usize)` and `has_cycle(&self) -> bool`. "
            "Include `fn main()` that asserts a graph with cycles returns true, and one without returns false, then prints OK.",
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
    {
        "id": "code_go_003", "difficulty": "easy", "category": "coding",
        "language": "go",
        "instruction":
            "Write a complete Go program (package main, imports, main func) with `func Reverse(s string) string` "
            "that reverses a string (ASCII only). main() should panic if Reverse(\"world\") != \"dlrow\", "
            "otherwise print OK.",
        "test_code": "// supplied via main()",
    },
    {
        "id": "code_go_004", "difficulty": "medium", "category": "coding",
        "language": "go",
        "instruction":
            "Write a complete Go program with a `SafeMap` struct that wraps a map of string to int with a `sync.RWMutex`. "
            "It should have `Get(key string) (int, bool)` and `Set(key string, val int)` methods. "
            "main() should concurrently set/get and panic on discrepancies, otherwise print OK.",
        "test_code": "// supplied via main()",
    },
    {
        "id": "code_go_005", "difficulty": "medium", "category": "coding",
        "language": "go",
        "instruction":
            "Write a complete Go program with `func BinarySearch(arr []int, target int) int` that returns the index "
            "of target in sorted slice, or -1 if not found. main() should panic on mismatch, otherwise print OK.",
        "test_code": "// supplied via main()",
    },
    {
        "id": "code_go_006", "difficulty": "hard", "category": "coding",
        "language": "go",
        "instruction":
            "Write a complete Go program with `func MergeIntervals(intervals [][]int) [][]int` that merges "
            "overlapping intervals. main() should panic if merging [[1,3],[2,6],[8,10]] does not yield "
            "[[1,6],[8,10]], otherwise print OK.",
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
    {
        "id": "code_cpp_003", "difficulty": "easy", "category": "coding",
        "language": "cpp",
        "instruction":
            "Write a complete C++ program with `bool is_anagram(std::string s1, std::string s2)` checking for "
            "anagrams (case-insensitive). main() should assert is_anagram(\"listen\", \"silent\") and "
            "!is_anagram(\"abc\", \"def\"), then print OK.",
        "test_code": "// supplied via main()",
    },
    {
        "id": "code_cpp_004", "difficulty": "medium", "category": "coding",
        "language": "cpp",
        "instruction":
            "Write a complete C++ program implementing `class StacksQueue` with `enqueue(int x)` and `dequeue() -> int` "
            "using two `std::stack`s. main() should assert sequence correctness and print OK.",
        "test_code": "// supplied via main()",
    },
    {
        "id": "code_cpp_005", "difficulty": "hard", "category": "coding",
        "language": "cpp",
        "instruction":
            "Write a complete C++ program with `int knapsack(const std::vector<int>& weights, "
            "const std::vector<int>& values, int capacity)`. main() should assert knapsack({1, 2, 3}, "
            "{60, 100, 120}, 5) == 220, then print OK.",
        "test_code": "// supplied via main()",
    },
]


ALL_MULTILANG_TASKS = (
    CODING_JS_TASKS + CODING_TS_TASKS + CODING_RUST_TASKS +
    CODING_GO_TASKS + CODING_CPP_TASKS
)
