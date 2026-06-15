"""GET /v1/spaces/{space}/symbols — graph-only symbol listing."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_scout_core


@requires_scout_core
def test_symbols_list_under_prefix(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "symbols" in data
    assert len(data["symbols"]) >= 1
    assert all(s["rel_path"].startswith("src/") for s in data["symbols"])


@requires_scout_core
def test_symbols_kind_filter(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/", "kinds": ["function"]},
    )
    assert resp.status_code == 200
    for sym in resp.json()["symbols"]:
        assert sym["kind"] == "function"


@requires_scout_core
def test_symbols_missing_prefix_422(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(f"/v1/spaces/{space}/symbols")
    assert resp.status_code == 422
