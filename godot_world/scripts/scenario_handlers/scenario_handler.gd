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
