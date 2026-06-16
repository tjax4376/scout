"""Path scope builder tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.hawkeye.runner.path_scope import directory_scope, file_scope


def test_file_scope_single_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "auth.py"
    target.parent.mkdir(parents=True)
    target.write_text("line1\nline2\nline3\n")

    scope = file_scope(repo, Path("src/auth.py"))
    assert scope.changed_paths == ["src/auth.py"]
    assert scope.changed_lines["src/auth.py"] == {1, 2, 3}
    assert scope.scope_ref == "file:src/auth.py"


def test_file_scope_missing() -> None:
    with pytest.raises(ValueError, match="file not found"):
        file_scope(Path("/tmp"), Path("nope.py"))


def test_directory_scope_recursion(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    auth = repo / "src" / "auth"
    api = repo / "src" / "api"
    junk = repo / "node_modules" / "pkg"
    auth.mkdir(parents=True)
    api.mkdir(parents=True)
    junk.mkdir(parents=True)
    (auth / "login.py").write_text("a\n")
    (api / "app.py").write_text("b\n")
    (junk / "ignored.js").write_text("c\n")

    scope = directory_scope(repo, Path("src"))
    paths = set(scope.changed_paths)
    assert "src/auth/login.py" in paths
    assert "src/api/app.py" in paths
    assert "node_modules/pkg/ignored.js" not in paths


def test_directory_scope_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    empty = repo / "empty"
    empty.mkdir(parents=True)
    with pytest.raises(ValueError, match="no reviewable files"):
        directory_scope(repo, Path("empty"))
