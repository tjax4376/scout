"""scout_core + indexing pipeline tests (require maturin build)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scout.config import ScoutConfig, SpaceEntry, register_space, save_config
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
    build_json = scout_core.py_build_graph("test", str(sample_project), files_json, "graph-only:v1")
    snapshot = json.loads(build_json)
    assert len(snapshot["nodes"]) > 0
    file_nodes = [n for n in snapshot["nodes"] if n["kind"] == "file"]
    assert file_nodes
    assert file_nodes[0]["location_ref"].startswith("src=/") or file_nodes[0]["location_ref"]


@requires_scout_core
def test_staleness_after_file_change(sample_project: Path, tmp_path: Path) -> None:
    import scout_core

    home = tmp_path / ".scout"
    home.mkdir()
    config = ScoutConfig()
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
    scout_core.py_write_graph_manifest(str(manifest_path(home, "demo")), files_json)

    stale, _ = scout_core.py_check_staleness(
        str(sample_project),
        str(manifest_path(home, "demo")),
        "",
        "",
        0,
    )
    assert stale is False

    auth = sample_project / "src" / "auth.py"
    auth.write_text(auth.read_text() + "\n# changed\n", encoding="utf-8")
    stale, _ = scout_core.py_check_staleness(
        str(sample_project),
        str(manifest_path(home, "demo")),
        "",
        "",
        0,
    )
    assert stale is True


@requires_scout_core
@pytest.mark.asyncio
async def test_reindex_atomic_swap(sample_project: Path, tmp_path: Path) -> None:
    import scout_core

    home = tmp_path / ".scout"
    home.mkdir()
    config = ScoutConfig()
    entry = SpaceEntry(name="demo", root=str(sample_project))
    register_space(home, entry, config)
    save_config(home, config)

    from scout.indexing import run_reindex

    version = await run_reindex(home, "demo", config)
    assert version == "graph-only:v1"
    assert graph_bin_path(home, "demo").exists()
    assert not index_db_path(home, "demo").exists()
    assert manifest_path(home, "demo").exists()

    assert scout_core.py_acquire_reindex_lock("demo") is True
    assert scout_core.py_acquire_reindex_lock("other") is False
    scout_core.py_release_reindex_lock()
