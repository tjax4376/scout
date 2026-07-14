"""Tests for memory REST API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scout.config import ScoutConfig, SpaceEntry, save_config


@pytest.fixture(autouse=True)
def _setup_test_space(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a test space for memory API tests."""
    save_config(
        scout_home,
        ScoutConfig(
            spaces={
                "test-space": SpaceEntry(
                    name="test-space",
                    root=str(scout_home / "test-space-root"),
                ),
            }
        ),
    )
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)


def test_create_memory_with_category(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/spaces/test-space/memory",
        json={
            "title": "Test Memory",
            "body": "This is test content.",
            "category": "api",
            "tags": ["test"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Memory"
    assert data["category"] == "api"
    assert data["tags"] == ["test"]
    assert "id" in data
    assert "created_at" in data
    assert "rel_path" in data


def test_create_memory_without_category_returns_409(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/spaces/test-space/memory",
        json={
            "title": "Uncategorized Memory",
            "body": "No category provided.",
        },
    )
    # Returns 409 with suggestions (if categories exist) or 400 (if none exist)
    assert resp.status_code in (400, 409)


def test_get_memory(api_client: TestClient) -> None:
    # Create first
    create_resp = api_client.post(
        "/v1/spaces/test-space/memory",
        json={
            "title": "Retrievable Memory",
            "body": "Body content.",
            "category": "api",
        },
    )
    assert create_resp.status_code == 201
    memory_id = create_resp.json()["id"]

    # Get it back
    resp = api_client.get(f"/v1/spaces/test-space/memory/{memory_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Retrievable Memory"


def test_get_nonexistent_memory(api_client: TestClient) -> None:
    resp = api_client.get("/v1/spaces/test-space/memory/nonexistent-id")
    assert resp.status_code == 404


def test_list_memories(api_client: TestClient) -> None:
    resp = api_client.get("/v1/spaces/test-space/memories")
    assert resp.status_code == 200
    data = resp.json()
    assert "memories" in data
    assert "total" in data
    assert isinstance(data["memories"], list)
    assert isinstance(data["total"], int)


def test_list_memories_filter_by_category(api_client: TestClient) -> None:
    # Create a memory
    api_client.post(
        "/v1/spaces/test-space/memory",
        json={"title": "API Memory", "body": "Content.", "category": "api"},
    )
    api_client.post(
        "/v1/spaces/test-space/memory",
        json={"title": "Config Memory", "body": "Content.", "category": "config"},
    )

    resp = api_client.get("/v1/spaces/test-space/memories", params={"category": "api"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["memories"][0]["category"] == "api"


def test_list_memories_filter_by_tag(api_client: TestClient) -> None:
    api_client.post(
        "/v1/spaces/test-space/memory",
        json={"title": "Tagged Memory", "body": "Content.", "category": "api", "tags": ["fastapi"]},
    )

    resp = api_client.get("/v1/spaces/test-space/memories", params={"tag": "fastapi"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


def test_list_memories_search(api_client: TestClient) -> None:
    api_client.post(
        "/v1/spaces/test-space/memory",
        json={"title": "Auth Memory", "body": "Authentication setup guide.", "category": "api"},
    )

    resp = api_client.get("/v1/spaces/test-space/memories", params={"q": "authentication"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_create_memory_invalid_title(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/spaces/test-space/memory",
        json={"title": "", "body": "Content.", "category": "api"},
    )
    assert resp.status_code == 422  # Pydantic validation error


def test_create_memory_unknown_space(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/spaces/nonexistent/memory",
        json={"title": "Memory", "body": "Content.", "category": "api"},
    )
    assert resp.status_code == 404


# ── Ask memory endpoint tests ─────────────────────────────────────


def test_ask_memory_returns_results(api_client: TestClient) -> None:
    # Create a memory first
    api_client.post(
        "/v1/spaces/test-space/memory",
        json={
            "title": "Auth Middleware",
            "body": "Use FastAPI middleware for authentication.",
            "category": "api-patterns",
        },
    )

    resp = api_client.post(
        "/v1/spaces/test-space/memory/ask",
        json={"query": "authentication middleware"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "memories" in data
    assert "total" in data
    assert "query" in data
    assert data["query"] == "authentication middleware"
    assert data["total"] >= 1


def test_ask_memory_empty_query(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/spaces/test-space/memory/ask",
        json={"query": ""},
    )
    assert resp.status_code == 422  # Pydantic validation (min_length=1)


def test_ask_memory_no_results(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/spaces/test-space/memory/ask",
        json={"query": "nonexistent topic xyz123abc"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["memories"] == []


def test_ask_memory_unknown_space(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/spaces/nonexistent/memory/ask",
        json={"query": "test query"},
    )
    assert resp.status_code == 404


def test_ask_memory_response_format(api_client: TestClient) -> None:
    api_client.post(
        "/v1/spaces/test-space/memory",
        json={
            "title": "Config Memory",
            "body": "Database configuration with PostgreSQL.",
            "category": "config",
            "tags": ["database"],
        },
    )

    resp = api_client.post(
        "/v1/spaces/test-space/memory/ask",
        json={"query": "database configuration"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["memories"]) >= 1
    mem = data["memories"][0]
    # Verify all required fields
    assert "id" in mem
    assert "title" in mem
    assert "body" in mem
    assert "category" in mem
    assert "tags" in mem
    assert "created_at" in mem
    assert "rel_path" in mem
