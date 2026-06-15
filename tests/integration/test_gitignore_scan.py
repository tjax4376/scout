"""Gitignore-aware scan tests."""

from __future__ import annotations


import scout_core
from tests.conftest import requires_scout_core


@requires_scout_core
def test_gitignore_excludes_ignored_dir(tmp_path) -> None:
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "skip.py").write_text("x", encoding="utf-8")
    (tmp_path / "keep.py").write_text("y", encoding="utf-8")

    files = scout_core.py_scan_workspace(str(tmp_path), respect_gitignore=True)
    paths = {f.rel_path for f in files}
    assert "keep.py" in paths
    assert "ignored/skip.py" not in paths


@requires_scout_core
def test_gitignore_opt_out(tmp_path) -> None:
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "skip.py").write_text("x", encoding="utf-8")
    (tmp_path / "keep.py").write_text("y", encoding="utf-8")

    files = scout_core.py_scan_workspace(str(tmp_path), respect_gitignore=False)
    paths = {f.rel_path for f in files}
    assert "ignored/skip.py" in paths


@requires_scout_core
def test_prescan_file_cache_ram_budget(tmp_path) -> None:
    from scout.prescan.runner import run_prescan

    (tmp_path / "a.py").write_text("hello\n", encoding="utf-8")
    base = run_prescan(tmp_path)
    with_cache = run_prescan(tmp_path, include_file_cache=True)
    assert with_cache.estimated_ram_bytes > base.estimated_ram_bytes
