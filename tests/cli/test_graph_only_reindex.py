"""Graph-only reindex CLI path."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.config import ScoutConfig, SpaceEntry, register_space, save_config
from scout.config import graph_bin_path, index_db_path, manifest_path
from tests.conftest import requires_scout_core


@requires_scout_core
@pytest.mark.asyncio
async def test_graph_only_reindex(sample_project: Path, tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    config = ScoutConfig()
    register_space(home, SpaceEntry(name="demo", root=str(sample_project)), config)
    save_config(home, config)

    from scout.indexing import run_reindex

    version = await run_reindex(home, "demo", config)
    assert version == "graph-only:v1"
    assert graph_bin_path(home, "demo").exists()
    assert manifest_path(home, "demo").exists()
    assert not index_db_path(home, "demo").exists()

    manifest = (home / "spaces" / "demo" / "manifest.json").read_text(encoding="utf-8")
    assert "graph-only:v1" in manifest
