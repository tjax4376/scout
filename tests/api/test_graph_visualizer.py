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
    # Cavern tab (graph-webui-cavern)
    assert 'data-tab="cavern"' in resp.text
    assert ">Cavern<" in resp.text
    assert 'id="memory-index"' in resp.text
    assert 'id="linked-files-index"' in resp.text
    assert 'id="memory-detail"' in resp.text
    assert 'id="api-key"' in resp.text


@requires_scout_core
def test_cavern_list_get_neighbors_contract(
    indexed_api_client: TestClient, indexed_space
) -> None:
    """Cavern WebUI flow: list memories → get detail → expand mem-* neighbors."""
    space, _ = indexed_space
    create = indexed_api_client.post(
        f"/v1/spaces/{space}/memory",
        json={
            "title": "Auth notes",
            "body": (
                "Auth lives in workspace path:\n"
                "src/auth.py\n"
                "Use authenticate helpers carefully."
            ),
            "category": "api",
            "tags": ["cavern"],
        },
    )
    assert create.status_code == 201
    memory = create.json()
    memory_id = memory["id"]
    assert memory["rel_path"] == f"scout/memories/{memory_id}.md"

    # Canonical global list
    listed = indexed_api_client.get("/v1/memories")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] >= 1
    assert any(m["id"] == memory_id for m in payload["memories"])
    listed_item = next(m for m in payload["memories"] if m["id"] == memory_id)
    assert "body" not in listed_item or listed_item.get("body") is None

    detail = indexed_api_client.get(f"/v1/memory/{memory_id}")
    assert detail.status_code == 200
    assert detail.json()["body"]
    assert detail.json()["title"] == "Auth notes"

    node_id = f"mem-{memory_id}"
    neighbors = indexed_api_client.get(
        f"/v1/spaces/{space}/node/{node_id}/neighbors",
        params={"depth": 1, "max_nodes": 50},
    )
    assert neighbors.status_code == 200
    data = neighbors.json()
    assert data["node_id"] == node_id
    assert "neighbors" in data
    assert any(
        (n.get("rel_path") == "src/auth.py") or ("auth" in (n.get("rel_path") or ""))
        for n in data["neighbors"]
    )
