"""Memory file storage — create, read, list structured markdown memories.

Metadata: v0.1.0 | Scout Contributors | 2026-07-13
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scout.config import scout_home

MEMORY_DIR_PREFIX = "memories"


def _memory_dir(home: Path, space: str) -> Path:
    """Return the memory directory path for a given space."""
    return home / "scout" / MEMORY_DIR_PREFIX / space


def ensure_memory_dir(home: Path, space: str) -> Path:
    """Create the memory directory if it doesn't exist. Returns the path."""
    mem_dir = _memory_dir(home, space)
    mem_dir.mkdir(parents=True, exist_ok=True)
    return mem_dir


def create_memory_file(
    home: Path,
    space: str,
    title: str,
    body: str,
    category: str,
    tags: list[str],
) -> dict[str, Any]:
    """Create a new memory file and return the response dict.

    Returns dict with: id, title, body, category, tags, created_at, space, rel_path
    """
    mem_dir = ensure_memory_dir(home, space)
    memory_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    rel_path = f"scout/{MEMORY_DIR_PREFIX}/{space}/{memory_id}.md"
    file_path = mem_dir / f"{memory_id}.md"

    frontmatter = {
        "id": memory_id,
        "title": title,
        "category": category,
        "tags": tags,
        "created_at": created_at,
        "space": space,
    }

    content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}---\n{body}"
    file_path.write_text(content, encoding="utf-8")

    return {
        "id": memory_id,
        "title": title,
        "body": body,
        "category": category,
        "tags": tags,
        "created_at": created_at,
        "space": space,
        "rel_path": rel_path,
    }


def read_memory_file(home: Path, space: str, memory_id: str) -> dict[str, Any] | None:
    """Read a memory file by ID. Returns None if not found."""
    file_path = _memory_dir(home, space) / f"{memory_id}.md"
    if not file_path.exists():
        return None

    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = _parse_memory_file(content)
    return {
        "id": frontmatter["id"],
        "title": frontmatter["title"],
        "body": body,
        "category": frontmatter["category"],
        "tags": frontmatter.get("tags", []),
        "created_at": frontmatter["created_at"],
        "space": frontmatter["space"],
        "rel_path": f"scout/{MEMORY_DIR_PREFIX}/{space}/{memory_id}.md",
    }


def list_memory_files(
    home: Path,
    space: str,
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """List memory files with optional filters.

    Filters: category (exact match), tag (contains), q (full-text search on title+body).
    """
    mem_dir = _memory_dir(home, space)
    if not mem_dir.exists():
        return []

    results: list[dict[str, Any]] = []
    for md_file in sorted(mem_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_memory_file(content)

        # Apply filters
        if category and frontmatter.get("category") != category:
            continue
        if tag and tag not in frontmatter.get("tags", []):
            continue
        if q:
            search_lower = q.lower()
            title_lower = frontmatter.get("title", "").lower()
            body_lower = body.lower()
            if search_lower not in title_lower and search_lower not in body_lower:
                continue

        results.append(
            {
                "id": frontmatter["id"],
                "title": frontmatter["title"],
                "category": frontmatter["category"],
                "tags": frontmatter.get("tags", []),
                "created_at": frontmatter["created_at"],
                "rel_path": f"scout/{MEMORY_DIR_PREFIX}/{space}/{frontmatter['id']}.md",
            }
        )

    return results


def _parse_memory_file(content: str) -> tuple[dict[str, Any], str]:
    """Parse a memory file's YAML frontmatter and body."""
    lines = content.split("\n", 2)
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, content

    fm_end = content.index("---", 3)
    frontmatter = yaml.safe_load(content[3:fm_end]) or {}
    body = content[fm_end + 3:].strip()
    return frontmatter, body
