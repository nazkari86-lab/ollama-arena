"""Example: vision model smoke test via Ollama backend."""
from ollama_arena.backends.ollama import OllamaBackend

# 1×1 PNG (base64)
TINY_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def main():
    backend = OllamaBackend()
    if not backend.is_alive():
        print("Ollama not running — start with: ollama serve")
        return
    models = backend.list_models()
    vision = next((m for m in models if "vision" in m.lower()), None)
    if not vision:
        print("No vision model pulled — try: ollama pull llama3.2-vision")
        return
    res = backend.generate(vision, "Describe this image in one sentence.", images=[TINY_PNG])
    print(f"Model: {vision}")
    print(res.text or res.error)


if __name__ == "__main__":
    main()
