# L3 visual world — Godot — design

Date: 2026-06-22

## Problem

Today's "world view" (the `#sim-world-viz` block in the Simulations tab,
`static/js/sim.js::renderSimWorld()`) is a single abstract icon plus a
text-summary line (e.g. "day 5 · energy 62 · money 340"). There is no
spatial representation of the world at all — agents, locations, and
relationships are invisible. This is what the earlier "Arena Universes"
audit (`docs/universes/repo-audit.md`) called L1/L2 (tick loop + systemic
depth) without an L3 (visual renderer). That audit explicitly flagged a
real game-engine L3 as "should be scoped and decided on its own, not
folded into extend Arena Universes" — this spec is that separate
decision, scoped for Godot specifically.

## Decisions made during brainstorming (not open questions anymore)

- **Phasing**: replay-first. Godot loads a *finished* run and plays its
  events back as an animation. Live (mid-run) viewing is an explicit,
  deferred phase 2 — the architecture below is built so phase 2 is "swap
  the data source," not a rewrite.
- **Scenarios**: `sims_world` and `mafia`, sharing **one Godot engine**
  via a generic renderer + small per-scenario scripts — not two separate
  Godot projects.
- **Delivery**: Godot's Web (HTML5/WASM) export, embedded in the existing
  web UI as a new tab via `<iframe>`. No separate native app to
  download/run.
- **Visual fidelity**: real, professionally-made pixel art (Kenney.nl CC0
  packs — verified free, no attribution required, commercial-use-OK:
  *Tiny Town*, *RPG Urban Pack*, *Fantasy Town Kit*, the ~60,000-asset
  *Kenney Game Assets All-in-1* bundle for top-down character sprites),
  not AI-generated sprites (AI image gen can't reliably hold a character
  consistent across walk-cycle animation frames) and not the app's
  existing flat/abstract icon style.
- **Camera**: both modes, user-toggleable — free drag/zoom/click-to-inspect,
  and a cinematic auto-camera that pans/zooms to the most recently active
  location.
- **Audio**: in scope for v1 — SFX (Kenney's CC0 *Impact Sounds* / *UI
  Audio* / *Interface Sounds* packs, verified) for actions, plus ambient
  background music. **Open item**: a specific Kenney *music* (not SFX)
  pack hasn't been verified yet the way the SFX packs have — first
  implementation step is confirming a real CC0 ambient track exists
  before depending on it; if none fits, fall back to SFX-only for v1
  rather than use an unverified source.

## Architecture

One new top-level directory, `godot_world/` — a Godot 4.x project,
independent of the Python package, talking to the existing FastAPI app
only over HTTP (no new coupling into `ollama_arena/simulations/`).

```
godot_world/
  project.godot
  scenes/
    world_renderer.tscn      # generic: NPCs, locations, camera, atmosphere
    action_bubble.tscn       # reusable speech/action popup above an NPC
  scripts/
    world_renderer.gd        # ticks through events, drives sprites/camera
    camera_rig.gd            # free drag/zoom + auto-cinematic mode
    scenario_handlers/
      sims_world_handler.gd  # layout_for() + on_event() for sims_world
      mafia_handler.gd       # layout_for() + on_event() for mafia
  assets/
    kenney_tiny_town/        # CC0, vendored (license file included)
    kenney_rpg_urban/
    kenney_characters/
    kenney_audio/
  export/                    # build output -> copied to static/godot/
```

**The shared contract** every scenario handler implements:

```gdscript
# layout_for(agent_ids: Array, statuses: Dictionary) -> Dictionary
#   Returns {agent_id: Vector2} plus {location_id: Vector2} -- computed
#   deterministically from the data itself (agent count, home_id/job
#   identities, mafia seat order), never from the backend. The Python
#   simulation has no concept of x/y and never will -- this keeps
#   `simulations/scenarios/*.py` completely unaware that Godot exists.
#
# on_event(event: Dictionary) -> void
#   event = {tick, kind, payload, actor_id, visibility} -- the exact
#   shape /api/sim/run/{id}/trace already returns. Maps kind -> a visual
#   reaction: "worked" -> walk-to-job + hammer-icon bubble, "spent" ->
#   coin-sparkle, "conflicted"/"socialized" -> walk-to-target + bubble,
#   "agent_died" -> fade-out, Mafia's "vote"/"night_kill"/"speak" ->
#   bubble + (for night_kill) only rendered to clients that the event's
#   own `visibility` field says can see it.
```

`world_renderer.gd` owns ticking through the loaded event list, calling
the active handler's `on_event()` per event in order, and owns the
NPC/location sprite pool. It does not know what "Mafia" or "sims_world"
mean -- adding a third scenario later is one new handler script, not a
new project, which is the entire point of "one engine."

## Data flow

1. User clicks a new **"▶ View in 3D world"** button next to a run in the
   existing Run history table (`templates/index.html`, sim tab) →
   navigates to the new **"🎮 World"** tab, which sets the embedded
   iframe's `src` to `/static/godot/index.html?run_id=<id>`.
2. Inside Godot, `world_renderer.gd` reads `run_id` from the URL (Godot's
   Web export exposes `JavaScriptBridge` for this) and calls the
   **existing, unmodified** `GET /api/sim/run/{run_id}/trace` endpoint via
   an `HTTPRequest` node. No new backend route for v1.
3. `world_renderer.gd` picks the right scenario handler from `run.scenario`
   (already present in the `trace` response's `run` field), calls
   `layout_for()` once to place buildings/home-spots, then steps through
   `events` in tick order, calling `on_event()` and advancing a tick
   counter/progress bar.
4. **Phase 2 (explicitly deferred, not designed in detail here)**: swap
   the one-shot `HTTPRequest` fetch for a `WebSocketPeer` subscription to
   the same broadcast channel `static/js/ws-client.js` already listens
   to (`sim_tick` events) — `on_event()` itself doesn't change, only
   where events come from.

## Build & serving pipeline

- Godot 4.x editor/CLI is a **new one-time toolchain dependency** for
  whoever builds the export — end users never install Godot, they just
  get static files. Build command:
  `godot --headless --export-release "Web" export/index.html`
- Export output (`index.html`, `.js`, `.wasm`, `.pck`) is copied into
  `static/godot/`, served by the FastAPI app's existing `StaticFiles`
  mount (`ollama_arena/web.py`) — no new serving code.
- Kenney assets are vendored into `godot_world/assets/` with their CC0
  license files kept alongside (CC0 needs no attribution, but keeping the
  license file is good practice and answers "where did this come from"
  for anyone auditing the repo later).

## Testing

GDScript isn't exercised by pytest, so testing splits three ways:

1. **GDScript unit tests via [GUT](https://github.com/bitwes/Gut)** (the
   standard free Godot-unit-test addon) for the parts that are pure logic,
   not rendering: `layout_for()` determinism (same input → same output,
   no overlapping positions), `on_event()` dispatch (right handler called
   for the right `kind`, unknown kinds don't crash).
2. **A Python contract test** (`tests/test_sim_trace_contract.py`) pinning
   the exact shape of `/api/sim/run/{id}/trace` that Godot depends on —
   protects the Godot consumer from silent backend drift, the same
   protective role `tests/test_web_providers_api.py` already plays for
   the Providers tab.
3. **Manual QA checklist** for the inherently visual parts (walk
   animations look right, camera modes both work, day/night tint applies,
   SFX fires on the right action, no console errors) — verified live in a
   browser the same way the Providers tab was, not something pytest can
   meaningfully assert.

## Explicitly in scope for v1

- `sims_world` + `mafia` on one shared Godot renderer.
- Replay of a finished run only.
- Free + auto-cinematic camera, toggleable.
- Kenney CC0 tile/character art with real walk-cycle animation.
- Day/night (Mafia) and day-counter (sims_world) atmosphere tint.
- Action bubbles for every existing event kind (worked/rested/socialized/
  spent/conflicted/goal_set/rent_paid/rent_debt/agent_died for sims_world;
  speak/vote/night_kill/etc. for Mafia, respecting `visibility`).
- SFX for actions; ambient music if a real CC0 source is confirmed during
  implementation (see open item above), SFX-only otherwise.
- "▶ View in 3D world" entry point from the existing Run history table.

## Explicitly deferred (not silently dropped)

- **Live (mid-run) viewing** — phase 2, same architecture, different data
  source (see Data flow §4).
- **`godot_rl_agents`'s TCP bridge protocol** — that project's actual
  bridge is native-Godot-process ↔ external Python over TCP; it doesn't
  apply as-is to a browser-embedded Web export talking HTTP to the same
  origin. Its ideas (observation/action schema framing) are still a
  useful reference if a future native-app delivery path is ever chosen
  instead of Web export — not used in v1.
- **YarnSpinner-Godot** — a real, if work-in-progress (per its own
  README), dialogue-scripting engine for Godot. v1 uses simple custom
  `action_bubble.tscn` popups instead; YarnSpinner is a candidate if a
  richer branching-dialogue "narrator" experience gets built later.
- A third scenario beyond sims_world/mafia.
- Deep click-to-inspect NPC panels beyond a basic status tooltip.

## Open items to resolve at the start of implementation, not now

- Confirm a real CC0 *ambient music* track (not just SFX) from Kenney or
  an equally clearly-licensed source before relying on it.
- Confirm exact Kenney pack filenames/versions to vendor (the search this
  session confirmed the packs exist and are CC0; picking precise file
  names happens when actually downloading them).
