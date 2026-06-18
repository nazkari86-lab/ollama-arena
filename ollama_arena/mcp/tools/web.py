"""Web search and fetch tools."""
from __future__ import annotations

import re
from typing import Callable

import requests


def ddg_search(args: dict) -> str:
    query = args.get("query") or args.get("q") or ""
    if not query:
        return "Error: No query provided."
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(
            f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}",
            headers=headers,
            timeout=10,
        )
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        res = [
            f"{i + 1}. {re.sub(r'<[^>]+>', '', titles[i]).strip()}"
            for i in range(min(5, len(titles)))
        ]
        return f"Results for '{query}':\n" + "\n".join(res) if res else "No results."
    except Exception as exc:
        return f"Error: {exc}"


def web_fetch(args: dict) -> str:
    url = args.get("url", "")
    if not url:
        return "Error: No url provided."
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        text = re.sub(
            r"<(script|style).*?>.*?</\1>",
            "",
            resp.text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return f"Content of {url}:\n\n" + re.sub(r"<[^>]+>", " ", text)[:4000]
    except Exception as exc:
        return f"Error: {exc}"


def wikipedia_search(args: dict) -> str:
    query = args.get("query") or args.get("q") or ""
    if not query:
        return "Error: No query provided."
    try:
        headers = {"User-Agent": "ollama-arena/1.1"}
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
            },
            headers=headers,
            timeout=10,
        )
        search_resp.raise_for_status()
        hits = search_resp.json().get("query", {}).get("search", [])
        if not hits:
            return f"No Wikipedia results for '{query}'."

        title = hits[0]["title"]
        summary_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": title,
                "format": "json",
            },
            headers=headers,
            timeout=10,
        )
        summary_resp.raise_for_status()
        pages = summary_resp.json().get("query", {}).get("pages", {})
        extract = next(iter(pages.values()), {}).get("extract", "")
        return f"Wikipedia: {title}\n\n{extract[:4000]}"
    except Exception as exc:
        return f"Error: {exc}"


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    """Return (name, handler, schema, danger_tier) tuples."""
    return [
        (
            "google_web_search",
            ddg_search,
            {
                "type": "function",
                "function": {
                    "name": "google_web_search",
                    "description": "Search the web via DuckDuckGo.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            "safe",
        ),
        (
            "ddg_search",
            ddg_search,
            {
                "type": "function",
                "function": {
                    "name": "ddg_search",
                    "description": "Search the web via DuckDuckGo HTML scraping.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            "safe",
        ),
        (
            "web_fetch",
            web_fetch,
            {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "Download a URL and return stripped text content.",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                },
            },
            "confirm",
        ),
        (
            "wikipedia_search",
            wikipedia_search,
            {
                "type": "function",
                "function": {
                    "name": "wikipedia_search",
                    "description": "Search Wikipedia and return the top article summary.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            "safe",
        ),
    ]
