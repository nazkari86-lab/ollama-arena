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
