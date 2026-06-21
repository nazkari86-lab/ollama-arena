"""Tests for mcp/tools/browser.py."""
from __future__ import annotations
import sys
import unittest.mock as mock
import pytest


class TestBrowserUse:
    def test_no_playwright_returns_error(self):
        from ollama_arena.mcp.tools.browser import browser_use
        with mock.patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            result = browser_use({"action": "navigate", "url": "http://example.com"})
        assert "not installed" in result.lower() or "Error" in result

    def test_navigate_success(self):
        from ollama_arena.mcp.tools.browser import browser_use
        mock_page = mock.MagicMock()
        mock_page.content.return_value = "<html><body>Hello</body></html>"
        mock_browser = mock.MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = mock.MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_playwright_ctx = mock.MagicMock()
        mock_playwright_ctx.__enter__ = mock.MagicMock(return_value=mock_p)
        mock_playwright_ctx.__exit__ = mock.MagicMock(return_value=False)
        mock_sync = mock.MagicMock(return_value=mock_playwright_ctx)
        mock_module = mock.MagicMock()
        mock_module.sync_playwright = mock_sync
        with mock.patch.dict(sys.modules, {"playwright": mock.MagicMock(), "playwright.sync_api": mock_module}):
            result = browser_use({"action": "navigate", "url": "http://example.com"})
        assert "example.com" in result or "Navigated" in result or "Hello" in result

    def test_click_success(self):
        from ollama_arena.mcp.tools.browser import browser_use
        mock_page = mock.MagicMock()
        mock_page.content.return_value = "<html><body>Clicked</body></html>"
        mock_browser = mock.MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = mock.MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_playwright_ctx = mock.MagicMock()
        mock_playwright_ctx.__enter__ = mock.MagicMock(return_value=mock_p)
        mock_playwright_ctx.__exit__ = mock.MagicMock(return_value=False)
        mock_sync = mock.MagicMock(return_value=mock_playwright_ctx)
        mock_module = mock.MagicMock()
        mock_module.sync_playwright = mock_sync
        with mock.patch.dict(sys.modules, {"playwright": mock.MagicMock(), "playwright.sync_api": mock_module}):
            result = browser_use({"action": "click", "url": "http://x.com", "selector": "#btn"})
        assert "Clicked" in result or "btn" in result

    def test_scrape_success(self):
        from ollama_arena.mcp.tools.browser import browser_use
        mock_page = mock.MagicMock()
        mock_page.inner_text.return_value = "Scraped text here"
        mock_browser = mock.MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = mock.MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_playwright_ctx = mock.MagicMock()
        mock_playwright_ctx.__enter__ = mock.MagicMock(return_value=mock_p)
        mock_playwright_ctx.__exit__ = mock.MagicMock(return_value=False)
        mock_sync = mock.MagicMock(return_value=mock_playwright_ctx)
        mock_module = mock.MagicMock()
        mock_module.sync_playwright = mock_sync
        with mock.patch.dict(sys.modules, {"playwright": mock.MagicMock(), "playwright.sync_api": mock_module}):
            result = browser_use({"action": "scrape", "selector": ".content"})
        assert "Scraped" in result or "Scraped text" in result

    def test_no_action_no_url(self):
        from ollama_arena.mcp.tools.browser import browser_use
        mock_page = mock.MagicMock()
        mock_browser = mock.MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = mock.MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_playwright_ctx = mock.MagicMock()
        mock_playwright_ctx.__enter__ = mock.MagicMock(return_value=mock_p)
        mock_playwright_ctx.__exit__ = mock.MagicMock(return_value=False)
        mock_sync = mock.MagicMock(return_value=mock_playwright_ctx)
        mock_module = mock.MagicMock()
        mock_module.sync_playwright = mock_sync
        with mock.patch.dict(sys.modules, {"playwright": mock.MagicMock(), "playwright.sync_api": mock_module}):
            result = browser_use({"action": "navigate"})  # no url
        assert "Error" in result or "requires" in result

    def test_exception_returns_error(self):
        from ollama_arena.mcp.tools.browser import browser_use
        mock_playwright_ctx = mock.MagicMock()
        mock_playwright_ctx.__enter__ = mock.MagicMock(side_effect=Exception("launch failed"))
        mock_playwright_ctx.__exit__ = mock.MagicMock(return_value=False)
        mock_sync = mock.MagicMock(return_value=mock_playwright_ctx)
        mock_module = mock.MagicMock()
        mock_module.sync_playwright = mock_sync
        with mock.patch.dict(sys.modules, {"playwright": mock.MagicMock(), "playwright.sync_api": mock_module}):
            result = browser_use({"action": "navigate", "url": "http://x.com"})
        assert "Error" in result

    def test_click_with_no_url(self):
        from ollama_arena.mcp.tools.browser import browser_use
        mock_page = mock.MagicMock()
        mock_page.content.return_value = "<html>after click</html>"
        mock_browser = mock.MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = mock.MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_playwright_ctx = mock.MagicMock()
        mock_playwright_ctx.__enter__ = mock.MagicMock(return_value=mock_p)
        mock_playwright_ctx.__exit__ = mock.MagicMock(return_value=False)
        mock_sync = mock.MagicMock(return_value=mock_playwright_ctx)
        mock_module = mock.MagicMock()
        mock_module.sync_playwright = mock_sync
        with mock.patch.dict(sys.modules, {"playwright": mock.MagicMock(), "playwright.sync_api": mock_module}):
            result = browser_use({"action": "click", "selector": "#btn"})  # no url
        # should click without navigating first
        mock_page.goto.assert_not_called()


class TestMockBrowserNavigate:
    def test_default_url(self):
        from ollama_arena.mcp.tools.browser import mock_browser_navigate
        import json
        result = mock_browser_navigate({})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert data["url"] == "about:blank"

    def test_custom_url(self):
        from ollama_arena.mcp.tools.browser import mock_browser_navigate
        import json
        result = mock_browser_navigate({"url": "http://test.com"})
        data = json.loads(result)
        assert data["url"] == "http://test.com"
        assert "title" in data
