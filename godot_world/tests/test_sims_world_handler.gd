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
