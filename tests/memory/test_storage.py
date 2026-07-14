"""Tests for memory file storage."""

from __future__ import annotations

from pathlib import Path

from scout.memory.storage import (
    create_memory_file,
    ensure_memory_dir,
    list_memory_files,
    read_memory_file,
)


def test_ensure_memory_dir_creates_path(tmp_path: Path) -> None:
    mem_dir = ensure_memory_dir(tmp_path, "test-space")
    assert mem_dir.exists()
    assert mem_dir == tmp_path / "scout" / "memories" / "test-space"


def test_create_memory_file(tmp_path: Path) -> None:
    result = create_memory_file(
        tmp_path,
        "test-space",
        "Test Memory",
        "This is the body content.",
        "api",
        ["fastapi", "rest"],
    )
    assert result["id"] is not None
    assert result["title"] == "Test Memory"
    assert result["category"] == "api"
    assert result["tags"] == ["fastapi", "rest"]
    assert result["space"] == "test-space"
    assert ".md" in result["rel_path"]

    # Verify file exists on disk (use full path, not relative rel_path)
    file_path = tmp_path / "scout" / "memories" / "test-space" / f"{result['id']}.md"
    assert file_path.exists()
    content = file_path.read_text()
    assert "---" in content
    assert "id:" in content
    assert "title: Test Memory" in content


def test_read_memory_file(tmp_path: Path) -> None:
    result = create_memory_file(
        tmp_path,
        "test-space",
        "Test Memory 2",
        "Body content here.",
        "config",
        [],
    )
    mem = read_memory_file(tmp_path, "test-space", result["id"])
    assert mem is not None
    assert mem["title"] == "Test Memory 2"
    assert mem["body"] == "Body content here."
    assert mem["category"] == "config"


def test_read_nonexistent_memory(tmp_path: Path) -> None:
    result = read_memory_file(tmp_path, "test-space", "nonexistent-id")
    assert result is None


def test_list_memory_files_empty(tmp_path: Path) -> None:
    result = list_memory_files(tmp_path, "test-space")
    assert result == []


def test_list_memory_files_with_filters(tmp_path: Path) -> None:
    create_memory_file(
        tmp_path,
        "test-space",
        "API Memory",
        "About the API module.",
        "api",
        ["fastapi"],
    )
    create_memory_file(
        tmp_path,
        "test-space",
        "Config Memory",
        "About configuration.",
        "config",
        [],
    )

    # All memories
    all_memories = list_memory_files(tmp_path, "test-space")
    assert len(all_memories) == 2

    # Filter by category
    api_only = list_memory_files(tmp_path, "test-space", category="api")
    assert len(api_only) == 1
    assert api_only[0]["title"] == "API Memory"

    # Filter by tag
    tagged = list_memory_files(tmp_path, "test-space", tag="fastapi")
    assert len(tagged) == 1

    # Full-text search
    search_result = list_memory_files(tmp_path, "test-space", q="configuration")
    assert len(search_result) == 1
    assert search_result[0]["title"] == "Config Memory"


def test_memory_file_frontmatter_format(tmp_path: Path) -> None:
    result = create_memory_file(
        tmp_path,
        "test-space",
        "Frontmatter Test",
        "Body text.",
        "api",
        ["test"],
    )
    file_path = tmp_path / "scout" / "memories" / "test-space" / f"{result['id']}.md"
    content = file_path.read_text()
    # Verify YAML frontmatter delimiters
    assert content.startswith("---\n")
    lines = content.split("\n")
    assert lines[0] == "---"
    # Find closing ---
    close_idx = content.index("---", 3)
    assert close_idx > 3
    # Body starts after closing ---
    body = content[close_idx + 3:].strip()
    assert body == "Body text."
