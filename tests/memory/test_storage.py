"""Tests for memory file storage (global flat store)."""

from __future__ import annotations

from pathlib import Path

from scout.memory.storage import (
    create_memory_file,
    ensure_memory_dir,
    list_memory_files,
    migrate_memories_to_global,
    read_memory_file,
)


def test_ensure_memory_dir_creates_path(tmp_path: Path) -> None:
    mem_dir = ensure_memory_dir(tmp_path)
    assert mem_dir.exists()
    assert mem_dir == tmp_path / "scout" / "memories"


def test_create_memory_file(tmp_path: Path) -> None:
    result = create_memory_file(
        tmp_path,
        "Test Memory",
        "This is the body content.",
        "api",
        ["fastapi", "rest"],
        source_space="test-space",
    )
    assert result["id"] is not None
    assert result["title"] == "Test Memory"
    assert result["category"] == "api"
    assert result["tags"] == ["fastapi", "rest"]
    assert result["space"] == "test-space"
    assert result["rel_path"] == f"scout/memories/{result['id']}.md"

    file_path = tmp_path / "scout" / "memories" / f"{result['id']}.md"
    assert file_path.exists()
    content = file_path.read_text()
    assert "---" in content
    assert "id:" in content
    assert "title: Test Memory" in content
    assert "source_space: test-space" in content


def test_read_memory_file(tmp_path: Path) -> None:
    result = create_memory_file(
        tmp_path,
        "Test Memory 2",
        "Body content here.",
        "config",
        [],
    )
    mem = read_memory_file(tmp_path, result["id"])
    assert mem is not None
    assert mem["title"] == "Test Memory 2"
    assert mem["body"] == "Body content here."
    assert mem["category"] == "config"


def test_read_nonexistent_memory(tmp_path: Path) -> None:
    result = read_memory_file(tmp_path, "nonexistent-id")
    assert result is None


def test_list_memory_files_empty(tmp_path: Path) -> None:
    result = list_memory_files(tmp_path)
    assert result == []


def test_list_memory_files_with_filters(tmp_path: Path) -> None:
    create_memory_file(
        tmp_path,
        "API Memory",
        "About the API module.",
        "api",
        ["fastapi"],
    )
    create_memory_file(
        tmp_path,
        "Config Memory",
        "About configuration.",
        "config",
        [],
    )

    all_memories = list_memory_files(tmp_path)
    assert len(all_memories) == 2

    api_only = list_memory_files(tmp_path, category="api")
    assert len(api_only) == 1
    assert api_only[0]["title"] == "API Memory"

    tagged = list_memory_files(tmp_path, tag="fastapi")
    assert len(tagged) == 1

    search_result = list_memory_files(tmp_path, q="configuration")
    assert len(search_result) == 1
    assert search_result[0]["title"] == "Config Memory"


def test_memory_file_frontmatter_format(tmp_path: Path) -> None:
    result = create_memory_file(
        tmp_path,
        "Frontmatter Test",
        "Body text.",
        "api",
        ["test"],
    )
    file_path = tmp_path / "scout" / "memories" / f"{result['id']}.md"
    content = file_path.read_text()
    assert content.startswith("---\n")
    close_idx = content.index("---", 3)
    body = content[close_idx + 3 :].strip()
    assert body == "Body text."


def test_migrate_nested_to_global(tmp_path: Path) -> None:
    nested = tmp_path / "scout" / "memories" / "old-space"
    nested.mkdir(parents=True)
    mem_id = "11111111-1111-1111-1111-111111111111"
    (nested / f"{mem_id}.md").write_text(
        f"---\nid: {mem_id}\ntitle: Old\ncategory: api\ntags: []\n"
        f"created_at: '2026-01-01T00:00:00+00:00'\nspace: old-space\n---\nBody.\n",
        encoding="utf-8",
    )
    stats = migrate_memories_to_global(tmp_path)
    assert stats["moved"] == 1
    dest = tmp_path / "scout" / "memories" / f"{mem_id}.md"
    assert dest.exists()
    assert not nested.exists()
    mem = read_memory_file(tmp_path, mem_id)
    assert mem is not None
    assert mem["title"] == "Old"
    assert mem["space"] == "old-space"

    # Idempotent
    stats2 = migrate_memories_to_global(tmp_path)
    assert stats2["moved"] == 0
