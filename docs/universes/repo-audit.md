# Arena Universes — Phase 1 repo audit

Date: 2026-06-22

## 1. Existing stack (what "Universes" must fit into)

- **Backend**: single Python package `ollama_arena/`, FastAPI app (`web.py`, one file, ~1600+ lines, all routes registered via an app-factory closure), SQLite storage (`storage/sqlite/*`, a hand-rolled connection-pool layer, no ORM), stdlib-dataclass schemas (no pydantic in the simulation layer specifically — see `simulations/core/action_schema.py`'s own docstring on why).
- **Frontend**: server-rendered Jinja templates (`templates/*.html`) + vanilla JS per-feature files (`static/js/*.js`, e.g. `match.js`, `spec.js`, `sim.js`, `genome.js`) + a single shared websocket (`ws-client.js`'s `connectWS()`) that dispatches by `event.type` prefix (`sim_*` already bypasses the per-job gate — see `handleWSEvent`/`handleSimWSEvent`). No SPA framework, no bundler.
- **CLI**: `argparse`-based, one subcommand tree in `cli/__init__.py`, delegating to `cli/<name>_cmd.py` modules.
- **Model/provider abstraction**: `backends/{ollama,openai_compat,anthropic,spec,transformers_backend}.py`, all implementing the same `generate()/generate_with_tools()/chat_turn()` shape (`backends/base.py`'s `Backend` protocol). This is the correct, already-proven integration point for "model controls an agent" — every existing feature (Arena Match, agent tools, simulations) goes through it.
- **Memory-aware scheduling**: `memory_scheduler.py` (CONCURRENT/HOT_SWAP/PIPELINE strategy, real RAM math, `unload_all_except()`). Already load-bearing for the rest of the app and **just proved necessary this session** for the simulations engine too (see §3).
- **Existing simulation engine**: `ollama_arena/simulations/` — **this is the critical finding, see §2.**

## 2. A simulations engine already exists — this changes the plan

The repo already has a complete, tested, working multi-agent simulation subsystem (committed this session, `da0b7ed`):

```
simulations/
  core/      action_schema.py, runner.py (SimulationManager: create/start/pause/resume),
             scenario.py, types.py, world.py (abstract World: observe/step_turn_based/
             step_simultaneous/checkpoint)
  agents/    base.py (SimAgent), llm_agent.py (LLMSimAgent: prompt-build -> backend.generate
             -> parse_action, retry-once-then-forfeit), profile.py
  scenarios/ rps.py, mafia.py, sims_world.py, game_playing.py, educational.py,
             sandbox_universe.py
  eval/      scoring.py, compare.py
  replay/    player.py
  training/  buffer.py, dataset.py, gpu.py, imitation.py, policy.py, selfplay.py
  world/     economy.py, entities.py, relationships.py
  storage.py (SimStore: SQLite, events/transitions/checkpoints/metrics, witness-filtered)
```

Mapped against the requested feature list, this **already covers most of L1 and a real slice of L2**:

| Requested (§3) | Already exists |
|---|---|
| locations/zones, agents w/ needs/goals/inventory/money/relationships/memory | `sims_world.py` (`NPCStatus`, `RelationshipGraph`, day-tick needs/jobs/money) |
| world tick loop, deterministic seedable sim | `runner.py`'s `start_run(max_ticks=...)`, `world.reset(seed=...)` |
| hidden information / witness-filtered events | `core/world.py` + `Event.witness_ids` (used by `mafia.py`) |
| replay logs | `replay/player.py`, `SimStore` event/transition log |
| scoring/evaluation | `eval/scoring.py`, `eval/compare.py`, per-scenario `ScenarioScorer` |
| checkpoint/resume (= pause/play) | `runner.py`'s `pause_run`/`resume_run` + `save_checkpoint` |
| model-vs-model in the same world | any `AgentSpec.model` already differs per agent; proven this session with 3 different models in one Mafia run |
| Arena UI integration | dashboard "Simulations" tab (`templates/index.html`, `static/js/sim.js`), live tick feed over the shared websocket |
| imitation/self-play training | `training/{imitation,selfplay,buffer,dataset}.py` (exists, not deeply audited this pass) |

**What's genuinely missing relative to the L2/L3 ask:** time-of-day/calendar granularity beyond a day-tick, an explicit economy with prices/wages/rent as first-class entities (sims_world has money/jobs but not a full economy ledger), a scenario/world *editor* UI (currently scenarios are Python classes, not data-authored), a behavior-tree/utility-AI planner (currently a single-shot prompt -> JSON action, no multi-step planning), long-term vector-backed memory (current memory = full witnessed-event history, unbounded, no embedding retrieval), and **all of L3** (no renderer, no map, no sprites/animation states — this is real, ~0% built).

**Implication for the plan:** building a parallel "Universes" stack as the original brief's §4.1 (11 new top-level modules: `universe-core`, `universe-domain`, `universe-engine`, ... `universe-l3-visual`, `universe-hub-pack`) would duplicate `simulations/` almost entirely and leave two competing simulation systems in one app — directly against the brief's own "do not rewrite", "preserve existing flows", "match existing codebase style" rules, and against this repo's actual flat-package convention (no service-style `name-core`/`name-domain` splitting exists anywhere else in the repo; `backends/`, `simulations/`, `agentic/`, `p2p/` are all single flat packages). **Recommendation: extend `simulations/` in place** (new scenario(s), a richer `sims_world`-style economy/calendar layer for L2, a new `simulations/visual/` or `simulations/l3/` adapter for L3) rather than introduce a second, parallel "Universes" package tree. Naming ("Universes" as the user-facing dashboard tab name vs. `simulations` as the Python package name) can stay split, the way "Arena Match" the UI feature and `arena.py` the module already differ.

## 3. Hard constraint discovered this session: local hardware

`OLLAMA_MAX_LOADED_MODELS=1` on this machine. Any scenario where different agents use different models forces a full model reload every turn. This was the actual root cause of "simulations don't run" (fixed this session via bounded `num_predict`/`num_ctx`, commit `da0b7ed`). **Any L2/L3 plan that assumes many agents each thinking every tick with their own model is not viable on this hardware as designed** — real-time visual ticking (§5.1, §6.1 "real-time" mode) with several different-model agents will thrash exactly like the pre-fix Mafia run did. This needs an explicit mitigation in the plan (e.g. reduced cognition frequency for background agents, as the brief's own §13 already anticipates — "support for reduced cognition frequency for background NPCs" is the right call, but must be load-bearing from day one, not a later optimization).

## 4. Local cloned-repo inventory

`~/ALL_CLONED_REPOS.md` exists and is current (generated today). Relevant non-noise entries (excluding IDE plugin caches, security tooling unrelated to this task):

| Repo | What it is | License | Relevance | Verdict |
|---|---|---|---|---|
| `arena-world-plus/agentsociety` (374M) | LLM agents in society (Tsinghua), Python, full social/economic sim | Apache-2.0 | Closest real match to the L2 ask (economy, social graph, LLM-driven residents) | **Ideas only.** Own DB/runtime/config model, would mean running a second framework alongside `simulations/`, not adapting it. Read its agent-cognition pipeline and economy model for design ideas (same "rewrite in own words" pattern already used for Mafia this session), do not embed it. |
| `arena-max-repos/GPTeam` | Multi-agent simulation w/ goals (LangChain-era) | MIT | Cognition-pipeline ideas (perception -> plan -> act -> reflect, same shape the brief's §5.3 asks for) | **Ideas only**, same reasoning. |
| `arena-world-plus/worldsim` (6.5M) | Tick-based multi-agent community/policy simulator | check repo (not yet confirmed) | Conceptually closest to L1's "world tick loop + agents reasoning + relationships" — but **TypeScript/Node**, this app is Python | **Ideas only** — different language rules out direct reuse regardless of license. |
| `arena-max-repos/mem0` | Maintained PyPI memory layer (`pip install mem0`) | Apache-2.0 | Directly addresses §5.5's "optional vector-backed retrieval" | **Real candidate as a pip dependency** if/when long-term vector memory is actually built (not needed for L1, a clear L2+ item) — this is the one entry on this list that's a legitimate "add as dependency," not "copy code." |
| `arena-world-plus/open_spiel` | DeepMind RL-for-games framework, Python | Apache-2.0 | Game-theoretic eval ideas (useful for `eval/scoring.py` if formalizing win conditions) | Ideas only, low priority. |
| `arena-world-plus/{carla, airsim, ProjectAirSim, habitat-lab, habitat-sim, SimWorld, SimWorld-Studio, Torque2D, DI-engine, alien, spring}` | Heavyweight robotics/3D/game-engine simulators (Unreal/Unity/C++-based, several GB each) | mixed | These are what a *true* L3 (real 3D rendered world) would eventually want | **Not viable to integrate into this stack** (FastAPI + vanilla JS, no game engine, no 3D runtime) without effectively building a second application and embedding/streaming it in — far beyond "extend Arena." Flag as future/aspirational only; not part of any near-term plan. |

**No entry on this list should be directly vendored or pip-installed without a separate go-ahead** — this matches the explicit decision made earlier this session (Mafia improvements: "ideas/algorithms only, rewrite in own words," after raising license/security concerns about vendoring). The current request's brief reopens "directly integrate" as an option; recommend keeping the stricter rule unless the user explicitly overrides it again, given how much heavier these particular repos are than the small Mafia-research case.

## 5. Risks / unknowns

- **Scope**: the full brief (L1+L2+L3 + editor + visual renderer + hub/pack format + benchmark integration) is a multi-week-to-multi-month effort, not a single session. Claiming otherwise would produce exactly the "fake scaffolding" / "toy demo" the brief explicitly forbids.
- **L3 in this stack**: no game engine, no canvas/WebGL renderer currently exists anywhere in `static/js/`. A real L3 (even 2D top-down) is a genuinely new frontend capability, not an extension of existing patterns — needs its own design pass before any code.
- **Naming**: the brief asks for a final decision among "Arena Universes / Arena LifeSim / Arena Worlds" based on repo convention. Existing UI tab names are short nouns ("Genome", "Spec Decode", "Simulations") — "Universes" fits that pattern best of the three.
- **Duplication risk**: building net-new `universe-*` modules instead of extending `simulations/` is the single biggest risk identified — see §2.
