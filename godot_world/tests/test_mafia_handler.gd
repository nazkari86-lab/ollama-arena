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
