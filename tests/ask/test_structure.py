"""Unit tests for scout.ask.structure.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: ask-scout-structure — verify ranking, validation, truncation, missing graph.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from scout.ask.structure import AskGraphMissingError, ask_structure
from scout.config import ScoutConfig, SpaceEntry


def _cfg(root: str = "/tmp/ws") -> ScoutConfig:
    return ScoutConfig(spaces={"demo": SpaceEntry(name="demo", root=root)})


def test_ask_empty_query_raises(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(ValueError, match="empty"):
        ask_structure(home, "demo", _cfg(), "   ")


def test_ask_missing_graph_raises(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "cache" / "demo").mkdir(parents=True)
    with pytest.raises(AskGraphMissingError):
        ask_structure(home, "demo", _cfg(str(tmp_path)), "auth")


def test_ask_returns_compact_hits_no_source(tmp_path: Path) -> None:
    home = tmp_path / "home"
    space_dir = home / "cache" / "demo"
    space_dir.mkdir(parents=True)
    (space_dir / "graph.bin").write_bytes(b"fake")

    search_payload = {
        "hits": [
            {
                "node_id": "a",
                "kind": "function",
                "symbol": "authenticate",
                "rel_path": "src/auth.py",
                "location_ref": "src=/src/auth.py",
                "start_line": 10,
                "end_line": 20,
                "score": 0.9,
                "compressed_text": "SHOULD_NOT_APPEAR",
            },
            {
                "node_id": "b",
                "kind": "function",
                "symbol": "auth_helper",
                "rel_path": "a/helper.py",
                "location_ref": "src=/a/helper.py",
                "start_line": 1,
                "end_line": 2,
                "score": 0.5,
            },
        ],
        "stale": False,
        "index_version": "graph-only:v1",
    }

    with (
        patch("scout.ask.structure.scout_core") as core,
        patch("scout.ask.structure.graph_path_search", return_value=search_payload),
    ):
        core.py_expand_neighbors.return_value = '{"node_id":"a","neighbors":[]}'
        result = ask_structure(
            home,
            "demo",
            _cfg(str(tmp_path)),
            "auth",
            expand_depth=0,
            top_k=10,
            max_nodes=50,
        )

    assert result["mode"] == "graph"
    assert result["total"] == 2
    assert result["hits"][0]["node_id"] == "a"
    for hit in result["hits"]:
        assert "compressed_text" not in hit
        assert "text" not in hit
        assert hit.get("location_ref")


def test_ask_truncates_when_max_nodes_hit(tmp_path: Path) -> None:
    home = tmp_path / "home"
    space_dir = home / "cache" / "demo"
    space_dir.mkdir(parents=True)
    (space_dir / "graph.bin").write_bytes(b"fake")

    hits = [
        {
            "node_id": f"n{i}",
            "kind": "function",
            "symbol": f"fn{i}",
            "rel_path": f"f{i}.py",
            "location_ref": f"src=/f{i}.py",
            "start_line": 1,
            "end_line": 1,
            "score": 1.0 - (i * 0.01),
        }
        for i in range(5)
    ]
    search_payload: dict[str, Any] = {
        "hits": hits,
        "stale": False,
        "index_version": "v1",
    }
    expand_payload = {
        "node_id": "n0",
        "neighbors": [
            {
                "node_id": "extra",
                "kind": "function",
                "symbol": "x",
                "rel_path": "x.py",
                "location_ref": "src=/x.py",
                "edge": "calls",
                "depth": 1,
            }
        ],
    }

    with (
        patch("scout.ask.structure.scout_core") as core,
        patch("scout.ask.structure.graph_path_search", return_value=search_payload),
    ):
        core.py_expand_neighbors.return_value = json.dumps(expand_payload)
        result = ask_structure(
            home,
            "demo",
            _cfg(str(tmp_path)),
            "fn",
            expand_depth=1,
            top_k=10,
            max_nodes=2,
        )

    assert result["truncated"] is True
    assert result["total"] <= 2
    assert len(result["hits"]) <= 2
