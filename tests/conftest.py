"""Shared pytest fixtures for Scout."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCOUT_CORE_AVAILABLE = importlib.util.find_spec("scout_core") is not None

requires_scout_core = pytest.mark.skipif(
    not SCOUT_CORE_AVAILABLE,
    reason="scout_core not built (run maturin develop)",
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Minimal Python project with auth + main modules."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text(
        "def authenticate(user):\n    return user\n\ndef logout():\n    pass\n",
        encoding="utf-8",
    )
    (src / "main.py").write_text(
        "from auth import authenticate\n\ndef main():\n    authenticate('x')\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def scout_home(tmp_path: Path) -> Path:
    """Isolated `.scout` directory with bootstrapped config."""
    from scout.config import bootstrap_scout_dir

    return bootstrap_scout_dir(tmp_path / ".scout")


@pytest.fixture
def patch_scout_config_home(scout_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Route `scout.config.scout_home()` to the isolated test home."""
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: scout_home)
    return scout_home
