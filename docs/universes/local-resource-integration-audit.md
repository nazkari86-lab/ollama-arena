# Local cloned-repo integration audit — Arena Universes

Date: 2026-06-22. Source of truth: `~/ALL_CLONED_REPOS.md` (generated 2026-06-21), cross-checked against `~/github_projects.txt` and direct inspection of each repo's README/size.

Decision rule applied to every entry: **integrate directly**, **wrap behind an adapter**, **ideas only (reimplemented in our own words)**, or **ignore**. Default posture carried over from this session's earlier Mafia-improvement work (explicit user decision: ideas only, no code copying, after raising license/security concerns) — anything stronger than "ideas only" is called out explicitly below and needs a separate go-ahead.

## Directly relevant (LLM-agent social/world simulation)

### `arena-world-plus/agentsociety` + `agentsociety-community` (374M, Apache-2.0)
**What**: Tsinghua FIB-lab's "AgentSociety: LLM Agents in Society" — Python framework running many LLM-driven residents through a social/economic simulation (jobs, economy, social ties).
**Why relevant**: closest existing match to the L2 "systemic living world" ask in the whole inventory.
**Verdict**: **Ideas only.** It is a complete, independent framework with its own runtime/config/storage model — adapting it would mean running it *alongside* `ollama_arena/simulations/` rather than extending it, which fails the "preserve existing flows, one cohesive subsystem" requirement. Read its agent-cognition pipeline and economy/social model for design ideas when building the L2 economy layer (same treatment already applied to the Mini-Mafia benchmark this session).
**Integrate now or later**: later, as a design reference only, when L2 economy work actually starts.

### `arena-max-repos/GPTeam` (MIT)
**What**: multi-agent simulation where GPT-driven agents collaborate toward goals (perception → plan → act → reflect loop).
**Why relevant**: its cognition loop shape matches the brief's §5.3 pipeline almost exactly.
**Verdict**: **Ideas only**, same reasoning as AgentSociety — small, MIT-licensed, low legal risk if ever copied verbatim, but the existing `LLMSimAgent.act()` already implements a (simpler) version of this loop; better to extend that in place than import a second agent-loop implementation.
**Integrate now or later**: later, if/when a multi-step planner (vs. today's single-shot decide) gets built.

### `arena-world-plus/worldsim` (6.5M, TypeScript/Node)
**What**: embeddable tick-based multi-agent simulation engine — "define a world, add agents with personalities/goals, advance tick by tick, agents reason/talk/build relationships."
**Why relevant**: conceptually the closest match to L1's tick loop of anything in the inventory.
**Verdict**: **Ideas only**, and not a close call — different language (TypeScript) than this entire codebase (Python). No direct or wrapped-adapter integration is realistic regardless of license.
**Integrate now or later**: n/a (read-only reference).

## Real dependency candidate (not "code reuse")

### `arena-max-repos/mem0` (Apache-2.0, on PyPI as `mem0`)
**What**: maintained, pip-installable "memory layer for personalized AI" — vector-backed long-term memory with retention/retrieval built in.
**Why relevant**: directly addresses §5.5's "optional vector-backed retrieval" for agent long-term memory, which the current `simulations/` engine doesn't have (memory today = full unbounded witnessed-event history passed into every prompt — flagged as a scaling concern in the earlier Mafia/llm_agent fix this session).
**Verdict**: **Legitimate dependency candidate**, not vendoring — this is the one entry where "add to `pyproject.toml`" is the right shape, same as any other PyPI package this repo already depends on. Not needed for L1 (current approach works at small scale); becomes worth adding once a scenario's event history genuinely outgrows what fits in a bounded `num_ctx` (the `_estimate_num_ctx` cap added this session will start silently truncating old history before that point — that's the actual trigger condition for "now mem0 is worth it," not a vague "later").
**Integrate now or later**: later, gated on that concrete trigger, not on a calendar date.

## Research/RL infrastructure (low priority, narrow use)

### `arena-world-plus/open_spiel` (Apache-2.0)
DeepMind's RL-for-games framework. Relevant only to `eval/scoring.py` if a scenario ever wants formal game-theoretic equilibrium analysis. **Ideas only, low priority** — nothing in the current brief needs this.

### `arena-world-plus/DI-engine` (+ `-docs`)
Decision-intelligence/RL training framework. Overlaps with `simulations/training/{selfplay,imitation,policy}.py`, which already exist and were not part of this audit's deep-dive. **Flag for a future pass**, not this one — out of scope for L1/L2/L3 itself.

## Not viable to integrate into this stack

`arena-world-plus/{carla, airsim, ProjectAirSim, habitat-lab, habitat-sim, SimWorld, SimWorld-Studio, Torque2D, alien, alien-docs, alien-world-explorer, spring, apesdk, apesdk-js, immersiveape, upq, uberserver}` — autonomous-driving sims, robotics simulators, artificial-life sandboxes, and C++/Unreal/Unity game engines, several GB each.

**Why not**: this is a FastAPI + server-rendered-Jinja + vanilla-JS web app with no game engine, no 3D runtime, no native build pipeline. Embedding any of these would mean standing up a second application (a game-engine process, likely with its own GPU/window requirements) and bridging it back into Arena over some IPC/streaming boundary — that is "build a new product," not "extend Arena," and several (CARLA, AirSim) are aimed at robotics/driving research, not life-sim visualization, so the domain fit is also weak.
**Verdict**: **Ignore** for any near-term L3 plan. If a *real* 3D/game-engine L3 is ever pursued, this list is the right starting point for *that* separate, much larger initiative — but it should be scoped and decided on its own, not folded into "extend Arena Universes."

## Explicitly out of scope for this audit

`~/impacket`, `~/security_research/*`, `~/.shadow_agent_v8/tools/*`, IDE plugin caches (`.cursor/plugins/cache/...`, `.claude/plugins/...`) — unrelated to simulation/world-engine work, not evaluated.
