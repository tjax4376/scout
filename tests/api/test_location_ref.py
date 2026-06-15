"""location_ref on graph API responses."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_scout_core


@requires_scout_core
def test_symbols_include_location_ref(
    indexed_api_client: TestClient, indexed_space
) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/"},
    )
    assert resp.status_code == 200
    symbols = resp.json()["symbols"]
    assert symbols
    for sym in symbols:
        assert sym["location_ref"]
        assert "=" in sym["location_ref"]
        assert sym["location_ref"].split("=", 1)[1].startswith("/")


@requires_scout_core
def test_neighbors_include_location_ref(
    indexed_api_client: TestClient, indexed_space
) -> None:
    space, _ = indexed_space
    symbols = indexed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/auth.py"},
    ).json()["symbols"]
    node_id = symbols[0]["node_id"]
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/node/{node_id}/neighbors",
        params={"depth": 2},
    )
    assert resp.status_code == 200
    for neighbor in resp.json()["neighbors"]:
        if neighbor.get("rel_path"):
            assert neighbor.get("location_ref")
