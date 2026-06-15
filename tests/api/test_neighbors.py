"""GET /v1/spaces/{space}/node/{id}/neighbors — graph expansion."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_scout_core


@requires_scout_core
def test_neighbors_from_symbol(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    symbols = indexed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/", "kinds": ["function"]},
    ).json()["symbols"]
    assert symbols
    node_id = symbols[0]["node_id"]

    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/node/{node_id}/neighbors",
        params={"depth": 3, "max_nodes": 20},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_id"] == node_id
    assert "neighbors" in data


@requires_scout_core
def test_neighbors_unknown_node_404(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/node/deadbeefdeadbeef/neighbors",
    )
    assert resp.status_code == 404
