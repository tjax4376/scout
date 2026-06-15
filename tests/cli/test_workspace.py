"""Tests for workspace resolution and source folder picker."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.setup.workspace import (
    discover_source_folders,
    prompt_index_subdirectory,
    resolve_path_input,
)


def test_resolve_path_input_dot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_path_input(".") == tmp_path.resolve()
    assert resolve_path_input("./") == tmp_path.resolve()


def test_resolve_path_input_relative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = tmp_path / "pkg"
    sub.mkdir()
    monkeypatch.chdir(tmp_path)
    assert resolve_path_input("pkg") == sub.resolve()


def test_resolve_path_input_absolute(tmp_path: Path) -> None:
    assert resolve_path_input(str(tmp_path)) == tmp_path.resolve()


def test_resolve_path_input_missing_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        resolve_path_input("missing-dir")


def test_discover_source_folders_filters_junk(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "lib").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "readme.md").write_text("x", encoding="utf-8")

    names = [p.name for p in discover_source_folders(tmp_path)]
    assert names == ["lib", "src"]


def test_prompt_index_subdirectory_whole_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src").mkdir()
    monkeypatch.setattr("scout.setup.workspace.typer.prompt", lambda *a, **k: "0")
    assert prompt_index_subdirectory(tmp_path) == tmp_path.resolve()


def test_prompt_index_subdirectory_pick_src(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr("scout.setup.workspace.typer.prompt", lambda *a, **k: "1")
    assert prompt_index_subdirectory(tmp_path) == src.resolve()


def test_prompt_index_subdirectory_empty_children(tmp_path: Path) -> None:
    (tmp_path / "readme.md").write_text("x", encoding="utf-8")
    assert prompt_index_subdirectory(tmp_path) == tmp_path.resolve()
