"""Integration tests for Scout MVP1."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout.config import (
    EmbedConfig,
    ScoutConfig,
    SpaceEntry,
    bootstrap_scout_dir,
    graph_bin_path,
    index_db_path,
    load_config,
    manifest_path,
    register_space,
    save_config,
)
from scout.prescan.runner import PrescanResult, check_byte_cap, check_capacity
from scout.skill.install import install_skill


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
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


def test_config_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: tmp_path / ".scout")
    home = bootstrap_scout_dir()
    assert (home / "config.yaml").exists()
    assert (home / "secrets.yaml").exists()


def test_prescan_capacity_gate_rejects() -> None:
    result = PrescanResult(
        file_count=1,
        total_bytes=10_000_000_000,
        languages={"python": 1},
        estimated_disk_bytes=20_000_000_000,
        estimated_ram_bytes=20_000_000_000,
        available_disk_bytes=1_000_000,
        available_ram_bytes=1_000_000,
    )
    with pytest.raises(RuntimeError, match="not enough capacity"):
        check_capacity(result)


def test_byte_cap_force_bypass() -> None:
    result = PrescanResult(
        file_count=1,
        total_bytes=200 * 1024**3,
        languages={"python": 1},
        estimated_disk_bytes=1000,
        estimated_ram_bytes=1000,
        available_disk_bytes=10_000_000_000,
        available_ram_bytes=10_000_000_000,
    )
    with pytest.raises(RuntimeError):
        check_byte_cap(result, force=False)
    check_byte_cap(result, force=True)


def test_skill_install_project_cursor(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    with patch("scout.skill.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text(
            "api={{SCOUT_API}} space={{DEFAULT_SPACE}}", encoding="utf-8"
        )
        mock_tpl.return_value = tpl
        dests = install_skill(
            "cursor",
            global_install=False,
            project_install=True,
            project_root=project,
            scout_api="http://127.0.0.1:8741/v1",
            default_space="test",
            force=True,
        )
    assert len(dests) == 1
    content = dests[0].joinpath("SKILL.md").read_text(encoding="utf-8")
    assert "8741" in content
    assert "test" in content


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("scout_core") is None,
    reason="scout_core not built",
)
def test_scan_and_build(sample_project: Path, tmp_path: Path) -> None:
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


@pytest.mark.asyncio
@pytest.mark.skipif(
    __import__("importlib").util.find_spec("scout_core") is None,
    reason="scout_core not built",
)
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
    provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4]] * 10)

    from scout.indexing import run_reindex

    # Patch embed to return correct count for any chunk list
    async def dynamic_embed(model: str, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    provider.embed = dynamic_embed

    version = await run_reindex(home, "demo", config, provider)
    assert version
    assert index_db_path(home, "demo").exists()
    assert graph_bin_path(home, "demo").exists()
    assert manifest_path(home, "demo").exists()

    # Concurrent reindex guard
    assert scout_core.py_acquire_reindex_lock("demo") is True
    assert scout_core.py_acquire_reindex_lock("other") is False
    scout_core.py_release_reindex_lock()
