.PHONY: install dev test lint fmt clean build publish

install:
	pip install -e .

dev:
	pip install -e ".[dev,all]"

test:
	pytest -q

lint:
	ruff check ollama_arena tests

fmt:
	ruff format ollama_arena tests

build:
	python -m build

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
