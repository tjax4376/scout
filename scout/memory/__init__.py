"""Memory module — structured markdown memories for Scout's cavern.

Metadata: v0.2.0 | Scout Contributors | 2026-07-14
Change rationale: global-memories-graph-index — global flat store.
"""

from __future__ import annotations

from scout.memory.categorize import get_existing_categories, recommend_categories
from scout.memory.models import (
    CategoryRecommendation,
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryResponse,
)
from scout.memory.storage import (
    create_memory_file,
    ensure_memory_dir,
    list_memory_files,
    migrate_memories_to_global,
    read_memory_file,
)

__all__ = [
    "CategoryRecommendation",
    "MemoryCreateRequest",
    "MemoryListResponse",
    "MemoryResponse",
    "create_memory_file",
    "ensure_memory_dir",
    "get_existing_categories",
    "list_memory_files",
    "migrate_memories_to_global",
    "read_memory_file",
    "recommend_categories",
]


def demo() -> None:
    """Self-check: create → read → list memory flow."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)

        result = create_memory_file(home, "Demo", "Demo body.", "test", [])
        assert result["title"] == "Demo"
        assert result["category"] == "test"

        mem = read_memory_file(home, result["id"])
        assert mem is not None
        assert mem["title"] == "Demo"
        assert mem["body"] == "Demo body."

        memories = list_memory_files(home)
        assert len(memories) == 1

        print("✓ memory demo passed")


if __name__ == "__main__":
    demo()
