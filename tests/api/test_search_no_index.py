"""POST /search when vector index absent."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_scout_core


@requires_scout_core
def test_search_503_without_index_db(
    indexed_api_client: TestClient, indexed_space
) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.post(
        f"/v1/spaces/{space}/search",
        json={"query": "auth"},
    )
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "vector index" in str(detail).lower()
