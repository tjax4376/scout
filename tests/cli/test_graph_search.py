"""Graph path search CLI tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scout.config import ScoutConfig, SpaceEntry, save_config
from scout.graph_find import graph_path_search
from tests.conftest import requires_scout_core


@requires_scout_core
@pytest.mark.asyncio
async def test_graph_path_search_finds_readme(
    tmp_path: Path,
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "README.md").write_text("# Scout\n", encoding="utf-8")
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    space = "demo"
    config = ScoutConfig(
        spaces={space: SpaceEntry(name=space, root=str(project))},
    )
    save_config(scout_home, config)
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: scout_home)

    from scout.indexing import run_reindex

    await run_reindex(scout_home, space, config)

    result = graph_path_search(scout_home, space, config, "README.md")
    paths = [h["rel_path"] for h in result["hits"]]
    assert "README.md" in paths
    assert result["graph_only"] is True


@requires_scout_core
def test_cli_search_graph_fallback(
    tmp_path: Path,
    scout_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "README.md").write_text("# Scout\n", encoding="utf-8")

    space = "scout"
    config = ScoutConfig(
        spaces={space: SpaceEntry(name=space, root=str(project))},
    )
    save_config(scout_home, config)
    monkeypatch.chdir(project)
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: scout_home)

    from scout.indexing import run_reindex

    asyncio.run(run_reindex(scout_home, space, config))

    import scout.cli.main as cli_main

    captured: dict[str, str] = {}

    class FakeJSON:
        def __init__(self, raw: str) -> None:
            captured["raw"] = raw

    monkeypatch.setattr(cli_main, "JSON", FakeJSON)
    cli_main.main([space, "search", "README.md"])

    payload = json.loads(captured["raw"])
    assert any(h["rel_path"] == "README.md" for h in payload["hits"])
    assert payload["graph_only"] is True
