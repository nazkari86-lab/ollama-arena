"""Browser automation tools (Playwright optional)."""
from __future__ import annotations

import json
from typing import Callable


def browser_use(args: dict) -> str:
    action = args.get("action", "navigate")
    url = args.get("url", "")
    selector = args.get("selector", "")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "Error: Playwright is not installed. "
            "Install with: pip install playwright && playwright install chromium"
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            if action == "navigate" and url:
                page.goto(url, timeout=15000)
                content = page.content()[:4000]
                browser.close()
                return f"Navigated to {url}. Page content preview:\n{content}"
            if action == "click" and selector:
                if url:
                    page.goto(url, timeout=15000)
                page.click(selector, timeout=10000)
                content = page.content()[:4000]
                browser.close()
                return f"Clicked '{selector}'. Page content preview:\n{content}"
            if action == "scrape" and selector:
                if url:
                    page.goto(url, timeout=15000)
                text = page.inner_text(selector)[:4000]
                browser.close()
                return f"Scraped '{selector}':\n{text}"
            browser.close()
            return "Error: browser_use requires action + url and/or selector."
    except Exception as exc:
        return f"Error: {exc}"


def mock_browser_navigate(args: dict) -> str:
    url = args.get("url", "about:blank")
    return json.dumps({"status": "ok", "url": url, "title": "Mock Browser Page"})


def tool_defs(include_mock: bool = False) -> list[tuple[str, Callable[[dict], str], dict, str]]:
    defs: list[tuple[str, Callable[[dict], str], dict, str]] = [
        (
            "browser_use",
            browser_use,
            {
                "type": "function",
                "function": {
                    "name": "browser_use",
                    "description": (
                        "Automate Chromium via Playwright: navigate, click CSS selectors, scrape."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["navigate", "click", "scrape"],
                            },
                            "url": {"type": "string"},
                            "selector": {"type": "string"},
                        },
                        "required": ["action"],
                    },
                },
            },
            "confirm",
        ),
    ]
    if include_mock:
        defs.append(
            (
                "browser_navigate",
                mock_browser_navigate,
                {
                    "type": "function",
                    "function": {
                        "name": "browser_navigate",
                        "description": "Navigate a browser to a URL (mock for benchmarks).",
                        "parameters": {
                            "type": "object",
                            "properties": {"url": {"type": "string"}},
                            "required": ["url"],
                        },
                    },
                },
                "confirm",
            )
        )
    return defs
