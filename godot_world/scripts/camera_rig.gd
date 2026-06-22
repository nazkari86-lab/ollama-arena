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
