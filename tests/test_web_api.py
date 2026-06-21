"""Tests for FastAPI web endpoints using TestClient.

The web app is built inside run_web() which ends with uvicorn.run().
We patch uvicorn.run to capture the app, then use starlette.testclient.TestClient.
"""
from __future__ import annotations

import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _app(tmp_path_factory):
    """Build the FastAPI app once for the whole module."""
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    db = tmp_path_factory.mktemp("webapi") / "arena_test.db"
    captured: dict = {}

    def _fake_uvicorn_run(app, **_kw):
        captured["app"] = app

    import ollama_arena.web as _web_mod

    with (
        mock.patch("uvicorn.run", side_effect=_fake_uvicorn_run),
        # Raise rate limit high so tests don't hit 429
        mock.patch.object(_web_mod, "_RL_DEFAULT", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_MATCH", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_PLAYGROUND", "10000/minute"),
        # Don't call Ollama on list_models
        mock.patch(
            "ollama_arena.backends.ollama.OllamaBackend.list_models",
            return_value=["llama3", "phi3"],
        ),
    ):
        from ollama_arena.web import run_web
        run_web(
            host="127.0.0.1",
            port=19_999,
            db_path=str(db),
        )

    assert "app" in captured, "uvicorn.run was not called — app not built"
    return captured["app"]


@pytest.fixture(scope="module")
def client(_app):
    from starlette.testclient import TestClient
    # raise_server_exceptions=False lets us assert on 4xx/5xx codes
    return TestClient(_app, raise_server_exceptions=False)


# ──────────────────────────────────────────────────────────────────────────────
# Security headers
# ──────────────────────────────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_csp_header_present(self, client):
        r = client.get("/api/version")
        assert "Content-Security-Policy" in r.headers

    def test_csp_script_src_no_unsafe_inline(self, client):
        # script-src must stay nonce-only — that's what actually prevents XSS.
        # style-src intentionally allows 'unsafe-inline': CSP nonces can't
        # cover inline style="..." attributes at all (only <style> blocks),
        # and the dynamic content placed in those attributes is already
        # HTML-escaped server-side, so 'unsafe-inline' there is a deliberate,
        # low-risk tradeoff rather than an oversight.
        r = client.get("/api/version")
        csp = r.headers.get("Content-Security-Policy", "")
        script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src"))
        assert "'unsafe-inline'" not in script_src

    def test_csp_has_nonce(self, client):
        r = client.get("/api/version")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "nonce-" in csp

    def test_x_frame_options_deny(self, client):
        r = client.get("/api/version")
        assert r.headers.get("X-Frame-Options") == "DENY"

    def test_x_content_type_nosniff(self, client):
        r = client.get("/api/version")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy(self, client):
        r = client.get("/api/version")
        assert r.headers.get("Referrer-Policy") == "no-referrer"

    def test_no_xss_protection_header(self, client):
        """X-XSS-Protection: 0 disables the broken IE filter."""
        r = client.get("/api/version")
        assert r.headers.get("X-XSS-Protection") == "0"


# ──────────────────────────────────────────────────────────────────────────────
# /api/version
# ──────────────────────────────────────────────────────────────────────────────

class TestVersionEndpoint:
    def test_status_200(self, client):
        r = client.get("/api/version")
        assert r.status_code == 200

    def test_has_version_key(self, client):
        data = client.get("/api/version").json()
        assert "version" in data
        assert isinstance(data["version"], str)


# ──────────────────────────────────────────────────────────────────────────────
# /api/leaderboard
# ──────────────────────────────────────────────────────────────────────────────

class TestLeaderboardEndpoint:
    def test_status_200(self, client):
        r = client.get("/api/leaderboard")
        assert r.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/api/leaderboard").json()
        assert isinstance(data, list)

    def test_anti_leaderboard_200(self, client):
        r = client.get("/api/anti-leaderboard")
        assert r.status_code == 200

    def test_category_leaderboard_200(self, client):
        r = client.get("/api/leaderboard/code")
        assert r.status_code == 200

    def test_category_leaderboard_returns_list(self, client):
        data = client.get("/api/leaderboard/math").json()
        assert isinstance(data, list)


# ──────────────────────────────────────────────────────────────────────────────
# /api/history + /api/history/search
# ──────────────────────────────────────────────────────────────────────────────

class TestHistoryEndpoints:
    def test_history_200(self, client):
        r = client.get("/api/history")
        assert r.status_code == 200

    def test_history_returns_list(self, client):
        data = client.get("/api/history").json()
        assert isinstance(data, list)

    def test_history_search_no_query_returns_all(self, client):
        r = client.get("/api/history/search?q=")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_history_search_with_query(self, client):
        r = client.get("/api/history/search?q=llama")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_history_search_limit(self, client):
        r = client.get("/api/history/search?q=&limit=5")
        assert r.status_code == 200

    def test_history_limit_param(self, client):
        r = client.get("/api/history?limit=10")
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# /api/stats
# ──────────────────────────────────────────────────────────────────────────────

class TestStatsEndpoint:
    def test_status_200(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200

    def test_returns_dict(self, client):
        data = client.get("/api/stats").json()
        assert isinstance(data, dict)


# ──────────────────────────────────────────────────────────────────────────────
# /api/compare
# ──────────────────────────────────────────────────────────────────────────────

class TestCompareEndpoint:
    def test_missing_b_param_400(self, client):
        r = client.get("/api/compare/llama3")
        assert r.status_code == 400

    def test_with_b_param_200(self, client):
        r = client.get("/api/compare/llama3?b=phi3")
        assert r.status_code == 200

    def test_h2h_returns_dict(self, client):
        data = client.get("/api/compare/llama3?b=phi3").json()
        assert isinstance(data, dict)


# ──────────────────────────────────────────────────────────────────────────────
# /api/models/{model}/elo-by-category
# ──────────────────────────────────────────────────────────────────────────────

class TestModelCategoryElos:
    def test_status_200(self, client):
        r = client.get("/api/models/llama3/elo-by-category")
        assert r.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/api/models/llama3/elo-by-category").json()
        assert isinstance(data, list)

    def test_unknown_model_returns_empty_list(self, client):
        data = client.get("/api/models/no_such_model/elo-by-category").json()
        assert data == []


# ──────────────────────────────────────────────────────────────────────────────
# /api/export
# ──────────────────────────────────────────────────────────────────────────────

class TestExportEndpoint:
    def test_json_export_200(self, client):
        r = client.get("/api/export")
        assert r.status_code == 200

    def test_json_export_content_type(self, client):
        r = client.get("/api/export")
        assert "json" in r.headers.get("content-type", "")

    def test_json_export_has_keys(self, client):
        import json
        r = client.get("/api/export")
        data = json.loads(r.content)
        assert "exported_at" in data
        assert "leaderboard" in data
        assert "match_history" in data
        assert "stats" in data

    def test_csv_export_200(self, client):
        r = client.get("/api/export?fmt=csv")
        assert r.status_code == 200

    def test_csv_content_type(self, client):
        r = client.get("/api/export?fmt=csv")
        assert "csv" in r.headers.get("content-type", "")

    def test_csv_has_header_row(self, client):
        r = client.get("/api/export?fmt=csv")
        first_line = r.text.split("\n")[0]
        assert "model_a" in first_line
        assert "model_b" in first_line

    def test_csv_content_disposition(self, client):
        r = client.get("/api/export?fmt=csv")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".csv" in cd


# ──────────────────────────────────────────────────────────────────────────────
# /api/categories + /api/perf + /api/datasets
# ──────────────────────────────────────────────────────────────────────────────

class TestInfoEndpoints:
    def test_categories_200(self, client):
        r = client.get("/api/categories")
        assert r.status_code == 200

    def test_categories_has_list(self, client):
        data = client.get("/api/categories").json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_perf_200(self, client):
        r = client.get("/api/perf")
        assert r.status_code == 200

    def test_perf_has_models_list(self, client):
        # static/js/match.js's loadPerf() reads data.models — pin the
        # contract so frontend and backend can't silently drift apart again
        # (this previously broke the Performance tab with no test catching it).
        data = client.get("/api/perf").json()
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_datasets_200(self, client):
        r = client.get("/api/datasets")
        assert r.status_code == 200

    def test_system_200(self, client):
        r = client.get("/api/system")
        assert r.status_code == 200

    def test_system_has_cpu_field(self, client):
        data = client.get("/api/system").json()
        assert "cpu_pct" in data or "ts" in data


# ──────────────────────────────────────────────────────────────────────────────
# /api/models
# ──────────────────────────────────────────────────────────────────────────────

class TestModelsEndpoint:
    def test_models_200(self, client):
        r = client.get("/api/models")
        assert r.status_code == 200

    def test_models_returns_list(self, client):
        # list_models is mocked → ["llama3", "phi3"]
        data = client.get("/api/models").json()
        assert isinstance(data, list)

    def test_models_caps_use_batched_parallel_detection(self, client, monkeypatch):
        # api_models() used to call model_caps.get() once per model in a
        # serial loop -- a cache miss did a blocking ~10s HTTP call per
        # model. It must now call detect_all() once with the full model
        # list instead (detect_all runs the per-model probes in parallel
        # threads), not get() in a loop.
        calls = []

        def fake_detect_all(names, ollama_url):
            calls.append(list(names))
            return {n: {"vision": False} for n in names}

        def fail_if_called(*a, **kw):
            raise AssertionError("get() must not be called directly from api_models()")

        monkeypatch.setattr("ollama_arena.model_caps.detect_all", fake_detect_all)
        monkeypatch.setattr("ollama_arena.model_caps.get", fail_if_called)
        client.get("/api/models")
        assert len(calls) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Task endpoints
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskEndpoints:
    def test_task_history_unknown_returns_empty(self, client):
        r = client.get("/api/task/nonexistent-task-id")
        assert r.status_code == 200
        data = r.json()
        assert "runs" in data
        assert data["runs"] == []

    def test_agent_trace_unknown_match(self, client):
        r = client.get("/api/agent_trace/999999")
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data
        assert data["tasks"] == []


# ──────────────────────────────────────────────────────────────────────────────
# Response caching (1s TTL — same request twice should be idempotent)
# ──────────────────────────────────────────────────────────────────────────────

class TestResponseCaching:
    def test_leaderboard_stable(self, client):
        r1 = client.get("/api/leaderboard").json()
        r2 = client.get("/api/leaderboard").json()
        assert r1 == r2

    def test_history_stable(self, client):
        r1 = client.get("/api/history").json()
        r2 = client.get("/api/history").json()
        assert r1 == r2


# ──────────────────────────────────────────────────────────────────────────────
# /api/report/{model}
# ──────────────────────────────────────────────────────────────────────────────

class TestReportEndpoint:
    def test_report_unknown_model_200(self, client):
        r = client.get("/api/report/no_such_model")
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Charts endpoints (HTML fragments)
# ──────────────────────────────────────────────────────────────────────────────

class TestChartEndpoints:
    def test_elo_chart_200(self, client):
        r = client.get("/charts/elo")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()

    def test_radar_chart_200(self, client):
        r = client.get("/charts/radar")
        assert r.status_code == 200

    def test_heatmap_chart_200(self, client):
        r = client.get("/charts/heatmap")
        assert r.status_code == 200

    def test_perf_chart_200(self, client):
        r = client.get("/charts/perf")
        assert r.status_code == 200

    def test_leaderboard_chart_200(self, client):
        r = client.get("/charts/leaderboard")
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# /api/hardware/scan + /genome redirect
# ──────────────────────────────────────────────────────────────────────────────

class TestHardwareScan:
    def test_hardware_scan_200(self, client):
        r = client.get("/api/hardware/scan")
        assert r.status_code == 200

    def test_hardware_scan_shape(self, client):
        data = client.get("/api/hardware/scan").json()
        assert set(data) == {"hardware", "models", "best_two"}
        assert "total_ram_gb" in data["hardware"]
        assert "usable_ram_gb" in data["hardware"]
        assert isinstance(data["models"], list)
        assert isinstance(data["best_two"], list)

    def test_hardware_scan_unreachable_ollama_returns_empty_models(self, client, monkeypatch):
        import requests
        monkeypatch.setattr(requests, "get",
                             mock.Mock(side_effect=ConnectionError("offline")))
        data = client.get("/api/hardware/scan").json()
        assert data["models"] == []
        assert data["best_two"] == []


class TestGenomeRedirect:
    def test_genome_page_redirects_to_tab(self, client):
        r = client.get("/genome", follow_redirects=False)
        assert r.status_code in (302, 307)
        assert r.headers["location"] == "/#genome"
