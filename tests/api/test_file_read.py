"""GET /v1/spaces/{space}/file — workspace file read."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import requires_scout_core


@requires_scout_core
def test_read_full_file(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/file",
        params={"rel_path": "src/auth.py"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "authenticate" in data["text"]
    assert data["total_lines"] >= 3


@requires_scout_core
def test_read_line_range(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/file",
        params={"rel_path": "src/auth.py", "start_line": 1, "end_line": 2},
    )
    assert resp.status_code == 200
    assert "authenticate" in resp.json()["text"]
    assert "logout" not in resp.json()["text"]


@requires_scout_core
def test_file_traversal_rejected(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/file",
        params={"rel_path": "../../../etc/passwd"},
    )
    assert resp.status_code == 400


@requires_scout_core
def test_file_too_large_413(indexed_api_client: TestClient, indexed_space, sample_project) -> None:
    space, _ = indexed_space
    big = sample_project / "big.txt"
    chunk = "x" * 65536
    with big.open("w", encoding="utf-8") as handle:
        for _ in range(8):
            handle.write(chunk)
        handle.write("x")
    resp = indexed_api_client.get(
        f"/v1/spaces/{space}/file",
        params={"rel_path": "big.txt"},
    )
    assert resp.status_code == 413
