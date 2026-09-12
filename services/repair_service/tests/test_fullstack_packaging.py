"""Tests for full-stack packaging, static asset serving, and strict JSON 404s."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from benchbook.interfaces.http.app import create_app


def test_strict_json_404_on_unknown_api_endpoints() -> None:
    """Verify any unknown /api/* request returns strict JSON 404 with standard envelope."""
    app = create_app(":memory:", assistant_mode="deterministic")
    client = TestClient(app)

    for method in ["get", "post", "put", "delete", "patch"]:
        caller = getattr(client, method)
        resp = caller("/api/nonexistent_subroute")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"] == "NOT_FOUND"
        assert "not found" in data["message"].lower()

    # Base /api route
    resp = client.get("/api")
    assert resp.status_code == 404
    assert resp.json()["error"] == "NOT_FOUND"


def test_fullstack_spa_serving_when_static_dir_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify FastAPI serves index.html and SPA fallback routes when static dir is configured."""
    with tempfile.TemporaryDirectory() as tmpdir:
        static_path = Path(tmpdir)
        index_file = static_path / "index.html"
        index_file.write_text(
            "<!DOCTYPE html><html><body>Benchbook App Root</body></html>", encoding="utf-8"
        )

        assets_dir = static_path / "assets"
        assets_dir.mkdir()
        bundle_file = assets_dir / "index-test.js"
        bundle_file.write_text("console.log('benchbook bundle');", encoding="utf-8")

        monkeypatch.setenv("BENCHBOOK_STATIC_DIR", str(static_path))

        app = create_app(":memory:", assistant_mode="deterministic")
        client = TestClient(app)

        # 1. Root serves index.html
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Benchbook App Root" in resp.text

        # 2. Static asset is served
        asset_resp = client.get("/assets/index-test.js")
        assert asset_resp.status_code == 200
        assert "benchbook bundle" in asset_resp.text

        # 3. Client-side SPA routes fallback to index.html
        spa_resp = client.get("/jobs/test-uuid-101")
        assert spa_resp.status_code == 200
        assert "Benchbook App Root" in spa_resp.text

        # 4. Unknown API route still returns strict JSON 404
        api_resp = client.get("/api/jobs/missing/action")
        assert api_resp.status_code == 404
        assert api_resp.json()["error"] == "NOT_FOUND"


def test_fallback_when_static_dir_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify 404 JSON fallback when static files are missing."""
    monkeypatch.setenv("BENCHBOOK_STATIC_DIR", "/nonexistent/static/dir")

    app = create_app(":memory:", assistant_mode="deterministic")
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 404
    assert resp.json()["error"] == "NOT_FOUND"
