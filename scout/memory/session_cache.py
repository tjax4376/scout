"""In-memory memory cache for embed serve mode (global store).

Metadata: v0.2.0 | Scout Contributors | 2026-07-14
Change rationale: global-memories-graph-index — single global MemoryCache.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from scout.memory.storage import _memory_root, _parse_memory_file, memory_rel_path

logger = logging.getLogger("scout.memory.session_cache")


class MemoryCache:
    """Global in-memory memory cache for embed mode."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._memories: dict[str, dict[str, Any]] = {}
        self._warm()

    def _warm(self) -> None:
        """Load existing memory files into the cache."""
        mem_dir = _memory_root(self._home)
        if not mem_dir.exists():
            return
        for md_file in sorted(mem_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                frontmatter, body = _parse_memory_file(content)
                if not frontmatter.get("id"):
                    continue
                mid = frontmatter["id"]
                source = frontmatter.get("source_space") or frontmatter.get("space") or ""
                self._memories[mid] = {
                    "id": mid,
                    "title": frontmatter.get("title", ""),
                    "body": body,
                    "category": frontmatter.get("category", ""),
                    "tags": frontmatter.get("tags", []),
                    "created_at": frontmatter.get("created_at", ""),
                    "space": source,
                    "rel_path": memory_rel_path(mid),
                }
            except Exception:
                logger.warning("failed to warm memory %s", md_file.name, exc_info=True)

    def get(self, memory_id: str) -> dict[str, Any] | None:
        """Get a memory by ID."""
        return self._memories.get(memory_id)

    def add(self, memory: dict[str, Any]) -> None:
        """Add a memory to the cache."""
        self._memories[memory["id"]] = memory

    def list(
        self,
        category: str | None = None,
        tag: str | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        """List memories with optional filters."""
        results: list[dict[str, Any]] = []
        for mem in self._memories.values():
            if category and mem.get("category") != category:
                continue
            if tag and tag not in mem.get("tags", []):
                continue
            if q:
                search_lower = q.lower()
                title_lower = mem.get("title", "").lower()
                body_lower = mem.get("body", "").lower()
                if search_lower not in title_lower and search_lower not in body_lower:
                    continue
            results.append(
                {
                    "id": mem["id"],
                    "title": mem["title"],
                    "category": mem["category"],
                    "tags": mem.get("tags", []),
                    "created_at": mem["created_at"],
                    "rel_path": mem["rel_path"],
                }
            )
        return results

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        return {"memory_count": len(self._memories)}
