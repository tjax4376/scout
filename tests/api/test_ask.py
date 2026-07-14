"""API tests for POST /v1/spaces/{space}/ask.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: ask-scout-structure — graph-only ask endpoint coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from scout.api.app import create_app
from scout.config import ScoutConfig, SpaceEntry, load_config, save_config
from tests.conftest import requires_scout_core


@requires_scout_core
def test_ask_returns_structure_hits(indexed_api_client: TestClient, indexed_space) -> None:
    space, _home = indexed_space
    resp = indexed_api_client.post(
        f"/v1/spaces/{space}/ask",
        json={"query": "auth", "expand_depth": 0},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "graph"
    assert data["query"] == "auth"
    assert isinstance(data["hits"], list)
    assert data["total"] == len(data["hits"])
    for hit in data["hits"]:
        assert "compressed_text" not in hit
        assert "text" not in hit
        if hit.get("node_id"):
            assert "location_ref" in hit or hit.get("rel_path")


@requires_scout_core
def test_ask_graph_only_not_503(indexed_api_client: TestClient, indexed_space) -> None:
    space, _home = indexed_space
    resp = indexed_api_client.post(
        f"/v1/spaces/{space}/ask",
        json={"query": "auth"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "graph"


@requires_scout_core
def test_ask_empty_query_422(indexed_api_client: TestClient, indexed_space) -> None:
    space, _home = indexed_space
    resp = indexed_api_client.post(
        f"/v1/spaces/{space}/ask",
        json={"query": ""},
    )
    assert resp.status_code == 422  # Pydantic validation (min_length=1)


@requires_scout_core
def test_ask_unknown_space_404(indexed_api_client: TestClient, indexed_space) -> None:
    _space, _home = indexed_space
    resp = indexed_api_client.post(
        "/v1/spaces/nope/ask",
        json={"query": "auth"},
    )
    assert resp.status_code == 404


@requires_scout_core
def test_ask_missing_graph_404(
    api_client: TestClient,
    scout_home: Path,
    sample_project: Path,
) -> None:
    save_config(
        scout_home,
        ScoutConfig(spaces={"bare": SpaceEntry(name="bare", root=str(sample_project))}),
    )
    resp = api_client.post("/v1/spaces/bare/ask", json={"query": "auth"})
    assert resp.status_code == 404
    assert "graph" in resp.json()["detail"].lower()


def test_ask_auth_required_401(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_config(scout_home)
    config.api.auth.enabled = True
    config.api.auth.key = "read-key"
    config.api.auth.admin_key = "admin-key"
    save_config(scout_home, config)
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    client = TestClient(create_app())
    resp = client.post("/v1/spaces/any/ask", json={"query": "auth"})
    assert resp.status_code == 401


@requires_scout_core
def test_ask_does_not_call_embed(
    indexed_api_client: TestClient,
    indexed_space,
) -> None:
    space, _home = indexed_space
    with patch("scout.api.app.build_provider") as build_provider:
        resp = indexed_api_client.post(
            f"/v1/spaces/{space}/ask",
            json={"query": "auth", "expand_depth": 1, "max_nodes": 20},
        )
        assert resp.status_code == 200
        build_provider.assert_not_called()
