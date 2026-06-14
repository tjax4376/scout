"""scout_core + indexing pipeline tests (require maturin build)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scout.config import EmbedConfig, ScoutConfig, SpaceEntry, register_space, save_config
from scout.config import graph_bin_path, index_db_path, manifest_path
from tests.conftest import requires_scout_core


@requires_scout_core
def test_scan_and_build(sample_project: Path) -> None:
    import scout_core

    files = scout_core.py_scan_workspace(str(sample_project))
    assert len(files) >= 2
    files_json = json.dumps(
        [
            {
                "rel_path": f.rel_path,
                "size": f.size,
                "mtime_secs": f.mtime_secs,
                "language": f.language,
                "is_binary": False,
            }
            for f in files
        ]
    )
    build_json = scout_core.py_build_index("test", str(sample_project), files_json, "v1")
    data = json.loads(build_json)
    assert len(data) == 2
    snapshot, chunks = data
    assert len(snapshot["nodes"]) > 0
    assert len(chunks) > 0


@requires_scout_core
def test_staleness_after_file_change(sample_project: Path, tmp_path: Path) -> None:
    import scout_core

    home = tmp_path / ".scout"
    home.mkdir()
    config = ScoutConfig(embed=EmbedConfig(provider="p", model="m", dimensions=4))
    entry = SpaceEntry(name="demo", root=str(sample_project))
    register_space(home, entry, config)
    save_config(home, config)

    files = scout_core.py_scan_workspace(str(sample_project))
    files_json = json.dumps(
        [
            {
                "rel_path": f.rel_path,
                "size": f.size,
                "mtime_secs": f.mtime_secs,
                "language": f.language,
                "is_binary": False,
            }
            for f in files
        ]
    )
    scout_core.py_write_manifest(str(manifest_path(home, "demo")), files_json, "p", "m", 4)

    stale, _ = scout_core.py_check_staleness(
        str(sample_project),
        str(manifest_path(home, "demo")),
        "p",
        "m",
        4,
    )
    assert stale is False

    auth = sample_project / "src" / "auth.py"
    auth.write_text(auth.read_text() + "\n# changed\n", encoding="utf-8")
    stale, _ = scout_core.py_check_staleness(
        str(sample_project),
        str(manifest_path(home, "demo")),
        "p",
        "m",
        4,
    )
    assert stale is True


@requires_scout_core
@pytest.mark.asyncio
async def test_reindex_atomic_swap(sample_project: Path, tmp_path: Path) -> None:
    import scout_core

    home = tmp_path / ".scout"
    home.mkdir()
    config = ScoutConfig(
        embed=EmbedConfig(provider="mock", model="mock-embed", dimensions=4),
    )
    entry = SpaceEntry(name="demo", root=str(sample_project))
    register_space(home, entry, config)
    save_config(home, config)

    provider = MagicMock()

    async def dynamic_embed(model: str, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    provider.embed = dynamic_embed

    from scout.indexing import run_reindex

    version = await run_reindex(home, "demo", config, provider)
    assert version
    assert index_db_path(home, "demo").exists()
    assert graph_bin_path(home, "demo").exists()
    assert manifest_path(home, "demo").exists()

    assert scout_core.py_acquire_reindex_lock("demo") is True
    assert scout_core.py_acquire_reindex_lock("other") is False
    scout_core.py_release_reindex_lock()


@requires_scout_core
@pytest.mark.asyncio
async def test_cli_search_path_without_serve(sample_project: Path, tmp_path: Path) -> None:
    """CLI search uses pyo3 directly — no HTTP."""
    import scout_core

    home = tmp_path / ".scout"
    home.mkdir()
    config = ScoutConfig(embed=EmbedConfig(provider="mock", model="m", dimensions=4))
    entry = SpaceEntry(name="demo", root=str(sample_project))
    register_space(home, entry, config)
    save_config(home, config)

    class Provider:
        async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    from scout.indexing import run_reindex

    await run_reindex(home, "demo", config, Provider())

    query_vec = (await Provider().embed("m", ["authenticate"]))[0]
    raw = scout_core.py_search(
        str(graph_bin_path(home, "demo")),
        str(index_db_path(home, "demo")),
        query_vec,
        5,
        0.0,
        None,
        None,
        False,
        "v1",
    )
    data = json.loads(raw)
    assert "hits" in data
