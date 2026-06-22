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
	var sprites: Variant = renderer.get("agent_sprites")
	if typeof(sprites) != TYPE_DICTIONARY:
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
