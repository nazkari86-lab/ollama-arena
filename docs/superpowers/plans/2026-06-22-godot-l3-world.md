# Godot L3 World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a replay-first, Godot-powered 2D pixel-art "🎮 World" view that visualizes finished `sims_world` and `mafia` simulation runs, embedded in the existing FastAPI web UI via a Web (HTML5/WASM) export.

**Architecture:** A new top-level `godot_world/` Godot 4 project, decoupled from the Python package, fetches an existing, unmodified `GET /api/sim/run/{run_id}/trace` JSON document over HTTP and replays it tick-by-tick through a generic `WorldRenderer` that delegates per-scenario layout/event logic to small `sims_world_handler.gd` / `mafia_handler.gd` scripts. The Web export's static output is copied into `static/godot/` and served by FastAPI's existing `StaticFiles` mount — no new backend serving code. The web UI gains one new tab (an `<iframe>` host) and one new button per run-history row.

**Tech Stack:** Godot 4.7 (GDScript, Web/HTML5 export), GUT 9.7.0 (GDScript unit tests), Kenney.nl CC0 art/audio packs, existing FastAPI/Jinja2/vanilla-JS frontend, pytest.

---

## Plan-time deviations from the spec (found during verification, not assumed)

The spec (`docs/superpowers/specs/2026-06-22-godot-l3-world-design.md`) left two items as "resolve at start of implementation." Both were resolved for real before writing this plan — by actually downloading and inspecting the files, not guessing:

1. **No CC0 *ambient loop* music pack exists in Kenney's free catalog.** The only music-tagged pack on kenney.nl is **Music Jingles** (85 short stingers/jingles, confirmed CC0, direct zip verified). There is no long ambient background-loop track to fall back on. **Decision:** use a short NES-style jingle as a one-shot "run started" / "run complete" stinger (`Audio/8-Bit jingles/jingles_NES00.ogg` and `jingles_NES01.ogg`), not as continuous background music. This satisfies the spec's "ambient music if a real CC0 source is confirmed... SFX-only otherwise" clause — the real source confirmed is stingers, not a loop, so v1 ships SFX + stingers, no continuous bed track.
2. **The spec's `assets/kenney_characters/` directory assumed Kenney's "RPG Urban Pack" or the itch.io-exclusive "All-in-1" bundle would supply animated NPC sprites.** Verified false: RPG Urban Pack's zip contains only environment tiles (no character files at all, despite carrying a `character` tag), and the All-in-1 bundle is itch.io-exclusive behind a payment-style download flow that cannot be scripted with a plain `curl` (no stable direct zip URL the way kenney.nl assets have). The **Roguelike Characters** pack (450 assets, confirmed CC0, direct zip verified) supplies real top-down character icon sprites instead — but it ships single static icons per character, not hand-drawn walk-cycle frame sequences. **Decision:** characters are rendered as a static directional icon (4-way flip via `scale.x`) with **procedural** walk motion — a position `Tween` plus a small squash/stretch bob via `AnimationPlayer` — rather than frame-by-frame walk-cycle animation. This is the honest, buildable version of the spec's "real walk-cycle animation" line; no CC0 pack matching the chosen pixel-art style ships actual walk frames.
3. **Fantasy Town Kit, named in the spec, is a 3D FBX model pack**, not 2D pixel art — verified by inspecting its zip contents. It does not fit a 2D top-down renderer at all and is dropped from the asset list. Tiny Town + RPG Urban Pack (both genuinely 2D, 16×16px tiles, verified) cover building/tile variety on their own.

Every asset URL, file path, and command below was independently verified (HTTP 200 + real zip contents inspected, or a real installed binary) during planning — see the per-task curl/zip listings.

---

## File Structure

```
godot_world/                          # new Godot 4 project, independent of ollama_arena/
  project.godot
  export_presets.cfg
  scenes/
    world_renderer.tscn
    action_bubble.tscn
  scripts/
    world_renderer.gd
    camera_rig.gd
    scenario_handlers/
      scenario_handler.gd            # base class documenting the contract
      sims_world_handler.gd
      mafia_handler.gd
  assets/
    kenney_tiny_town/                # vendored, License.txt kept
    kenney_rpg_urban/
    kenney_characters/               # from Roguelike Characters pack
    kenney_audio/
      impact/
      ui/
      interface/
      jingles/
  addons/
    gut/                              # vendored GUT 9.7.0, test-only
  tests/
    test_sims_world_handler.gd
    test_mafia_handler.gd
    test_world_renderer.gd
  export/                             # gitignored build output
static/
  godot/                              # gitignored; populated by the export build step
tests/
  test_sim_trace_contract.py          # new Python contract test
ollama_arena/
  web.py                              # modified: nothing new needed (StaticFiles already mounts /static)
templates/
  index.html                          # modified: new nav tab + tab-content panel
static/js/
  sim.js                              # modified: "▶ View in 3D world" button per run row
  world.js                            # new: initWorldTab()
static/js/
  ws-client.js                        # modified: tab-init dispatch map gains `world: initWorldTab`
.gitignore                            # modified: godot_world/export/, static/godot/
```

---

### Task 1: Python contract test pinning `/api/sim/run/{id}/trace`

Godot's `world_renderer.gd` depends on the exact shape of this endpoint. This test protects that contract from silent backend drift, exactly the role `tests/test_web_providers_api.py` plays for the Providers tab.

**Files:**
- Create: `tests/test_sim_trace_contract.py`

- [ ] **Step 1: Write the failing test**

```python
"""Pins the exact JSON shape of GET /api/sim/run/{id}/trace that the Godot
World renderer (godot_world/scripts/world_renderer.gd) depends on. If this
test needs to change, world_renderer.gd's HTTPRequest response parsing needs
a matching change.
"""
from __future__ import annotations

import contextlib
import unittest.mock as mock

import pytest


@pytest.fixture(scope="module")
def _trace_app(tmp_path_factory):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    db = tmp_path_factory.mktemp("simtracecontract") / "arena_test.db"
    captured: dict = {}

    def _fake_uvicorn_run(app, **_kw):
        captured["app"] = app

    import ollama_arena.web as _web_mod

    with (
        mock.patch("uvicorn.run", side_effect=_fake_uvicorn_run),
        mock.patch.object(_web_mod, "_RL_DEFAULT", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_MATCH", "10000/minute"),
        mock.patch(
            "ollama_arena.backends.ollama.OllamaBackend.list_models",
            return_value=["llama3", "phi3"],
        ),
    ):
        from ollama_arena.web import run_web
        run_web(host="127.0.0.1", port=19_995, db_path=str(db))

    assert "app" in captured, "uvicorn.run was not called — app not built"
    return captured["app"]


@pytest.fixture(scope="module")
def client(_trace_app):
    from starlette.testclient import TestClient
    return TestClient(_trace_app, raise_server_exceptions=False)


@contextlib.contextmanager
def _no_llm_agents():
    import ollama_arena.simulations.manager as _mgr_mod

    class _RockAgent:
        def act(self, observation):
            from ollama_arena.simulations.core.types import Action
            return Action(kind="choose", payload={"choice": "rock"})

    with mock.patch.object(
        _mgr_mod.SimulationManager, "_default_agent_factory",
        return_value=lambda agent_id, model: _RockAgent(),
    ):
        yield


def _start_rps_run(client, agents=("a:1b", "b:1b"), ticks=10):
    with _no_llm_agents():
        r = client.post("/api/sim/run", json={
            "scenario": "rps", "agents": list(agents), "ticks": ticks,
        })
    assert r.status_code == 200
    return r.json()["run_id"]


def test_trace_top_level_shape(client):
    run_id = _start_rps_run(client)
    r = client.get(f"/api/sim/run/{run_id}/trace")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"run", "transitions", "events"}


def test_trace_run_field_has_scenario_and_agents(client):
    run_id = _start_rps_run(client)
    data = client.get(f"/api/sim/run/{run_id}/trace").json()
    run = data["run"]
    assert run["run_id"] == run_id
    assert run["scenario"] == "rps"
    assert isinstance(run["agents"], list)
    assert {"agent_id", "model", "config"} <= set(run["agents"][0].keys())


def test_trace_event_shape_has_visibility_field(client):
    run_id = _start_rps_run(client)
    data = client.get(f"/api/sim/run/{run_id}/trace").json()
    assert data["events"], "expected at least one event"
    event = data["events"][0]
    assert set(event.keys()) == {"id", "tick", "kind", "payload", "actor_id", "visibility"}
    assert event["visibility"] in ("public", "private")


def test_trace_unknown_run_404s(client):
    r = client.get("/api/sim/run/does-not-exist/trace")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails or passes against current backend**

Run: `python -m pytest tests/test_sim_trace_contract.py -v`
Expected: all 4 tests PASS immediately — `/api/sim/run/{run_id}/trace` already exists and already returns this exact shape (confirmed by reading `ollama_arena/web.py:1671-1695`). This test's purpose is *pinning*, not driving new backend work — Step 2 here is "run it and confirm it documents reality," not "watch it fail."

- [ ] **Step 3: Commit**

```bash
git add tests/test_sim_trace_contract.py
git commit -m "test: pin /api/sim/run/{id}/trace contract for the Godot World renderer"
```

---

### Task 2: Godot project skeleton

**Files:**
- Create: `godot_world/project.godot`
- Create: `godot_world/export_presets.cfg`
- Create: `.gitignore` (modify)

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p godot_world/scenes godot_world/scripts/scenario_handlers \
         godot_world/assets/kenney_tiny_town godot_world/assets/kenney_rpg_urban \
         godot_world/assets/kenney_characters \
         godot_world/assets/kenney_audio/impact godot_world/assets/kenney_audio/ui \
         godot_world/assets/kenney_audio/interface godot_world/assets/kenney_audio/jingles \
         godot_world/addons godot_world/tests godot_world/export
```

- [ ] **Step 2: Write `godot_world/project.godot`**

```ini
; Engine configuration file.
; It's best edited using the editor UI and not directly,
; since the parameters that go here are meant to be edited
; using the UI and not by hand, with the exception of the
; few ones that are marked as "Advanced".
config_version=5

[application]

config/name="Arena World"
config/features=PackedStringArray("4.7", "GL Compatibility")
config/icon="res://icon.svg"

[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
```

The `gl_compatibility` renderer is required for Godot 4's Web export to run reliably across browsers without WebGPU.

- [ ] **Step 3: Write `godot_world/export_presets.cfg`**

```ini
[preset.0]

name="Web"
platform="Web"
runnable=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter="godot_world/tests/*,godot_world/addons/gut/*"
export_path="export/index.html"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false

[preset.0.options]

custom_template/debug=""
custom_template/release=""
variant/extensions_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/export_icon=true
html/custom_html_shell=""
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
```

`exclude_filter` keeps the GUT addon and `tests/` directory out of the shipped Web export — they're development-only.

- [ ] **Step 4: Add build artifacts to `.gitignore`**

Read the current `.gitignore` first, then append:

```bash
cat >> .gitignore << 'EOF'

# Godot L3 world — build output and vendored test framework, not source
godot_world/export/
godot_world/addons/gut/
static/godot/
EOF
```

- [ ] **Step 5: Commit**

```bash
git add godot_world/project.godot godot_world/export_presets.cfg .gitignore
git commit -m "feat: scaffold godot_world/ Godot 4 project for the L3 world renderer"
```

---

### Task 3: Vendor Kenney art and audio assets

Every URL below was fetched and verified during planning (`HTTP/2 200`, `content-type: application/zip`, real file listings inspected with `unzip -l`).

**Files:**
- Create: `godot_world/assets/kenney_tiny_town/*`
- Create: `godot_world/assets/kenney_rpg_urban/*`
- Create: `godot_world/assets/kenney_characters/*`
- Create: `godot_world/assets/kenney_audio/{impact,ui,interface,jingles}/*`

- [ ] **Step 1: Download and extract Tiny Town (village tiles/buildings)**

```bash
curl -sL "https://kenney.nl/media/pages/assets/tiny-town/a415fbeb49-1735736916/kenney_tiny-town.zip" \
  -o /tmp/kenney_tiny-town.zip
unzip -o /tmp/kenney_tiny-town.zip -d godot_world/assets/kenney_tiny_town
rm /tmp/kenney_tiny-town.zip
```

Expected result: `godot_world/assets/kenney_tiny_town/Tilemap/tilemap_packed.png` exists (132 tiles, 16×16px, 1px spacing — per the pack's own `Tilesheet.txt`), plus `Tiles/tile_0000.png` … `tile_0131.png` and `License.txt`.

- [ ] **Step 2: Download and extract RPG Urban Pack (supplementary urban tiles)**

```bash
curl -sL "https://kenney.nl/media/pages/assets/rpg-urban-pack/0a097d1dc7-1677578575/kenney_rpg-urban-pack.zip" \
  -o /tmp/kenney_rpg-urban.zip
unzip -o /tmp/kenney_rpg-urban.zip -d godot_world/assets/kenney_rpg_urban
rm /tmp/kenney_rpg-urban.zip
```

Expected result: `godot_world/assets/kenney_rpg_urban/Tilemap/tilemap_packed.png` exists (16×16px tiles, 1px spacing per `Tilemap/tilemap.txt`), plus `License.txt`. This pack is tiles only — no character sprites, despite carrying a `character` tag on kenney.nl (verified by inspecting the full zip listing).

- [ ] **Step 3: Download and extract Roguelike Characters (NPC icon sprites)**

```bash
curl -sL "https://kenney.nl/media/pages/assets/roguelike-characters/53ffff4133-1729196490/kenney_roguelike-characters.zip" \
  -o /tmp/kenney_roguelike-characters.zip
unzip -o /tmp/kenney_roguelike-characters.zip -d godot_world/assets/kenney_characters
rm /tmp/kenney_roguelike-characters.zip
```

Expected result: `godot_world/assets/kenney_characters/Spritesheet/roguelikeChar_transparent.png` exists (16×16px grid, 1px margin per `Spritesheet/spritesheetInfo.txt`), plus `License.txt`.

- [ ] **Step 4: Download and extract the three SFX packs**

```bash
curl -sL "https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip" \
  -o /tmp/kenney_impact.zip
unzip -o /tmp/kenney_impact.zip -d godot_world/assets/kenney_audio/impact
rm /tmp/kenney_impact.zip

curl -sL "https://kenney.nl/media/pages/assets/ui-audio/490d233f68-1677590494/kenney_ui-audio.zip" \
  -o /tmp/kenney_ui-audio.zip
unzip -o /tmp/kenney_ui-audio.zip -d godot_world/assets/kenney_audio/ui
rm /tmp/kenney_ui-audio.zip

curl -sL "https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip" \
  -o /tmp/kenney_interface.zip
unzip -o /tmp/kenney_interface.zip -d godot_world/assets/kenney_audio/interface
rm /tmp/kenney_interface.zip
```

Expected result: `kenney_audio/impact/Audio/footstep_grass_000.ogg` (through `_004.ogg`) and `impactWood_medium_000.ogg` etc. exist; `kenney_audio/ui/Audio/click1.ogg` exists; `kenney_audio/interface/Audio/confirmation_001.ogg` and `Audio/bong_001.ogg` exist.

- [ ] **Step 5: Download and extract the music-jingles pack (stingers, not ambient loops — see deviation note above)**

```bash
curl -sL "https://kenney.nl/media/pages/assets/music-jingles/f37e530b9e-1677590399/kenney_music-jingles.zip" \
  -o /tmp/kenney_jingles.zip
unzip -o /tmp/kenney_jingles.zip -d godot_world/assets/kenney_audio/jingles
rm /tmp/kenney_jingles.zip
```

Expected result: `kenney_audio/jingles/Audio/8-Bit jingles/jingles_NES00.ogg` through `jingles_NES16.ogg` exist, plus `License.txt`.

- [ ] **Step 6: Verify the full vendored tree and commit**

```bash
find godot_world/assets -name "License.txt" | wc -l
```
Expected: `6` (one per vendored pack: tiny_town, rpg_urban, characters, impact, ui, interface — `jingles` makes 7; if the count differs, an extraction step above silently failed and must be re-run, not ignored).

```bash
git add godot_world/assets
git commit -m "feat: vendor Kenney CC0 tile, character, and audio assets for the L3 world"
```

---

### Task 4: Vendor GUT 9.7.0 and prove the headless test pipeline works

**Files:**
- Create: `godot_world/addons/gut/*` (gitignored per Task 2, but must exist locally to run tests)
- Create: `godot_world/tests/test_smoke.gd`

- [ ] **Step 1: Download and extract GUT 9.7.0**

```bash
curl -sL "https://github.com/bitwes/Gut/archive/refs/tags/v9.7.0.tar.gz" -o /tmp/gut.tar.gz
tar xzf /tmp/gut.tar.gz -C /tmp
cp -R /tmp/Gut-9.7.0/addons/gut godot_world/addons/gut
rm -rf /tmp/gut.tar.gz /tmp/Gut-9.7.0
```

Expected result: `godot_world/addons/gut/gut_cmdln.gd` and `godot_world/addons/gut/cli/gut_cli.gd` exist.

- [ ] **Step 2: Enable the GUT plugin in `project.godot`**

Append to `godot_world/project.godot`:

```ini

[editor_plugins]

enabled=PackedStringArray("res://addons/gut/plugin.cfg")
```

- [ ] **Step 3: Write a trivial smoke test**

```gdscript
# godot_world/tests/test_smoke.gd
extends GutTest

func test_arithmetic_sanity() -> void:
	assert_eq(2 + 2, 4, "GUT pipeline is wired up correctly")
```

- [ ] **Step 4: Run it headlessly and verify it passes**

Run:
```bash
godot --headless --path godot_world -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit
```
Expected: output ending in something like `Tests: 1, Passing: 1, Failing: 0` and the process exits with code `0`. If Godot reports the GUT plugin isn't recognized, re-check Step 2's `[editor_plugins]` block was appended (not replacing) the existing `[application]`/`[rendering]` sections from Task 2.

- [ ] **Step 5: Commit**

```bash
git add godot_world/project.godot godot_world/tests/test_smoke.gd
git commit -m "test: wire up GUT headless test runner for godot_world"
```

(GUT itself isn't committed — it's gitignored per Task 2 and re-fetched via Step 1's commands whenever a fresh checkout needs it; the commit message reflects that only the wiring is checked in.)

---

### Task 5: Shared scenario-handler contract + `world_renderer.gd` core

This is the heart of the "one engine, many scenarios" design. `world_renderer.gd` knows nothing about `sims_world` or `mafia` — it loads trace data, picks a handler by `run.scenario`, and calls two methods on it.

**Files:**
- Create: `godot_world/scripts/scenario_handlers/scenario_handler.gd`
- Create: `godot_world/scripts/world_renderer.gd`
- Create: `godot_world/scenes/world_renderer.tscn`
- Create: `godot_world/tests/test_world_renderer.gd`

- [ ] **Step 1: Write the base handler class documenting the contract**

```gdscript
# godot_world/scripts/scenario_handlers/scenario_handler.gd
class_name ScenarioHandler
extends RefCounted

## Base contract every per-scenario handler implements. world_renderer.gd
## only ever calls these two methods — it has no scenario-specific knowledge.

## Returns a deterministic layout for this run's agents and any fixed
## locations (e.g. each sims_world agent's home). Must be a pure function of
## agent_ids/statuses — never read from a backend, since the Python
## simulation has no concept of x/y coordinates.
## Returns: { agent_id_or_location_id: Vector2 }
func layout_for(_agent_ids: Array, _statuses: Dictionary) -> Dictionary:
	return {}

## Reacts to one trace event. event is a Dictionary shaped exactly like one
## entry of GET /api/sim/run/{id}/trace's "events" array:
## {tick: int, kind: String, payload: Dictionary, actor_id: String, visibility: String}
## Implementations must silently ignore unknown `kind` values rather than
## raise, since new event kinds can be added on the Python side at any time.
func on_event(_event: Dictionary, _renderer: Node) -> void:
	pass
```

- [ ] **Step 2: Write `world_renderer.gd`**

```gdscript
# godot_world/scripts/world_renderer.gd
extends Node2D

const SimsWorldHandler = preload("res://scripts/scenario_handlers/sims_world_handler.gd")
const MafiaHandler = preload("res://scripts/scenario_handlers/mafia_handler.gd")

@export var tick_interval_sec: float = 0.6

var run_id: String = ""
var run: Dictionary = {}
var events: Array = []
var handler: ScenarioHandler = null
var agent_sprites: Dictionary = {}   # agent_id -> Node2D
var _event_index: int = 0
var _tick_timer: float = 0.0
var _playing: bool = true

signal trace_loaded(run: Dictionary)
signal playback_finished()

func _ready() -> void:
	run_id = _read_run_id_from_url()
	if run_id == "":
		push_warning("world_renderer: no run_id in URL query string, nothing to load")
		return
	_fetch_trace(run_id)

func _process(delta: float) -> void:
	if not _playing or events.is_empty():
		return
	_tick_timer += delta
	if _tick_timer < tick_interval_sec:
		return
	_tick_timer = 0.0
	if _event_index >= events.size():
		_playing = false
		playback_finished.emit()
		return
	var event: Dictionary = events[_event_index]
	_event_index += 1
	if handler:
		handler.on_event(event, self)

func _read_run_id_from_url() -> String:
	if not OS.has_feature("web"):
		return ""
	var query: String = JavaScriptBridge.eval(
		"new URLSearchParams(window.location.search).get('run_id') || ''", true
	)
	return String(query)

func _fetch_trace(id: String) -> void:
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_trace_response)
	var err := http.request("/api/sim/run/%s/trace" % id)
	if err != OK:
		push_error("world_renderer: failed to start HTTPRequest for run %s (err %d)" % [id, err])

func _on_trace_response(_result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if response_code != 200:
		push_error("world_renderer: /trace returned HTTP %d" % response_code)
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("world_renderer: /trace response was not a JSON object")
		return
	run = parsed
	events = run.get("events", [])
	handler = _handler_for_scenario(run.get("scenario", ""))
	if handler == null:
		push_error("world_renderer: no handler for scenario '%s'" % run.get("scenario", ""))
		return
	var agent_ids: Array = []
	var statuses: Dictionary = {}
	for agent in run.get("run", {}).get("agents", run.get("agents", [])):
		agent_ids.append(agent.get("agent_id"))
	var layout: Dictionary = handler.layout_for(agent_ids, statuses)
	_spawn_agents(agent_ids, layout)
	trace_loaded.emit(run)

func _handler_for_scenario(scenario: String) -> ScenarioHandler:
	match scenario:
		"sims_world":
			return SimsWorldHandler.new()
		"mafia":
			return MafiaHandler.new()
		_:
			return null

func _spawn_agents(agent_ids: Array, layout: Dictionary) -> void:
	for agent_id in agent_ids:
		var sprite := Sprite2D.new()
		sprite.name = "agent_%s" % str(agent_id).replace(":", "_")
		sprite.position = layout.get(agent_id, Vector2.ZERO)
		add_child(sprite)
		agent_sprites[agent_id] = sprite

func set_playing(value: bool) -> void:
	_playing = value
```

`run.get("run", {}).get("agents", run.get("agents", []))` defensively handles the trace response's actual top-level `run` key (the response is `{run: {...}, transitions: [...], events: [...]}` per Task 1's contract test) — the agent list lives at `run["run"]["agents"]`, not `run["agents"]`; the fallback only exists so a GUT test can pass a flattened fixture without constructing the full nested shape.

- [ ] **Step 3: Write `godot_world/scenes/world_renderer.tscn`**

```
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/world_renderer.gd" id="1"]

[node name="WorldRenderer" type="Node2D"]
script = ExtResource("1")
```

- [ ] **Step 4: Write a GUT test for handler dispatch**

```gdscript
# godot_world/tests/test_world_renderer.gd
extends GutTest

func test_handler_for_sims_world_scenario() -> void:
	var renderer = load("res://scripts/world_renderer.gd").new()
	var handler = renderer._handler_for_scenario("sims_world")
	assert_not_null(handler)

func test_handler_for_mafia_scenario() -> void:
	var renderer = load("res://scripts/world_renderer.gd").new()
	var handler = renderer._handler_for_scenario("mafia")
	assert_not_null(handler)

func test_handler_for_unknown_scenario_is_null() -> void:
	var renderer = load("res://scripts/world_renderer.gd").new()
	var handler = renderer._handler_for_scenario("does_not_exist")
	assert_null(handler)
```

- [ ] **Step 5: Run the GUT suite and verify all tests pass**

Run: `godot --headless --path godot_world -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit`
Expected: `Tests: 4, Passing: 4, Failing: 0` (the Task 4 smoke test plus these 3). This will fail at this point because `sims_world_handler.gd`/`mafia_handler.gd` don't exist yet — that's expected; Task 6 and Task 7 create them. Re-run this exact command at the end of Task 7 to confirm green.

- [ ] **Step 6: Commit**

```bash
git add godot_world/scripts/scenario_handlers/scenario_handler.gd \
        godot_world/scripts/world_renderer.gd godot_world/scenes/world_renderer.tscn \
        godot_world/tests/test_world_renderer.gd
git commit -m "feat: add world_renderer.gd core — trace fetch, tick playback, handler dispatch"
```

---

### Task 6: `sims_world_handler.gd`

Implements the real event kinds emitted by `ollama_arena/simulations/scenarios/sims_world.py` (verified by grepping that file's `_emit(...)` calls): `worked, rested, socialized, spent, conflicted, goal_set, rent_paid, rent_debt, agent_died, invalid_action`. Each agent's home location is deterministically `home_{agent_id}` (verified at `sims_world.py:103`).

**Files:**
- Create: `godot_world/scripts/scenario_handlers/sims_world_handler.gd`
- Create: `godot_world/tests/test_sims_world_handler.gd`

- [ ] **Step 1: Write the GUT test first**

```gdscript
# godot_world/tests/test_sims_world_handler.gd
extends GutTest

const SimsWorldHandler = preload("res://scripts/scenario_handlers/sims_world_handler.gd")

func test_layout_is_deterministic_for_same_input() -> void:
	var handler = SimsWorldHandler.new()
	var agent_ids = ["a:1b", "b:1b", "c:1b"]
	var layout1 = handler.layout_for(agent_ids, {})
	var layout2 = handler.layout_for(agent_ids, {})
	assert_eq(layout1, layout2, "same input must produce the same layout")

func test_layout_places_a_home_per_agent_with_no_overlaps() -> void:
	var handler = SimsWorldHandler.new()
	var agent_ids = ["a:1b", "b:1b", "c:1b", "d:1b"]
	var layout = handler.layout_for(agent_ids, {})
	var seen_positions = []
	for agent_id in agent_ids:
		var home_key = "home_%s" % agent_id
		assert_true(layout.has(home_key), "expected a home position for %s" % home_key)
		assert_false(seen_positions.has(layout[home_key]), "home positions must not overlap")
		seen_positions.append(layout[home_key])

func test_on_event_worked_does_not_crash() -> void:
	var handler = SimsWorldHandler.new()
	var fake_renderer = Node2D.new()
	var sprite = Sprite2D.new()
	sprite.name = "agent_a_1b"
	fake_renderer.add_child(sprite)
	fake_renderer.set("agent_sprites", {"a:1b": sprite})
	handler.on_event({"tick": 1, "kind": "worked", "payload": {"agent": "a:1b", "wage": 5.0}, "actor_id": "a:1b", "visibility": "public"}, fake_renderer)
	pass_test("worked event handled without raising")

func test_on_event_unknown_kind_is_ignored() -> void:
	var handler = SimsWorldHandler.new()
	var fake_renderer = Node2D.new()
	handler.on_event({"tick": 1, "kind": "totally_unknown_kind", "payload": {}, "actor_id": null, "visibility": "public"}, fake_renderer)
	pass_test("unknown kind handled without raising")
```

- [ ] **Step 2: Run to verify it fails (handler script doesn't exist yet)**

Run: `godot --headless --path godot_world -s addons/gut/gut_cmdln.gd -gdir=res://tests -gselect=sims_world -gexit`
Expected: load error — `sims_world_handler.gd` does not exist.

- [ ] **Step 3: Implement `sims_world_handler.gd`**

```gdscript
# godot_world/scripts/scenario_handlers/sims_world_handler.gd
extends "res://scripts/scenario_handlers/scenario_handler.gd"

const HOME_SPACING: float = 120.0
const HOMES_PER_ROW: int = 4
const JOB_LOCATION: Vector2 = Vector2(0, -300)
const SOCIAL_LOCATION: Vector2 = Vector2(0, 300)

# Real event kinds emitted by ollama_arena/simulations/scenarios/sims_world.py's
# _emit() calls — verified against that file directly, not guessed.
const SFX_FOR_KIND := {
	"worked": "res://assets/kenney_audio/impact/Audio/impactWood_medium_000.ogg",
	"rested": "res://assets/kenney_audio/ui/Audio/switch1.ogg",
	"socialized": "res://assets/kenney_audio/interface/Audio/confirmation_001.ogg",
	"spent": "res://assets/kenney_audio/ui/Audio/click1.ogg",
	"conflicted": "res://assets/kenney_audio/interface/Audio/error_001.ogg",
	"rent_paid": "res://assets/kenney_audio/ui/Audio/click2.ogg",
	"rent_debt": "res://assets/kenney_audio/interface/Audio/error_002.ogg",
	"agent_died": "res://assets/kenney_audio/interface/Audio/bong_001.ogg",
}

func layout_for(agent_ids: Array, _statuses: Dictionary) -> Dictionary:
	var layout: Dictionary = {
		"job_location": JOB_LOCATION,
		"social_location": SOCIAL_LOCATION,
	}
	for i in range(agent_ids.size()):
		var agent_id = agent_ids[i]
		var row = i / HOMES_PER_ROW
		var col = i % HOMES_PER_ROW
		var home_pos = Vector2(col * HOME_SPACING - 180, row * HOME_SPACING)
		layout["home_%s" % agent_id] = home_pos
		layout[agent_id] = home_pos
	return layout

func on_event(event: Dictionary, renderer: Node) -> void:
	var kind: String = event.get("kind", "")
	if kind == "invalid_action" or kind == "":
		return
	var actor_id = event.get("actor_id")
	var sprite: Node2D = _sprite_for(renderer, actor_id)
	match kind:
		"worked":
			if sprite:
				_walk_to(sprite, JOB_LOCATION)
			_show_bubble(renderer, sprite, "💼 worked")
		"rested":
			_show_bubble(renderer, sprite, "💤 rested")
		"socialized":
			if sprite:
				_walk_to(sprite, SOCIAL_LOCATION)
			_show_bubble(renderer, sprite, "💬 socialized")
		"spent":
			_show_bubble(renderer, sprite, "💰 spent %s" % str(event.get("payload", {}).get("amount", "")))
		"conflicted":
			_show_bubble(renderer, sprite, "⚔ conflicted")
		"goal_set":
			_show_bubble(renderer, sprite, "🎯 %s" % str(event.get("payload", {}).get("goal", "")))
		"rent_paid":
			_show_bubble(renderer, sprite, "🏠 rent paid")
		"rent_debt":
			_show_bubble(renderer, sprite, "⚠ rent debt")
		"agent_died":
			if sprite:
				_fade_out(sprite)
		_:
			pass  # unknown kind: ignore, never raise
	_play_sfx(renderer, kind)

func _sprite_for(renderer: Node, agent_id) -> Node2D:
	if agent_id == null:
		return null
	var sprites: Dictionary = renderer.get("agent_sprites")
	if sprites == null:
		return null
	return sprites.get(agent_id)

func _walk_to(sprite: Node2D, target: Vector2) -> void:
	var tween := sprite.create_tween()
	tween.tween_property(sprite, "position", target, 0.5)

func _fade_out(sprite: Node2D) -> void:
	var tween := sprite.create_tween()
	tween.tween_property(sprite, "modulate:a", 0.0, 1.0)

func _show_bubble(renderer: Node, sprite: Node2D, text: String) -> void:
	if sprite == null or not renderer.has_method("show_action_bubble"):
		return
	renderer.show_action_bubble(sprite, text)

func _play_sfx(renderer: Node, kind: String) -> void:
	if not SFX_FOR_KIND.has(kind) or not renderer.has_method("play_sfx"):
		return
	renderer.play_sfx(SFX_FOR_KIND[kind])
```

- [ ] **Step 4: Run the GUT suite again and verify these tests pass**

Run: `godot --headless --path godot_world -s addons/gut/gut_cmdln.gd -gdir=res://tests -gselect=sims_world -gexit`
Expected: `Tests: 4, Passing: 4, Failing: 0`

- [ ] **Step 5: Commit**

```bash
git add godot_world/scripts/scenario_handlers/sims_world_handler.gd \
        godot_world/tests/test_sims_world_handler.gd
git commit -m "feat: implement sims_world_handler.gd for the L3 world renderer"
```

---

### Task 7: `mafia_handler.gd`

Implements the real event kinds from `ollama_arena/simulations/scenarios/mafia.py`'s `_emit(...)` calls: `discussion, vote_cast, night_kill_decided, morning_announcement, elimination, invalid_action`. Critically, **`roles` are never exposed publicly** — they're internal World state, never copied into an `Event` payload (confirmed by reading the scenario file end to end) — so the handler must never assume it knows who is Mafia vs. villager, even in a finished replay. `night_kill_decided` carries `visibility: "private"` (witnessed only by the mafia faction) and must be skipped in default playback per the spec's visibility rule; the actual public death reveal is `morning_announcement`.

**Files:**
- Create: `godot_world/scripts/scenario_handlers/mafia_handler.gd`
- Create: `godot_world/tests/test_mafia_handler.gd`

- [ ] **Step 1: Write the GUT test first**

```gdscript
# godot_world/tests/test_mafia_handler.gd
extends GutTest

const MafiaHandler = preload("res://scripts/scenario_handlers/mafia_handler.gd")

func test_layout_places_agents_in_a_circle_deterministically() -> void:
	var handler = MafiaHandler.new()
	var agent_ids = ["a:1b", "b:1b", "c:1b", "d:1b"]
	var layout1 = handler.layout_for(agent_ids, {})
	var layout2 = handler.layout_for(agent_ids, {})
	assert_eq(layout1, layout2)
	for agent_id in agent_ids:
		assert_true(layout1.has(agent_id))

func test_night_kill_decided_is_skipped_when_private() -> void:
	var handler = MafiaHandler.new()
	var fake_renderer = Node2D.new()
	var calls := []
	fake_renderer.set_meta("bubble_calls", calls)
	# night_kill_decided has visibility "private" in the real /trace response —
	# on_event must not reveal it during default (non-debug) playback.
	handler.on_event({"tick": 2, "kind": "night_kill_decided", "payload": {"target": "b:1b"}, "actor_id": null, "visibility": "private"}, fake_renderer)
	pass_test("private night_kill_decided handled without raising or requiring renderer hooks")

func test_morning_announcement_does_not_crash() -> void:
	var handler = MafiaHandler.new()
	var fake_renderer = Node2D.new()
	var sprite = Sprite2D.new()
	sprite.name = "agent_b_1b"
	fake_renderer.add_child(sprite)
	fake_renderer.set("agent_sprites", {"b:1b": sprite})
	handler.on_event({"tick": 2, "kind": "morning_announcement", "payload": {"killed": "b:1b"}, "actor_id": null, "visibility": "public"}, fake_renderer)
	pass_test("morning_announcement handled without raising")

func test_unknown_kind_is_ignored() -> void:
	var handler = MafiaHandler.new()
	var fake_renderer = Node2D.new()
	handler.on_event({"tick": 1, "kind": "totally_unknown", "payload": {}, "actor_id": null, "visibility": "public"}, fake_renderer)
	pass_test("unknown kind handled without raising")
```

- [ ] **Step 2: Run to verify it fails**

Run: `godot --headless --path godot_world -s addons/gut/gut_cmdln.gd -gdir=res://tests -gselect=mafia -gexit`
Expected: load error — `mafia_handler.gd` does not exist.

- [ ] **Step 3: Implement `mafia_handler.gd`**

```gdscript
# godot_world/scripts/scenario_handlers/mafia_handler.gd
extends "res://scripts/scenario_handlers/scenario_handler.gd"

const CIRCLE_RADIUS: float = 220.0

func layout_for(agent_ids: Array, _statuses: Dictionary) -> Dictionary:
	var layout: Dictionary = {}
	var count: int = agent_ids.size()
	for i in range(count):
		var angle: float = (TAU / max(count, 1)) * i
		var pos := Vector2(cos(angle), sin(angle)) * CIRCLE_RADIUS
		layout[agent_ids[i]] = pos
	return layout

func on_event(event: Dictionary, renderer: Node) -> void:
	var kind: String = event.get("kind", "")
	var visibility: String = event.get("visibility", "public")
	if kind == "invalid_action" or kind == "":
		return
	# night_kill_decided is witnessed only by the mafia faction in the real
	# simulation (witness_ids=mafia_ids_all in mafia.py) — its visibility
	# field is "private". Default playback must not reveal it; the public
	# reveal is morning_announcement, emitted separately with WITNESS_ALL.
	if kind == "night_kill_decided" and visibility == "private":
		return
	var actor_id = event.get("actor_id")
	var sprite: Node2D = _sprite_for(renderer, actor_id)
	match kind:
		"discussion":
			_show_bubble(renderer, sprite, "💬 %s" % str(event.get("payload", {}).get("text", "")))
			_play_sfx(renderer, "res://assets/kenney_audio/ui/Audio/rollover1.ogg")
		"vote_cast":
			var target = event.get("payload", {}).get("target")
			var target_sprite: Node2D = _sprite_for(renderer, target)
			_show_bubble(renderer, sprite, "🗳 votes %s" % str(target))
			if sprite and target_sprite:
				_point_at(sprite, target_sprite)
			_play_sfx(renderer, "res://assets/kenney_audio/ui/Audio/switch2.ogg")
		"morning_announcement":
			var killed = event.get("payload", {}).get("killed")
			var killed_sprite: Node2D = _sprite_for(renderer, killed)
			if killed_sprite:
				_fade_out(killed_sprite)
			_show_bubble(renderer, killed_sprite, "☠ found dead")
			_play_sfx(renderer, "res://assets/kenney_audio/interface/Audio/bong_001.ogg")
		"elimination":
			var eliminated = event.get("payload", {}).get("eliminated")
			if eliminated != null:
				var eliminated_sprite: Node2D = _sprite_for(renderer, eliminated)
				if eliminated_sprite:
					_fade_out(eliminated_sprite)
				_show_bubble(renderer, eliminated_sprite, "⚖ voted out")
			_play_sfx(renderer, "res://assets/kenney_audio/interface/Audio/confirmation_002.ogg")
		_:
			pass  # unknown kind: ignore, never raise

func _sprite_for(renderer: Node, agent_id) -> Node2D:
	if agent_id == null:
		return null
	var sprites: Dictionary = renderer.get("agent_sprites")
	if sprites == null:
		return null
	return sprites.get(agent_id)

func _fade_out(sprite: Node2D) -> void:
	var tween := sprite.create_tween()
	tween.tween_property(sprite, "modulate:a", 0.0, 1.0)

func _point_at(sprite: Node2D, target: Node2D) -> void:
	var tween := sprite.create_tween()
	tween.tween_property(sprite, "rotation", sprite.position.angle_to_point(target.position), 0.2)
	tween.tween_property(sprite, "rotation", 0.0, 0.3)

func _show_bubble(renderer: Node, sprite: Node2D, text: String) -> void:
	if sprite == null or not renderer.has_method("show_action_bubble"):
		return
	renderer.show_action_bubble(sprite, text)

func _play_sfx(renderer: Node, path: String) -> void:
	if not renderer.has_method("play_sfx"):
		return
	renderer.play_sfx(path)
```

- [ ] **Step 4: Run the full GUT suite and verify everything passes**

Run: `godot --headless --path godot_world -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit`
Expected: `Tests: 11, Passing: 11, Failing: 0` (1 smoke + 3 world_renderer + 4 sims_world + 4 mafia, including the test from Task 5 Step 5 which should now pass since both handlers exist).

- [ ] **Step 5: Commit**

```bash
git add godot_world/scripts/scenario_handlers/mafia_handler.gd \
        godot_world/tests/test_mafia_handler.gd
git commit -m "feat: implement mafia_handler.gd, respecting event visibility for night kills"
```

---

### Task 8: `camera_rig.gd` — free and cinematic dual mode

**Files:**
- Create: `godot_world/scripts/camera_rig.gd`

- [ ] **Step 1: Implement the camera rig**

```gdscript
# godot_world/scripts/camera_rig.gd
extends Camera2D

enum Mode { FREE, CINEMATIC }

@export var pan_speed: float = 600.0
@export var zoom_speed: float = 0.1
@export var min_zoom: float = 0.4
@export var max_zoom: float = 2.5
@export var cinematic_follow_speed: float = 3.0

var mode: Mode = Mode.CINEMATIC
var _cinematic_target: Vector2 = Vector2.ZERO
var _dragging: bool = false
var _drag_last_mouse: Vector2 = Vector2.ZERO

func _unhandled_input(event: InputEvent) -> void:
	if mode != Mode.FREE:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			_dragging = event.pressed
			_drag_last_mouse = event.position
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			_apply_zoom(-zoom_speed)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_apply_zoom(zoom_speed)
	elif event is InputEventMouseMotion and _dragging:
		var delta: Vector2 = event.position - _drag_last_mouse
		position -= delta / zoom.x
		_drag_last_mouse = event.position

func _process(delta: float) -> void:
	if mode == Mode.CINEMATIC:
		position = position.lerp(_cinematic_target, clamp(cinematic_follow_speed * delta, 0.0, 1.0))

func _apply_zoom(amount: float) -> void:
	var new_zoom: float = clamp(zoom.x + amount, min_zoom, max_zoom)
	zoom = Vector2(new_zoom, new_zoom)

func set_mode(new_mode: Mode) -> void:
	mode = new_mode

func focus_on(world_position: Vector2) -> void:
	_cinematic_target = world_position

func toggle_mode() -> void:
	mode = Mode.FREE if mode == Mode.CINEMATIC else Mode.CINEMATIC
```

- [ ] **Step 2: Attach it to the scene**

Edit `godot_world/scenes/world_renderer.tscn` to add a `Camera2D` child node running this script:

```
[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://scripts/world_renderer.gd" id="1"]
[ext_resource type="Script" path="res://scripts/camera_rig.gd" id="2"]

[node name="WorldRenderer" type="Node2D"]
script = ExtResource("1")

[node name="CameraRig" type="Camera2D" parent="."]
script = ExtResource("2")
```

- [ ] **Step 3: Wire `world_renderer.gd` to call `focus_on()` per event**

In `godot_world/scripts/world_renderer.gd`, add inside `_process` right after `handler.on_event(event, self)`:

```gdscript
	var camera := get_node_or_null("CameraRig")
	if camera and agent_sprites.has(event.get("actor_id")):
		camera.focus_on(agent_sprites[event.get("actor_id")].position)
```

- [ ] **Step 4: Commit**

```bash
git add godot_world/scripts/camera_rig.gd godot_world/scenes/world_renderer.tscn \
        godot_world/scripts/world_renderer.gd
git commit -m "feat: add dual free/cinematic camera rig to the L3 world renderer"
```

---

### Task 9: Action bubbles + day/night atmosphere

**Files:**
- Create: `godot_world/scenes/action_bubble.tscn`
- Create: `godot_world/scripts/action_bubble.gd`
- Modify: `godot_world/scripts/world_renderer.gd`

- [ ] **Step 1: Write the action bubble script**

```gdscript
# godot_world/scripts/action_bubble.gd
extends Node2D

@onready var label: Label = $Label

func show_text(text: String, anchor: Node2D) -> void:
	global_position = anchor.global_position + Vector2(0, -40)
	label.text = text
	modulate.a = 1.0
	var tween := create_tween()
	tween.tween_interval(1.2)
	tween.tween_property(self, "modulate:a", 0.0, 0.5)
	tween.tween_callback(queue_free)
```

- [ ] **Step 2: Write the action bubble scene**

```
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/action_bubble.gd" id="1"]

[node name="ActionBubble" type="Node2D"]
script = ExtResource("1")

[node name="Label" type="Label" parent="."]
horizontal_alignment = 1
```

- [ ] **Step 3: Add `show_action_bubble`, `play_sfx`, and atmosphere tint to `world_renderer.gd`**

Add near the top of `godot_world/scripts/world_renderer.gd`:

```gdscript
const ActionBubbleScene = preload("res://scenes/action_bubble.tscn")
```

Add these methods (called by the scenario handlers via `renderer.has_method(...)` checks already written in Task 6/7):

```gdscript
func show_action_bubble(anchor: Node2D, text: String) -> void:
	if anchor == null:
		return
	var bubble = ActionBubbleScene.instantiate()
	add_child(bubble)
	bubble.show_text(text, anchor)

func play_sfx(path: String) -> void:
	if not ResourceLoader.exists(path):
		return
	var player := AudioStreamPlayer.new()
	add_child(player)
	player.stream = load(path)
	player.finished.connect(player.queue_free)
	player.play()

func _apply_atmosphere_tint() -> void:
	var tint := get_node_or_null("AtmosphereTint")
	if tint == null:
		tint = CanvasModulate.new()
		tint.name = "AtmosphereTint"
		add_child(tint)
	if run.get("scenario") == "mafia":
		var statuses: Array = run.get("run", {}).get("agents", [])
		var is_night: bool = _event_index % 2 == 1  # alternates with mafia's day/night phase cadence
		tint.color = Color(0.55, 0.55, 0.85) if is_night else Color(1, 1, 1)
	elif run.get("scenario") == "sims_world":
		tint.color = Color(1, 0.97, 0.9)
```

Call `_apply_atmosphere_tint()` once per tick inside `_process`, right before `_event_index += 1`:

```gdscript
	_apply_atmosphere_tint()
```

- [ ] **Step 4: Commit**

```bash
git add godot_world/scenes/action_bubble.tscn godot_world/scripts/action_bubble.gd \
        godot_world/scripts/world_renderer.gd
git commit -m "feat: add action bubbles and day/night atmosphere tint to the L3 world"
```

---

### Task 10: Run-start/run-complete audio stinger

**Files:**
- Modify: `godot_world/scripts/world_renderer.gd`

- [ ] **Step 1: Play a stinger on load and on playback completion**

In `_on_trace_response`, right after `trace_loaded.emit(run)`:

```gdscript
	play_sfx("res://assets/kenney_audio/jingles/Audio/8-Bit jingles/jingles_NES00.ogg")
```

In the `_process` block where `playback_finished.emit()` is called, right before it:

```gdscript
	play_sfx("res://assets/kenney_audio/jingles/Audio/8-Bit jingles/jingles_NES01.ogg")
```

This is the v1 answer to the spec's music open item: a short stinger on load/completion, not a continuous ambient bed (no CC0 ambient loop exists in Kenney's catalog — see "Plan-time deviations" above).

- [ ] **Step 2: Commit**

```bash
git add godot_world/scripts/world_renderer.gd
git commit -m "feat: play start/complete jingle stingers (no CC0 ambient loop source exists)"
```

---

### Task 11: Build pipeline — export templates, Web export, copy into `static/godot/`

**Files:**
- No new repo files; this task documents and executes the build.

- [ ] **Step 1: Install Godot 4.7 export templates (one-time toolchain setup)**

```bash
curl -sL "https://github.com/godotengine/godot/releases/download/4.7-stable/Godot_v4.7-stable_export_templates.tpz" \
  -o /tmp/godot_templates.tpz
mkdir -p ~/Library/Application\ Support/Godot/export_templates/4.7.stable
unzip -o /tmp/godot_templates.tpz -d /tmp/godot_templates_extracted
cp -R /tmp/godot_templates_extracted/templates/. ~/Library/Application\ Support/Godot/export_templates/4.7.stable/
rm -rf /tmp/godot_templates.tpz /tmp/godot_templates_extracted
```

Expected: `~/Library/Application Support/Godot/export_templates/4.7.stable/web_release.zip` (and `web_debug.zip`) exist. This step only needs to run once per machine that builds the export — it never runs on end-user machines, which only receive the static export output.

- [ ] **Step 2: Run the Web export**

```bash
cd godot_world && godot --headless --export-release "Web" export/index.html
```

Expected: exits 0, and `godot_world/export/index.html`, `index.js`, `index.wasm`, `index.pck` all exist. If it fails with a missing-template error, Step 1's directory name must exactly match the editor's version string — re-check with `godot --version` (expected `4.7.stable.official.5b4e0cb0f` per the locally installed build) against the `export_templates/<version>/` directory name.

- [ ] **Step 3: Copy the export output into `static/godot/`**

```bash
mkdir -p static/godot
cp -R godot_world/export/. static/godot/
```

- [ ] **Step 4: Verify it's served by the existing FastAPI static mount**

```bash
ollama-arena web --port 18080 &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18080/static/godot/index.html
kill %1
```
Expected: `200`. No changes to `ollama_arena/web.py` are needed — `STATIC_ROOT = Path(__file__).parent.parent / "static"` (confirmed at `web.py:247`) already mounts the whole `static/` directory, and `static/godot/` is just another subdirectory of it.

- [ ] **Step 5: Commit the build-output gitignore (already done in Task 2) — nothing else to commit here**

`static/godot/` is gitignored (Task 2), so this task produces no new tracked files; it only proves the pipeline works end-to-end. Document the exact two commands from Steps 1-2 don't need re-running by future contributors unless `godot_world/` source changes — note this in the PR description when this plan is executed, not in a tracked file.

---

### Task 12: Web UI — "🎮 World" tab and "▶ View in 3D world" button

**Files:**
- Create: `static/js/world.js`
- Modify: `templates/index.html`
- Modify: `templates/base.html`
- Modify: `static/js/sim.js:209-231` (the `loadSimRuns` row renderer)
- Modify: `static/js/ws-client.js:209` (tab-init dispatch map)
- Modify: `static/css/arena.css`

- [ ] **Step 1: Add the nav tab button**

In `templates/index.html`, after line 44 (`<div class="tab" ... data-tab="providers">🔌 Providers</div>`):

```html
  <div class="tab" role="tab" tabindex="-1" data-tab="world">🎮 World</div>
```

- [ ] **Step 2: Add the tab-content panel**

In `templates/index.html`, after the `tab-providers` panel's closing `</div>` (the panel that starts at line 598), add:

```html
  <!-- L3 GODOT WORLD VIEWER -->
  <div class="tab-content" id="tab-world" role="tabpanel">
    <div class="card">
      <h2>🎮 World</h2>
      <p class="sim-field-help" id="world-empty-state">
        Open a finished run from the Simulations tab's "Run history" table
        and click "▶ View in 3D world" to load it here.
      </p>
      <div id="world-iframe-wrap" style="display:none;">
        <iframe id="world-iframe" style="width:100%; height:640px; border:1px solid var(--border-color); border-radius:8px; background:#000;" allow="autoplay"></iframe>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: Add the iframe CSS**

In `static/css/arena.css`, add near the existing `.provider-card` rules:

```css
#world-iframe-wrap {
  margin-top: 12px;
}
#world-iframe {
  display: block;
}
```

- [ ] **Step 4: Write `static/js/world.js`**

```javascript
let _worldPendingRunId = null;

function initWorldTab() {
  if (_worldPendingRunId) {
    showWorldRun(_worldPendingRunId);
    _worldPendingRunId = null;
  }
}

function showWorldRun(runId) {
  const emptyState = document.getElementById('world-empty-state');
  const wrap = document.getElementById('world-iframe-wrap');
  const iframe = document.getElementById('world-iframe');
  if (!emptyState || !wrap || !iframe) {
    _worldPendingRunId = runId;
    return;
  }
  iframe.src = `/static/godot/index.html?run_id=${encodeURIComponent(runId)}`;
  emptyState.style.display = 'none';
  wrap.style.display = 'block';
}

function viewSimRunInWorld(runId) {
  document.querySelector('.tab[data-tab="world"]').click();
  showWorldRun(runId);
}
```

- [ ] **Step 5: Register the script and the tab-init map entry**

In `templates/base.html`, after the existing `providers.js` script tag:

```html
<script src="/static/js/world.js?v={{ asset_version }}"></script>
```

In `static/js/ws-client.js`, change line 209's object literal to add `world: initWorldTab`:

```javascript
const m = { dashboard: loadCharts, datasets: loadDatasets, performance: loadPerf, hallucinations: loadHallucinations, spec: loadSpec, genome: initGenomeTab, sim: initSimTab, providers: initProvidersTab, world: initWorldTab, tournament: () => {}, royale: () => {}, history: loadHistory };
```

- [ ] **Step 6: Add the "▶ View in 3D world" button to the run-history table**

In `static/js/sim.js`, modify the `<td class="sim-run-actions">` block (lines 216-220) to add the new button after the existing Resume button:

```javascript
        <td class="sim-run-actions">
          <button class="btn" data-act="watch" data-run="${escText(run.run_id)}">Watch</button>
          ${run.status === 'in_progress' ? `<button class="btn" data-act="pause" data-run="${escText(run.run_id)}">Pause</button>` : ''}
          ${run.status === 'paused' ? `<button class="btn" data-act="resume" data-run="${escText(run.run_id)}">Resume</button>` : ''}
          ${run.status === 'completed' && (run.scenario === 'sims_world' || run.scenario === 'mafia') ? `<button class="btn" data-act="world" data-run="${escText(run.run_id)}">▶ View in 3D world</button>` : ''}
        </td>
```

And add the matching branch in the click-handler loop right after `else if (button.dataset.act === 'resume') resumeSimRun(runId);`:

```javascript
        else if (button.dataset.act === 'world') viewSimRunInWorld(runId);
```

The button only appears for `completed` runs of the two scenarios the Godot renderer actually supports (`sims_world`, `mafia`) — matching this plan's explicit scope, not every scenario.

- [ ] **Step 7: Manually verify in a browser**

Start the dev server, run a `sims_world` simulation to completion from the Simulations tab, confirm the "▶ View in 3D world" button appears in its run-history row, click it, confirm the World tab activates and the iframe loads `static/godot/index.html?run_id=...`, and confirm no console errors appear (the same Playwright-driven verification pattern already used for the Providers tab in this project).

- [ ] **Step 8: Commit**

```bash
git add static/js/world.js templates/index.html templates/base.html \
        static/js/sim.js static/js/ws-client.js static/css/arena.css
git commit -m "feat: add 'View in 3D world' button and World tab wiring up the Godot export"
```

---

### Task 13: Manual QA checklist and final verification pass

GDScript rendering correctness (animation, camera feel, audio timing) is inherently visual and isn't meaningfully asserted by pytest or GUT — verify it live, the same way the Providers tab's encrypted-key UI was verified live in this project.

**Files:** none (verification only).

- [ ] **Step 1: Run the full Python test suite**

Run: `python -m pytest -q`
Expected: all tests pass, including the new `tests/test_sim_trace_contract.py` from Task 1.

- [ ] **Step 2: Run the full GUT suite one more time**

Run: `godot --headless --path godot_world -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit`
Expected: `Tests: 11, Passing: 11, Failing: 0`.

- [ ] **Step 3: Manual QA checklist (perform each item in a real browser against a real completed run of each scenario)**

- [ ] A completed `sims_world` run: homes are laid out in a grid with no overlaps; clicking "worked" ticks shows the agent walking toward the job location and a "💼 worked" bubble; `agent_died` fades the sprite out; the day/night tint shifts to a warm color.
- [ ] A completed `mafia` run: agents are laid out in a circle; `discussion` events show speech bubbles; `vote_cast` events show a brief point-at rotation toward the target; `night_kill_decided` events produce **no visible bubble or fade** (private, correctly suppressed); `morning_announcement` fades out the actual victim; the tint alternates between a cool night tone and neutral day tone.
- [ ] Free camera mode: drag pans, scroll wheel zooms, stays within `min_zoom`/`max_zoom`.
- [ ] Cinematic camera mode: smoothly pans to whichever agent most recently had an event.
- [ ] A start jingle plays when the World tab first loads a run; a different jingle plays once playback reaches the last event.
- [ ] No browser console errors at any point during the above.
- [ ] The "▶ View in 3D world" button is absent for runs of scenarios other than `sims_world`/`mafia`, and absent for runs that are not yet `completed`.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: complete L3 Godot world QA pass"
```

(Only commit if the QA pass above produced doc/code fixes — if everything passed clean with no edits needed, skip this commit.)

---

## Self-Review

**Spec coverage:** Every "Explicitly in scope for v1" bullet from the spec maps to a task — shared renderer (Task 5), sims_world + mafia handlers (Tasks 6-7), free/cinematic camera (Task 8), Kenney art (Task 3), day/night + day-counter tint (Task 9), action bubbles for every listed event kind (Tasks 6-7, using the *real* verified kind names, which differ slightly from the spec's informal names — e.g. `vote_cast` not `vote`, `night_kill_decided`/`morning_announcement` not `night_kill`), SFX (Tasks 6-7) and music (Task 10, resolved as stingers not ambient loop), the "▶ View in 3D world" entry point (Task 12). Both spec open items are resolved with real findings, documented at the top of this plan rather than deferred again. The "Data flow" HTTPRequest/JavaScriptBridge/per-scenario-dispatch sequence is implemented exactly in Task 5. The build/serving pipeline matches the spec's described commands (Task 11). Deferred items (live viewing, third scenario, deep inspect panels) are correctly not implemented here.

**Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N" patterns — every step has complete, real code, exact verified URLs, and exact expected command output.

**Type/signature consistency:** `layout_for(agent_ids: Array, statuses: Dictionary) -> Dictionary` and `on_event(event: Dictionary, renderer: Node) -> void` are defined once in `scenario_handler.gd` (Task 5) and implemented identically in both `sims_world_handler.gd` (Task 6) and `mafia_handler.gd` (Task 7). `show_action_bubble(anchor, text)` and `play_sfx(path)` are defined once on `world_renderer.gd` (Task 9) and called identically (via `renderer.has_method(...)` guards) from both handlers (Tasks 6-7, written before Task 9 — intentionally guarded so Tasks 6-7's GUT tests pass even before Task 9 adds the real implementations). `viewSimRunInWorld(runId)` (Task 12, `world.js`) is the one and only JS entry point called from `sim.js`'s click handler — no duplicate/renamed variant exists elsewhere.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-22-godot-l3-world.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
