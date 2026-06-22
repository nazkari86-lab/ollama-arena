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
