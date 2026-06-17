import pytest
from ollama_arena.evaluator import eval_json

def test_eval_json_perfect():
    task = {
        "id": "json_test",
        "expected_schema": {"city": "string", "temp": "number", "rainy": "boolean"}
    }
    response = '{"city": "Berlin", "temp": 18.5, "rainy": false}'
    assert eval_json(task, response) == 1.0

def test_eval_json_partial_keys():
    task = {
        "id": "json_test",
        "expected_schema": {"city": "string", "temp": "number", "rainy": "boolean"}
    }
    # only city and temp are present, rainy is missing
    response = '{"city": "Berlin", "temp": 18.5}'
    assert eval_json(task, response) == pytest.approx(0.667, 0.01)

def test_eval_json_wrong_types():
    task = {
        "id": "json_test",
        "expected_schema": {"city": "string", "temp": "number", "rainy": "boolean"}
    }
    # temp is a string instead of number, rainy is string instead of boolean
    response = '{"city": "Berlin", "temp": "18.5", "rainy": "no"}'
    assert eval_json(task, response) == pytest.approx(0.333, 0.01)

def test_eval_json_invalid_syntax():
    task = {
        "id": "json_test",
        "expected_schema": {"city": "string"}
    }
    response = '{"city": "Berlin"'  # missing closing brace
    assert eval_json(task, response) == 0.0

def test_eval_json_markdown_fenced():
    task = {
        "id": "json_test",
        "expected_schema": {"city": "string"}
    }
    response = "Here is the response:\n```json\n{\n  \"city\": \"Tokyo\"\n}\n```"
    assert eval_json(task, response) == 1.0

def test_eval_json_no_schema():
    task = {
        "id": "json_test"
    }
    response = '{"any_key": [1, 2, 3]}'
    assert eval_json(task, response) == 1.0

def test_eval_json_not_a_dict():
    task = {
        "id": "json_test",
        "expected_schema": {"city": "string"}
    }
    response = '["Tokyo"]'
    assert eval_json(task, response) == 0.0
