"""Memory file storage — global flat markdown memories.

Metadata: v0.2.0 | Scout Contributors | 2026-07-14
Change rationale: global-memories-graph-index — flat global store, migrate nested.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

MEMORY_DIR_PREFIX = "memories"

logger = logging.getLogger("scout.memory.storage")


def _memory_root(home: Path) -> Path:
    """Return the global memory directory path."""
    return home / "scout" / MEMORY_DIR_PREFIX


def ensure_memory_dir(home: Path) -> Path:
    """Create the global memory directory if needed. Returns the path."""
    mem_dir = _memory_root(home)
    mem_dir.mkdir(parents=True, exist_ok=True)
    return mem_dir


def memory_rel_path(memory_id: str) -> str:
    """Logical rel_path for a global memory file."""
    return f"scout/{MEMORY_DIR_PREFIX}/{memory_id}.md"


def create_memory_file(
    home: Path,
    title: str,
    body: str,
    category: str,
    tags: list[str],
    *,
    source_space: str | None = None,
) -> dict[str, Any]:
    """Create a new global memory file and return the response dict.

    Returns dict with: id, title, body, category, tags, created_at, space, rel_path
    (`space` is optional audit field from source_space, else empty string).
    """
    mem_dir = ensure_memory_dir(home)
    memory_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    rel_path = memory_rel_path(memory_id)
    file_path = mem_dir / f"{memory_id}.md"

    frontmatter: dict[str, Any] = {
        "id": memory_id,
        "title": title,
        "category": category,
        "tags": tags,
        "created_at": created_at,
    }
    if source_space:
        frontmatter["source_space"] = source_space

    content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}---\n{body}"
    file_path.write_text(content, encoding="utf-8")

    return {
        "id": memory_id,
        "title": title,
        "body": body,
        "category": category,
        "tags": tags,
        "created_at": created_at,
        "space": source_space or "",
        "rel_path": rel_path,
    }


def read_memory_file(home: Path, memory_id: str) -> dict[str, Any] | None:
    """Read a memory file by ID from the global store. Returns None if not found."""
    file_path = _memory_root(home) / f"{memory_id}.md"
    if not file_path.exists():
        return None

    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = _parse_memory_file(content)
    if not frontmatter.get("id"):
        return None
    source = frontmatter.get("source_space") or frontmatter.get("space") or ""
    return {
        "id": frontmatter["id"],
        "title": frontmatter.get("title", ""),
        "body": body,
        "category": frontmatter.get("category", ""),
        "tags": frontmatter.get("tags", []),
        "created_at": frontmatter.get("created_at", ""),
        "space": source,
        "rel_path": memory_rel_path(frontmatter["id"]),
    }


def list_memory_files(
    home: Path,
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """List global memory files with optional filters."""
    mem_dir = _memory_root(home)
    if not mem_dir.exists():
        return []

    results: list[dict[str, Any]] = []
    for md_file in sorted(mem_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_memory_file(content)
        if not frontmatter.get("id"):
            continue

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
                "title": frontmatter.get("title", ""),
                "category": frontmatter.get("category", ""),
                "tags": frontmatter.get("tags", []),
                "created_at": frontmatter.get("created_at", ""),
                "rel_path": memory_rel_path(frontmatter["id"]),
            }
        )

    return results


def migrate_memories_to_global(home: Path) -> dict[str, int]:
    """Idempotent migrate of nested `{space}/{id}.md` into flat global store.

    Returns counts: {"moved": n, "skipped": n, "conflicts": n}.
    """
    root = _memory_root(home)
    if not root.exists():
        return {"moved": 0, "skipped": 0, "conflicts": 0}

    moved = 0
    skipped = 0
    conflicts = 0

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        space_name = child.name
        for md_file in sorted(child.glob("*.md")):
            dest = root / md_file.name
            try:
                content = md_file.read_text(encoding="utf-8")
                frontmatter, body = _parse_memory_file(content)
                # Prefer source_space audit; keep legacy space as source_space
                if "source_space" not in frontmatter and space_name:
                    frontmatter["source_space"] = frontmatter.pop("space", space_name)
                elif "space" in frontmatter:
                    frontmatter.pop("space", None)

                new_content = (
                    f"---\n"
                    f"{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}"
                    f"---\n{body}"
                )

                if dest.exists():
                    # Prefer newer created_at; else keep both with conflict suffix
                    existing = dest.read_text(encoding="utf-8")
                    exist_fm, _ = _parse_memory_file(existing)
                    src_ts = str(frontmatter.get("created_at") or "")
                    dst_ts = str(exist_fm.get("created_at") or "")
                    if src_ts and dst_ts and src_ts <= dst_ts:
                        skipped += 1
                        md_file.unlink(missing_ok=True)
                        continue
                    if src_ts and dst_ts and src_ts > dst_ts:
                        dest.write_text(new_content, encoding="utf-8")
                        md_file.unlink(missing_ok=True)
                        moved += 1
                        continue
                    # Ambiguous conflict — keep both
                    conflict_path = root / f"{md_file.stem}.from-{space_name}{md_file.suffix}"
                    conflict_path.write_text(new_content, encoding="utf-8")
                    md_file.unlink(missing_ok=True)
                    conflicts += 1
                    logger.warning(
                        "memory migrate conflict for %s; kept as %s",
                        md_file.name,
                        conflict_path.name,
                    )
                    continue

                dest.write_text(new_content, encoding="utf-8")
                md_file.unlink(missing_ok=True)
                moved += 1
            except Exception:
                logger.exception("failed to migrate memory %s", md_file)
                skipped += 1

        # Remove empty space dirs
        try:
            if child.exists() and not any(child.iterdir()):
                child.rmdir()
        except OSError:
            logger.warning("could not remove empty memory space dir %s", child)

    return {"moved": moved, "skipped": skipped, "conflicts": conflicts}


def _parse_memory_file(content: str) -> tuple[dict[str, Any], str]:
    """Parse a memory file's YAML frontmatter and body."""
    lines = content.split("\n", 2)
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, content

    try:
        fm_end = content.index("---", 3)
    except ValueError:
        return {}, content
    frontmatter = yaml.safe_load(content[3:fm_end]) or {}
    body = content[fm_end + 3 :].strip()
    return frontmatter, body
