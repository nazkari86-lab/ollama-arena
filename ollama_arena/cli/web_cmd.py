"""Web dashboard CLI command."""
from __future__ import annotations


def cmd_web(args):
    from ..web import run_web
    run_web(
        host=args.host, port=args.port,
        ollama_url=args.ollama, db_path=args.db,
        backend=args.backend, api_key=args.api_key,
    )
