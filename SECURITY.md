# Ollama Arena — Security Posture

This document records the defenses applied to Ollama Arena and the audit results.
Keep it current whenever a security-relevant change lands.

## 1. Sandboxed code execution (Zero Trust Execution)

- **AST validator** (`ollama_arena/sandboxes/security.py`)
  - Rejects imports of: `os, sys, subprocess, shutil, pty, signal, resource,
    socket, urllib, requests, http, asyncio, pickle, marshal, ctypes,
    importlib, builtins, threading, multiprocessing, gc, inspect, paramiko, …`
  - Rejects calls to: `eval, exec, compile, getattr, setattr, delattr, hasattr,
    globals, locals, vars, dir, __import__, open, breakpoint, input, type, …`
  - Rejects every dunder attribute access (`__class__`, `__mro__`,
    `__subclasses__`, `__globals__`, `__builtins__`, `__base__`, `__dict__`,
    `__code__`, `__getitem__`, `__reduce__`, …) except `__name__`, `__main__`,
    `__doc__`, `__init__`
  - Rejects subscript dunder lookups (`x["__builtins__"]`)
  - Caps source size at 256 KiB

- **Docker container** (`_run_in_docker`)
  - `--network=none`
  - `--cap-drop=ALL`
  - `--security-opt=no-new-privileges`
  - `--security-opt seccomp=…/seccomp.json` — explicit deny-list of
    `mount, ptrace, kexec_*, perf_event_open, pivot_root, swapon, reboot,
     userfaultfd, bpf, clone3, …`
  - `--memory 512m --memory-swap 512m` (no swap)
  - `--cpus 0.5`
  - `--pids-limit 64` (fork-bomb defense)
  - `--ulimit nofile=128 nproc=64`
  - `--read-only` rootfs + `tmpfs=/tmp:noexec,nosuid,size=64m`
  - `--user 65534:65534` (`nobody`)

## 2. Web / API hardening

| Defense | Implementation | Default |
|---|---|---|
| CORS allowlist | `_ALLOWED_ORIGINS` env, no `*` by default | localhost only |
| Rate limit `/api/match` | slowapi, per-IP | `2/minute` |
| Rate limit `/api/tournament` | slowapi, per-IP | `1/minute` |
| Rate limit `/api/playground/*` | slowapi, per-IP | `10/minute` |
| Rate limit `/api/spec/stream` | slowapi, per-IP | `20/minute` |
| Rate limit `/api/spec/start_all` | slowapi, per-IP | `1/minute` |
| Rate limit (default) | slowapi, per-IP | `120/minute` |
| WebSocket Origin check | `_ALLOWED_ORIGINS`; close 1008 on mismatch | enforced |
| CSP | `default-src 'self'` + explicit CDNs | enforced |
| `X-Frame-Options` | `DENY` | enforced |
| `X-Content-Type-Options` | `nosniff` | enforced |
| `Referrer-Policy` | `no-referrer` | enforced |
| `Permissions-Policy` | camera/geo/mic/usb/payment denied | enforced |

Override via env: `ARENA_ALLOWED_ORIGINS`, `ARENA_RL_MATCH`,
`ARENA_RL_TOURNAMENT`, `ARENA_RL_PLAYGROUND`, `ARENA_RL_SPEC_STREAM`,
`ARENA_RL_DEFAULT`.

## 3. Frontend XSS defense

- **DOMPurify 3.2.4** loaded with SRI (`sha384-eEu5CTj3qGvu9PdJuS+Ylk…`)
- `safeHTML(s)` — used on every model-derived string that becomes innerHTML
- `escText(s)` — used on every model-derived string interpolated as text
- `formatCodeBlocks(text)` — escapes first, then re-wraps fenced code, then
  runs through `safeHTML`
- All `.innerHTML` paths that touch model_a/model_b/task_id/response_*/error
  now go through `escText` or `safeHTML`

## 4. Database integrity

Audited `ollama_arena/elo.py` and `ollama_arena/performance.py`:

- 26 `.execute()` calls — all use parameterized `?` placeholders
- No f-string or `.format()` interpolation in SQL
- No `+`-concatenation of host strings into SQL (operators in SQL strings
  like `wins=wins+1` are SQL-side, not injection vectors)
- WAL mode enabled (`PRAGMA journal_mode=WAL`)
- `synchronous=NORMAL` — balanced durability/throughput

## 5. LLM-Judge prompt-injection guard

- Anti-injection preamble at start of system prompt
- Responses A/B are clamped (`max chars`) and stripped of system markers
- `temperature=0`, `max_tokens=64` (just enough for `A: N\nB: N`)
- Output JSON-shape validated; on parse failure both scores default to 0

## 6. What is NOT covered

- Distributed denial of service — slowapi is per-process. For prod put
  the arena behind a reverse proxy (nginx/Caddy) with global rate limits.
- Multi-tenant isolation — the arena assumes a single trusted operator.
- TLS — handled by the reverse proxy, not by uvicorn.

## How to verify

```bash
pytest tests/test_security.py
```
