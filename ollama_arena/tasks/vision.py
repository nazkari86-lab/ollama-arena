"""Vision / multimodal evaluation tasks."""

# 1×1 red PNG — lightweight placeholder for VLM benchmarks
_RED_PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _task(tid, instruction, keywords, difficulty="medium", extra=None):
    t = {
        "id": tid,
        "category": "vision",
        "instruction": instruction,
        "images": [_RED_PX],
        "expected_keywords": keywords,
        "difficulty": difficulty,
    }
    if extra:
        t.update(extra)
    return t


TASKS = [
    _task("vis_001", "Describe the dominant color in this image.", ["red"], "easy"),
    _task("vis_002", "What shape appears in this image?", ["square", "pixel", "dot"], "easy"),
    _task("vis_003", "Is this image mostly a solid color? Answer yes or no.", ["yes"], "easy"),
    _task("vis_004", "Estimate how many distinct objects are visible.", ["one", "1", "single"], "easy"),
    _task("vis_005", "Does this image look like a photograph or an icon?", ["icon", "pixel", "simple"], "medium"),
    _task("vis_006", "Would this image work as a favicon? Explain briefly.", ["yes", "small", "simple"], "medium"),
    _task("vis_007", "Describe the brightness of this image.", ["bright", "light"], "medium"),
    _task("vis_008", "If this were a traffic light, which signal would it represent?", ["stop", "red"], "medium"),
    _task("vis_009", "OCR task: read any visible text in the image.", ["no text", "none", "empty"], "medium"),
    _task("vis_010", "Classify this image: diagram, photo, or abstract.", ["abstract", "solid", "color"], "medium"),
    _task("vis_011", "Is there a human face in this image?", ["no", "not"], "easy"),
    _task("vis_012", "Describe the background of this image.", ["red", "solid", "uniform"], "easy"),
    _task("vis_013", "What file format might this image be?", ["png", "bitmap"], "hard"),
    _task("vis_014", "Would color-blind users distinguish this from green?", ["yes", "red"], "hard"),
    _task("vis_015", "Summarize this image in one sentence for alt text.", ["red", "pixel", "solid"], "medium"),
]


def get_vision_tasks():
    return TASKS
