# Model-size warning + emergency stop — design

Date: 2026-06-21

## Problem

The user picks two models for an Arena Match/Tournament/Royale on a laptop
with limited RAM. Two failure modes exist today:

1. The dashboard already computes whether a model pair fits in RAM
   (`/api/strategy` → CONCURRENT/HOT_SWAP/PIPELINE/INSUFFICIENT, backed by
   `memory_scheduler.py`'s real RAM math) and shows it as a passive badge
   on the Battle tab. It's easy to miss — there's no active warning when a
   risky pair is selected.
2. If the laptop genuinely starts thrashing (low RAM / heavy swap) while a
   job is mid-run, there is no way to stop everything quickly. `Stop All`
   on the Spec Decode tab only kills `llama-server` spec processes, not
   regular Ollama-served models or an in-flight arena job.

## Goals

- Warn the user immediately when they select a model pair that the
  scheduler itself considers risky (PIPELINE or INSUFFICIENT).
- Provide a single "stop everything now" action: kills Spec Decode
  servers, unloads every Ollama-loaded model from RAM, and stops the
  current job from launching further tasks.
- Auto-trigger that same stop action when the system shows real signs of
  memory thrash (low available RAM or high swap usage), with no
  confirmation step — speed matters more than avoiding a rare false
  positive, mitigated by requiring the signal to be sustained for two
  consecutive polls (~4s) before firing.
- Also expose the same action as a manual "Emergency Stop" button, always
  visible regardless of which tab is open.

## Non-goals

- Not adding cancellation to the `CONCURRENT` execution path
  (`ThreadPoolExecutor.map` over both models at once) — that mode only
  runs when both models comfortably fit per the scheduler's own math, so
  it's the least likely path to cause thrash. Left unguarded.
- Not aborting a single in-flight HTTP generate call mid-stream. Stopping
  further task iterations plus forcing `keep_alive=0` unload is enough —
  Ollama will tear down the in-flight request itself once the model is
  evicted.
- Not adding new hardware probing. Reuses `psutil.virtual_memory()` /
  `psutil.swap_memory()`, already a dependency.

## Design

### 1. Selection-time warning (toast)

`static/js/match.js`'s `previewStrategy()` already runs on every
`model-a`/`model-b` `change` event and calls `POST /api/strategy`, which
returns the scheduler's real per-pair decision. Today it only updates the
passive badge (`#strategy-badge`/`#strategy-reason`).

Change: after rendering the badge, if `d.strategy` is `PIPELINE` or
`INSUFFICIENT`, additionally call the existing `toast()` helper
(`static/js/utils.js`) with a `warning` (PIPELINE) or `error`
(INSUFFICIENT) kind and `d.reason` as the message. Non-blocking — the user
can still start the match. No new threshold logic: this reuses the
scheduler's existing pairwise fit decision rather than inventing a
second, less-accurate single-model size check.

### 2. `emergency_stop()` — single stop-everything function

New module `ollama_arena/safety.py`:

```python
STOP_REQUESTED = threading.Event()

def emergency_stop(reason: str, *, spec_manager, scheduler) -> dict:
    spec_result = spec_manager.stop_all()
    STOP_REQUESTED.set()
    unloaded = scheduler.unload_all_except([])
    return {
        "reason": reason,
        "spec_stopped": spec_result,
        "models_unloaded": unloaded,
        "ts": time.time(),
    }
```

`STOP_REQUESTED` is a process-wide flag. It is cleared at the start of
every new job (`/api/match`, `/api/tournament`, `/api/royale` handlers in
`web.py`, right where `jobs[jid] = {...}` is first set) so a stop from a
previous job doesn't block a new one the user deliberately starts
afterward.

### 3. Cooperative cancellation of the running job

`arena.py` has four sequential per-task loop sites that matter for
runaway memory growth:

- `_execute_pipelined`'s phase-1 loop (all tasks vs model A)
- `_execute_pipelined`'s phase-2 loop (all tasks vs model B)
- `HOT_SWAP`'s `[_execute_hotswap(t) for t in tasks]` (convert to an
  explicit `for` loop)
- `run_tournament`/`run_royale`'s sequential task loops

Each gets a check at the top of the iteration:

```python
if safety.STOP_REQUESTED.is_set():
    break
```

This stops the job from launching further generate calls. The job's
`status` is then set to `"stopped"` (new status value, alongside existing
`"done"`/`"error"`) so the frontend can distinguish "stopped early" from
"finished".

`CONCURRENT` mode (`ThreadPoolExecutor.map`) is intentionally left
without a cancellation check — see Non-goals.

### 4. Background lag monitor

A daemon thread started once at app startup (alongside other
already-running background pieces in `web.py`'s app-factory):

- Polls every 2s:
  - `psutil.virtual_memory().available` — danger threshold reuses
    `memory_scheduler._OS_RESERVE_GB` (1.5 GB) as the floor: below that,
    the OS itself is short on the margin it needs to stay responsive.
  - `psutil.swap_memory().percent` — new env-tunable threshold,
    `ARENA_MEM_SWAP_DANGER_PCT`, default `60`.
- Requires the breach to be true on **two consecutive polls** (~4s
  sustained) before acting, to avoid firing on a single brief spike (e.g.
  a short-lived OS background task).
- On a sustained breach: calls `emergency_stop(reason="auto: low_ram"` or
  `"auto: swap")` directly (no confirmation, per the decision above), then
  broadcasts `{"type": "system_alert", **result}` over the existing
  `ConnectionManager.broadcast()` websocket.
- After firing, the monitor requires RAM/swap to drop back under
  threshold before it can fire again (simple re-arm condition), so it
  doesn't spam repeated stops while the system is still recovering.

### 5. Manual trigger endpoint

`POST /api/emergency_stop` in `web.py` — calls
`safety.emergency_stop("manual", spec_manager=_spec_manager,
scheduler=arena.scheduler)` and returns the result dict. No rate limiter:
this is a safety action and must always be available.

### 6. Frontend wiring

- `templates/index.html`/`base.html`: add a `🛑 Emergency Stop` button to
  the persistent header (visible from every tab, not inside any
  tab-content panel).
- `static/js/bootstrap.js`: wire the button via `addEventListener` (CSP
  rules out inline `onclick`, matching every other button on this
  dashboard) to `POST /api/emergency_stop`, then `toast()` the result.
- `static/js/ws-client.js`: `system_alert` events must be handled **before**
  the existing `if (d.job_id === currentJobId)` gate in `connectWS()`'s
  `onmessage`, the same way `sim_`-prefixed events already bypass that
  gate — an auto-triggered stop must reach the UI even if the user isn't
  looking at the tab of the job that got stopped. On receipt: show a
  banner (reusing the `_showOllamaWarning`-style fixed-position banner
  pattern) — "⚠️ System overload detected — all models stopped
  automatically" for `reason` starting with `auto:`, or "🛑 Stopped
  manually" otherwise — then call `loadModels()` and (if on the Genome
  tab) re-trigger a hardware scan so the UI doesn't keep showing
  now-unloaded models as loaded.

## Testing

- `safety.py`: unit tests for `emergency_stop()` (mocked
  spec_manager/scheduler) verifying it calls both `stop_all()` and
  `unload_all_except([])` and sets `STOP_REQUESTED`.
- `arena.py`: tests that `STOP_REQUESTED.set()` before a pipelined/hotswap
  /tournament/royale run causes it to stop after the first task with
  `status == "stopped"`, and that results before the break point are
  preserved.
- `web.py`: route test for `POST /api/emergency_stop` (mocked
  spec_manager/scheduler) asserting the response shape; test that
  starting a new job via `/api/match` clears `STOP_REQUESTED`.
- Monitor thread: tested as a pure function (`_check_thresholds(avail_gb,
  swap_pct, consecutive_breaches) -> bool`) rather than testing the real
  sleep loop, so the hysteresis logic is verified without real timing.
- Frontend: no existing JS test harness in this repo for `match.js`/
  `ws-client.js` (verified via `tests/` — all Python); the live
  browser-verification step from the prior CSP/button-wiring work applies
  here too — click the Emergency Stop button live and confirm a toast +
  model-list refresh, not just absence of console errors.

## Open items deliberately left for the implementation plan

- Exact CSS placement/styling of the header button and the alert banner
  (follow existing header layout and `_showOllamaWarning` banner styling).
- Whether `swap_memory()` is reliable enough in the sandboxed test
  environment to assert real values (likely needs mocking `psutil` in
  tests, consistent with how `telemetry/bandwidth.py`'s tests already mock
  psutil elsewhere in this repo).
