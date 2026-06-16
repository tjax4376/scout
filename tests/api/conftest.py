"""Fixtures for REST API tests (FastAPI TestClient)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scout.api.app import create_app
from scout.api.rate_limit import reset_rate_limiter
from scout.config import (
    ScoutConfig,
    SpaceEntry,
    graph_bin_path,
    index_db_path,
    save_config,
)


@pytest.fixture(autouse=True)
def _reset_api_rate_limiter() -> None:
    """Isolate rate-limit tests from prior search requests in the suite."""
    reset_rate_limiter()
    yield
    reset_rate_limiter()


@pytest.fixture
def api_client(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with `scout.api.app.scout_home` patched to isolated home."""
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    return TestClient(create_app())


def save_spaces_config(home: Path, spaces: dict[str, SpaceEntry]) -> None:
    """Write space entries into config.yaml for API tests."""
    save_config(home, ScoutConfig(spaces=spaces))


@pytest.fixture
def graph_indexed_space(
    sample_project: Path,
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, Path]:
    """Build graph-only indexed space; returns (space_name, scout_home)."""
    pytest.importorskip("scout_core")
    import asyncio

    from scout.indexing import run_reindex

    space = "demo"
    config = ScoutConfig(
        spaces={space: SpaceEntry(name=space, root=str(sample_project))},
    )
    save_config(scout_home, config)
    asyncio.run(run_reindex(scout_home, space, config))

    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    assert graph_bin_path(scout_home, space).exists()
    assert not index_db_path(scout_home, space).exists()
    return space, scout_home


@pytest.fixture
def indexed_space(graph_indexed_space: tuple[str, Path]) -> tuple[str, Path]:
    """Alias for graph-only indexed space."""
    return graph_indexed_space


@pytest.fixture
def indexed_api_client(indexed_space: tuple[str, Path]) -> TestClient:
    return TestClient(create_app())
