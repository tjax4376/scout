"""File cache unit tests."""

from __future__ import annotations

from pathlib import Path


from scout.config import SpaceEntry
from scout.session.file_cache import FileCache
from tests.conftest import requires_scout_core


@requires_scout_core
def test_file_cache_warm_and_hit(sample_project: Path) -> None:
    entry = SpaceEntry(name="demo", root=str(sample_project))
    cache = FileCache()
    cache.warm(entry)
    stats = cache.stats()
    assert stats.file_count > 0
    assert stats.bytes > 0
    assert stats.warm_seconds >= 0

    text = cache.get(sample_project, "src/auth.py")
    assert text is not None
    assert "authenticate" in text


@requires_scout_core
def test_file_cache_stale_after_edit(tmp_path: Path) -> None:
    target = tmp_path / "mutable.py"
    target.write_text("version one\n", encoding="utf-8")
    cache = FileCache()
    cache.put("mutable.py", "version one\n", mtime_secs=1)
    assert cache.get(tmp_path, "mutable.py") is None


@requires_scout_core
def test_file_cache_read_response_line_range(sample_project: Path) -> None:
    entry = SpaceEntry(name="demo", root=str(sample_project))
    cache = FileCache()
    cache.warm(entry)
    payload = cache.read_response(sample_project, "src/auth.py", 1, 1)
    assert payload is not None
    assert "authenticate" in str(payload["text"])
    assert payload["start_line"] == 1
