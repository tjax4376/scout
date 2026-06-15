"""GET /v1/spaces/{space}/node/{id} — graph metadata + location_ref."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_scout_core


@requires_scout_core
def test_node_returns_location_ref(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    symbols = indexed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/auth.py"},
    ).json()["symbols"]
    fn = next(s for s in symbols if s.get("symbol") == "authenticate")

    resp = indexed_api_client.get(f"/v1/spaces/{space}/node/{fn['node_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["location_ref"] == "src=/src/auth.py"
    assert data["text"] == ""
    assert data["score"] == 0.0

    file_resp = indexed_api_client.get(
        f"/v1/spaces/{space}/file",
        params={
            "rel_path": "src/auth.py",
            "start_line": data["start_line"],
            "end_line": data["end_line"],
        },
    )
    assert file_resp.status_code == 200
    assert "authenticate" in file_resp.json()["text"]
