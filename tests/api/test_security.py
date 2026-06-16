"""Security hardening tests for Scout API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from scout.api.app import create_app
from scout.config import ScoutConfig, SpaceEntry, load_config, save_config
from tests.api.conftest import save_spaces_config


def _auth_client(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    config = load_config(scout_home)
    config.api.auth.enabled = True
    config.api.auth.key = "read-key"
    config.api.auth.admin_key = "admin-key"
    config.api.rate_limit.search_per_minute = 2
    config.api.rate_limit.reindex_per_hour = 1
    save_config(scout_home, config)
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    return TestClient(create_app())


def test_auth_missing_returns_401(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _auth_client(scout_home, monkeypatch)
    resp = client.get("/v1/spaces/list")
    assert resp.status_code == 401


def test_auth_read_key_allows_list(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _auth_client(scout_home, monkeypatch)
    resp = client.get("/v1/spaces/list", headers={"Authorization": "Bearer read-key"})
    assert resp.status_code == 200


def test_auth_health_public_without_token(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _auth_client(scout_home, monkeypatch)
    resp = client.get("/v1/health")
    assert resp.status_code == 200


def test_admin_reindex_forbidden_with_read_key(
    sample_project: Path,
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_spaces_config(
        scout_home,
        {"demo": SpaceEntry(name="demo", root=str(sample_project))},
    )
    client = _auth_client(scout_home, monkeypatch)
    resp = client.post(
        "/v1/spaces/demo/reindex",
        headers={"Authorization": "Bearer read-key"},
    )
    assert resp.status_code == 403


def test_security_headers_present(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    resp = client.get("/v1/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("Content-Security-Policy") == "default-src 'self'"


def test_https_redirect_on_health(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_config(scout_home)
    config.api.force_https = True
    save_config(scout_home, config)
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    resp = client.get("/v1/health", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"].startswith("https://")


def test_hsts_header_when_forwarded_https(
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    resp = client.get("/v1/health", headers={"X-Forwarded-Proto": "https"})
    assert resp.status_code == 200
    assert "max-age=31536000" in resp.headers.get("Strict-Transport-Security", "")


def test_graph_static_cache_control(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    resp = client.get("/graph/index.html")
    if resp.status_code == 200:
        assert resp.headers.get("Cache-Control") == "no-store"


def test_graph_csp_allows_inline(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    resp = client.get("/graph/index.html")
    if resp.status_code == 200:
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "unsafe-inline" in csp


def test_search_rate_limit_returns_429(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_config(scout_home)
    config.api.auth.enabled = False
    config.api.rate_limit.search_per_minute = 1
    save_config(scout_home, config)
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    first = client.post("/v1/spaces/missing/search", json={"query": "x"})
    second = client.post("/v1/spaces/missing/search", json={"query": "x"})
    assert first.status_code != 429
    assert second.status_code == 429
    assert second.headers.get("Retry-After")


def test_rate_limit_per_token_not_shared(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_config(scout_home)
    config.api.auth.enabled = False
    config.api.rate_limit.search_per_minute = 1
    save_config(scout_home, config)
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    body = {"query": "x"}
    first_a = client.post(
        "/v1/spaces/missing/search",
        json=body,
        headers={"Authorization": "Bearer token-a"},
    )
    first_b = client.post(
        "/v1/spaces/missing/search",
        json=body,
        headers={"Authorization": "Bearer token-b"},
    )
    second_a = client.post(
        "/v1/spaces/missing/search",
        json=body,
        headers={"Authorization": "Bearer token-a"},
    )
    assert first_a.status_code != 429
    assert first_b.status_code != 429
    assert second_a.status_code == 429


def test_reindex_rate_limit_returns_429(
    sample_project: Path,
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scout.api.app as api_app

    save_spaces_config(
        scout_home,
        {"demo": SpaceEntry(name="demo", root=str(sample_project))},
    )
    config = load_config(scout_home)
    config.api.auth.enabled = True
    config.api.auth.key = "read-key"
    config.api.auth.admin_key = "admin-key"
    config.api.rate_limit.reindex_per_hour = 1
    save_config(scout_home, config)
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    monkeypatch.setattr(api_app, "run_reindex", AsyncMock(return_value="v1"))
    client = TestClient(create_app())
    headers = {"Authorization": "Bearer admin-key"}
    first = client.post("/v1/spaces/demo/reindex", headers=headers)
    second = client.post("/v1/spaces/demo/reindex", headers=headers)
    assert first.status_code != 429
    assert second.status_code == 429


def test_path_traversal_blocked_at_api(
    sample_project: Path,
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_spaces_config(
        scout_home,
        {"demo": SpaceEntry(name="demo", root=str(sample_project))},
    )
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    resp = client.get("/v1/spaces/demo/file", params={"rel_path": "../outside.py"})
    assert resp.status_code == 400


def test_authenticated_file_read(
    tmp_path: Path,
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json as json_mod

    import scout.api.app as api_app

    class _FakeCore:
        @staticmethod
        def py_read_workspace_file(*args, **kwargs) -> str:
            return json_mod.dumps({"text": "x = 1\n", "rel_path": "main.py"})

        @staticmethod
        def py_check_staleness(*args, **kwargs) -> tuple[bool, str]:
            return False, "v1"

    src = tmp_path / "main.py"
    src.write_text("x = 1\n", encoding="utf-8")
    save_spaces_config(
        scout_home,
        {"demo": SpaceEntry(name="demo", root=str(tmp_path))},
    )
    monkeypatch.setattr(api_app, "scout_core", _FakeCore())
    client = _auth_client(scout_home, monkeypatch)
    resp = client.get(
        "/v1/spaces/demo/file",
        params={"rel_path": "main.py"},
        headers={"Authorization": "Bearer read-key"},
    )
    assert resp.status_code == 200
    assert "text" in resp.json()


def test_internal_error_masked(
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    monkeypatch.setattr("scout.api.app.scout_core", None)
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/v1/spaces/demo/node/n1")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "internal server error"
