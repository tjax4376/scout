"""Fixtures for REST API tests (FastAPI TestClient)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scout.api.app import create_app
from scout.config import ScoutConfig, SpaceEntry, save_config


@pytest.fixture
def api_client(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with `scout.api.app.scout_home` patched to isolated home."""
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    return TestClient(create_app())


def save_spaces_config(home: Path, spaces: dict[str, SpaceEntry]) -> None:
    """Write space entries into config.yaml for API tests."""
    save_config(home, ScoutConfig(spaces=spaces))
