"""Vision / multimodal payload tests for Ollama backend."""
import json as json_module
from unittest.mock import MagicMock, patch

import pytest

from ollama_arena.backends.ollama import OllamaBackend


@pytest.fixture
def backend():
    return OllamaBackend(base_url="http://localhost:11434", timeout=5)


def test_generate_passes_images_in_message(backend):
    captured = {}

    def fake_post(url, json=None, stream=True, timeout=None):
        captured["body"] = json
        mock = MagicMock()
        mock.iter_lines.return_value = [
            json_module.dumps({
                "message": {"content": "I see a cat."},
                "done": True,
                "prompt_eval_count": 10,
                "eval_count": 5,
            }).encode()
        ]
        return mock

    img_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    with patch("requests.post", side_effect=fake_post):
        res = backend.generate("llama3.2-vision", "Describe this image.", images=[img_b64])

    assert res.text == "I see a cat."
    msgs = captured["body"]["messages"]
    user_msgs = [m for m in msgs if m.get("role") == "user" and m.get("images")]
    assert user_msgs
    assert user_msgs[0].get("images") == [img_b64]


def test_chat_turn_accepts_messages_with_images(backend):
    captured = {}

    def fake_post(url, json=None, stream=True, timeout=None):
        captured["body"] = json
        mock = MagicMock()
        mock.iter_lines.return_value = [
            json_module.dumps({
                "message": {"content": "ok"},
                "done": True,
                "prompt_eval_count": 1,
                "eval_count": 1,
            }).encode()
        ]
        return mock

    messages = [{"role": "user", "content": "what is this?", "images": ["abc123"]}]
    with patch("requests.post", side_effect=fake_post):
        turn = backend.chat_turn("llama3.2-vision", messages, tools=[])

    assert turn.error == ""
    msgs = captured["body"]["messages"]
    user_msgs = [m for m in msgs if m.get("role") == "user" and m.get("images")]
    assert user_msgs
    assert user_msgs[0].get("images") == ["abc123"]
