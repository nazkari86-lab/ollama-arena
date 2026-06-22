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
	var sprites: Variant = renderer.get("agent_sprites")
	if typeof(sprites) != TYPE_DICTIONARY:
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
