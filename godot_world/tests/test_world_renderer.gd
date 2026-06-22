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
