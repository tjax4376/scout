"""Memory module — structured markdown memories for Scout's cavern.

Metadata: v0.1.0 | Scout Contributors | 2026-07-13
Change rationale: add-memory-api — agent-contributed knowledge storage.
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
    "read_memory_file",
    "recommend_categories",
]


def demo() -> None:
    """Self-check: create → read → list memory flow."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        space = "demo-space"

        # Create
        result = create_memory_file(home, space, "Demo", "Demo body.", "test", [])
        assert result["title"] == "Demo"
        assert result["category"] == "test"

        # Read
        mem = read_memory_file(home, space, result["id"])
        assert mem is not None
        assert mem["title"] == "Demo"
        assert mem["body"] == "Demo body."

        # List
        memories = list_memory_files(home, space)
        assert len(memories) == 1

        print("✓ memory demo passed")


if __name__ == "__main__":
    demo()
