"""Unit tests for session index store."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.config import EmbedConfig, ScoutConfig, SpaceEntry, save_config, session_index_path
from scout.session.store import SessionIndexStore
from tests.conftest import requires_scout_core


@requires_scout_core
def test_session_index_cleared_on_prepare(
    scout_home: Path,
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: scout_home)
    space = "demo"
    config = ScoutConfig(
        spaces={space: SpaceEntry(name=space, root=str(sample_project))},
        embed=EmbedConfig(provider="lmstudio", model="test-model", dimensions=4),
    )
    save_config(scout_home, config)
    store = SessionIndexStore(scout_home, space, config)
    store.prepare_fresh()
    chunks = [
        {
            "node_id": "n1",
            "text": "hello",
            "kind": "function",
            "rel_path": "src/auth.py",
            "symbol": "authenticate",
            "start_line": 1,
            "end_line": 2,
        }
    ]
    store.append(chunks, [[0.1, 0.2, 0.3, 0.4]])
    assert store.stats() == (1, 1)

    store.prepare_fresh()
    assert store.stats() == (0, 0)
    assert session_index_path(scout_home, space).exists()
