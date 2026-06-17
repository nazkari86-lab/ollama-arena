import pytest
from unittest.mock import patch
from ollama_arena.evaluator import eval_coding

@patch("ollama_arena.sandboxes.run_in_language")
def test_eval_coding_uses_docker_by_default(mock_run):
    mock_run.return_value.accepted = True
    task = {"id": "test_001", "category": "coding", "language": "python", "test_code": "assert True"}
    response = "```python\nprint('hello')\n```"
    
    # We expect it to try docker by default now
    eval_coding(task, response)
    
    # Assert run_in_language was called
    mock_run.assert_called_once()
    # Check if use_docker was passed as True in kwargs
    assert mock_run.call_args[1].get("use_docker") == True
