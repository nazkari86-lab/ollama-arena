"""Fire-and-forget webhook notifications (Discord / Slack / generic JSON).

Set ARENA_WEBHOOK_URL to enable. The URL format is auto-detected:
  - discord.com/api/webhooks/* → Discord embed format
  - hooks.slack.com/*         → Slack incoming webhook format
  - anything else             → generic {"event": ..., "data": ...} JSON

Calls are non-blocking: they run in a daemon thread so they never delay
match processing even if the remote endpoint is slow.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any
from urllib.parse import urlsplit

log = logging.getLogger("arena.webhooks")

_WEBHOOK_URL: str | None = None
_SESSION = None  # lazily created requests.Session


def _session():
    global _SESSION
    if _SESSION is None:
        try:
            import requests
            _SESSION = requests.Session()
            _SESSION.headers.update({"Content-Type": "application/json", "User-Agent": "ollama-arena/1.0"})
        except ImportError:
            pass
    return _SESSION


def _webhook_url() -> str | None:
    global _WEBHOOK_URL
    if _WEBHOOK_URL is None:
        _WEBHOOK_URL = os.getenv("ARENA_WEBHOOK_URL", "")
    return _WEBHOOK_URL or None


def _build_payload(event: str, data: dict) -> dict:
    url = _webhook_url() or ""
    if "discord.com/api/webhooks" in url:
        winner = data.get("winner", "draw")
        model_a = data.get("model_a", "?")
        model_b = data.get("model_b", "?")
        color = 0x57F287 if winner != "draw" else 0x5865F2
        return {
            "embeds": [{
                "title": f"Match Complete: {model_a} vs {model_b}",
                "color": color,
                "fields": [
                    {"name": "Category", "value": data.get("category", "?"), "inline": True},
                    {"name": "Score", "value": f"{data.get('score_a', 0)}-{data.get('score_b', 0)}", "inline": True},
                    {"name": "Winner", "value": winner, "inline": True},
                    {"name": "ELO Δ (A)", "value": f"{data.get('elo_delta_a', 0):+.1f}", "inline": True},
                    {"name": "ELO Δ (B)", "value": f"{data.get('elo_delta_b', 0):+.1f}", "inline": True},
                    {"name": "Duration", "value": f"{data.get('duration_s', 0):.1f}s", "inline": True},
                ],
                "footer": {"text": f"ollama-arena • {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}"},
            }]
        }
    if "hooks.slack.com" in url:
        model_a = data.get("model_a", "?")
        model_b = data.get("model_b", "?")
        return {
            "text": (
                f"*Match complete*: `{model_a}` vs `{model_b}` "
                f"({data.get('category', '?')}) — "
                f"score {data.get('score_a', 0)}-{data.get('score_b', 0)}, "
                f"winner: *{data.get('winner', 'draw')}*, "
                f"ELO Δ {data.get('elo_delta_a', 0):+.1f} / {data.get('elo_delta_b', 0):+.1f}"
            )
        }
    return {"event": event, "data": data, "ts": time.time()}


def _redact_url(url: str) -> str:
    """Strip path/query from a webhook URL before logging.

    Discord and Slack webhook URLs embed a bearer-equivalent secret token
    directly in the path (e.g. /api/webhooks/<id>/<token>). Logging the
    full URL — or letting an exception's string form leak it — hands
    anyone with log access the ability to post as the configured webhook.
    """
    try:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}/***"
    except Exception:
        return "<redacted>"


def _post(url: str, payload: dict) -> None:
    sess = _session()
    if sess is None:
        return
    safe_url = _redact_url(url)
    try:
        resp = sess.post(url, json=payload, timeout=8)
        if resp.status_code >= 400:
            log.warning(f"Webhook {safe_url} returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        # Don't interpolate the exception itself: requests/urllib3 errors
        # (e.g. ConnectionError, MaxRetryError) often embed the full
        # request URL — including the secret token — in their message.
        log.warning(f"Webhook POST failed for {safe_url} ({type(e).__name__})")


def notify_match(
    model_a: str, model_b: str, category: str,
    score_a: float, score_b: float,
    elo_a_before: float, elo_a_after: float,
    elo_b_before: float, elo_b_after: float,
    duration_s: float,
) -> None:
    """Send a match-complete notification. Non-blocking."""
    url = _webhook_url()
    if not url:
        return

    if score_a > score_b:
        winner = model_a
    elif score_b > score_a:
        winner = model_b
    else:
        winner = "draw"

    data: dict[str, Any] = {
        "model_a": model_a, "model_b": model_b, "category": category,
        "score_a": score_a, "score_b": score_b, "winner": winner,
        "elo_a_before": elo_a_before, "elo_a_after": elo_a_after,
        "elo_b_before": elo_b_before, "elo_b_after": elo_b_after,
        "elo_delta_a": round(elo_a_after - elo_a_before, 1),
        "elo_delta_b": round(elo_b_after - elo_b_before, 1),
        "duration_s": round(duration_s, 1),
    }
    payload = _build_payload("match_complete", data)
    t = threading.Thread(target=_post, args=(url, payload), daemon=True)
    t.start()
