"""Tests for graph search and file aggregate REST endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_scout_core


@requires_scout_core
def test_graph_search_symbol_match(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/graph/search",
        params={"q": "authenticate"},
    )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits
    assert any("authenticate" in str(h.get("symbol", "")).lower() for h in hits)
    assert resp.headers.get("X-Scout-Stale") in {"true", "false"}


@requires_scout_core
def test_graph_search_path_match(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/graph/search",
        params={"q": "auth.py"},
    )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits
    assert any("auth.py" in str(h.get("rel_path", "")) for h in hits)


@requires_scout_core
def test_graph_search_empty_query_400(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/graph/search",
        params={"q": "   "},
    )
    assert resp.status_code == 422 or resp.status_code == 400


@requires_scout_core
def test_graph_search_unknown_space(api_client: TestClient) -> None:
    resp = api_client.get(
        "/v1/spaces/missing/graph/search",
        params={"q": "auth"},
    )
    assert resp.status_code == 404


@requires_scout_core
def test_graph_file_symbols_and_neighbors(
    indexed_api_client: TestClient, indexed_space
) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/graph/file",
        params={"rel_path": "src/auth.py"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["rel_path"] == "src/auth.py"
    assert payload["symbols"]
    assert "authenticate" in str(payload["symbols"][0].get("symbol", "")).lower()
    assert "edges" in payload
    assert "truncated" in payload


@requires_scout_core
def test_graph_file_invalid_path_400(
    indexed_api_client: TestClient, indexed_space
) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/graph/file",
        params={"rel_path": "../etc/passwd"},
    )
    assert resp.status_code == 400


@requires_scout_core
def test_graph_file_truncation_flag(
    indexed_api_client: TestClient, indexed_space, monkeypatch
) -> None:
    from scout.api import graph_file as graph_file_mod

    space, _ = indexed_space

    def _fake_aggregate(graph_path: str, rel_path: str, *, max_nodes: int = 200):
        return {
            "rel_path": rel_path,
            "symbols": [{"node_id": "a", "kind": "function", "symbol": "fn"}],
            "neighbors": [],
            "edges": [],
            "truncated": True,
        }

    monkeypatch.setattr(graph_file_mod, "aggregate_file_graph", _fake_aggregate)
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/graph/file",
        params={"rel_path": "src/auth.py", "max_nodes": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["truncated"] is True


@requires_scout_core
def test_graph_static_page(indexed_api_client: TestClient) -> None:
    resp = indexed_api_client.get("/graph/")
    assert resp.status_code == 200
    assert "Scout Graph" in resp.text
