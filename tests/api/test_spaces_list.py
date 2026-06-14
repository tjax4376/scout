"""GET /v1/spaces/list — contract tests per api-contracts.md."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from scout.config import SpaceEntry

from tests.api.conftest import save_spaces_config


def test_spaces_list_empty(api_client: TestClient) -> None:
    resp = api_client.get("/v1/spaces/list")
    assert resp.status_code == 200
    assert resp.json() == {"spaces": []}


def test_spaces_list_sorted_alphabetically(
    api_client: TestClient, scout_home: Path
) -> None:
    save_spaces_config(
        scout_home,
        {
            "zebra": SpaceEntry(name="zebra", root="/z", skip_globs=["*.log"]),
            "alpha": SpaceEntry(name="alpha", root="/a", skip_paths=["vendor/"]),
        },
    )

    resp = api_client.get("/v1/spaces/list")
    assert resp.status_code == 200
    data = resp.json()
    assert [s["name"] for s in data["spaces"]] == ["alpha", "zebra"]
    assert data["spaces"][0] == {
        "name": "alpha",
        "root": "/a",
        "skip_globs": [],
        "skip_paths": ["vendor/"],
    }
    assert data["spaces"][1]["skip_globs"] == ["*.log"]
