"""Shared pytest configuration — env must be set before ollama_arena.web import."""
import os

os.environ.setdefault("ARENA_ALLOWED_ORIGINS", "http://localhost:7860")
os.environ.setdefault("ARENA_RL_PLAYGROUND", "3/minute")
os.environ.setdefault("ARENA_RL_DEFAULT", "5/minute")
