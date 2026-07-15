"""Category recommendation for memories.

Metadata: v0.2.0 | Scout Contributors | 2026-07-14
Change rationale: global-memories-graph-index — categories from global store.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from scout.memory.storage import _memory_root


def get_existing_categories(home: Path) -> list[str]:
    """Return category names from the global memory store."""
    mem_dir = _memory_root(home)
    if not mem_dir.exists():
        return []

    categories: set[str] = set()
    for md_file in mem_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        try:
            lines = content.split("\n", 2)
            if len(lines) < 3 or lines[0].strip() != "---":
                continue
            fm_end = content.index("---", 3)
            frontmatter = yaml.safe_load(content[3:fm_end]) or {}
            cat = frontmatter.get("category")
            if cat:
                categories.add(cat)
        except (ValueError, yaml.YAMLError):
            continue

    return sorted(categories)


def compute_overlap_score(text: str, category: str) -> float:
    """Compute keyword overlap score between text and a category name."""
    text_lower = text.lower()
    category_words = set(re.split(r"[-_\s]+", category.lower()))
    if not category_words or "" in category_words:
        return 0.0

    matches = sum(1 for word in category_words if word in text_lower)
    return matches / len(category_words)


def recommend_categories(
    home: Path,
    title: str,
    body: str,
    max_suggestions: int = 3,
) -> list[str]:
    """Recommend up to `max_suggestions` categories ranked by relevance."""
    categories = get_existing_categories(home)
    if not categories:
        return []

    text = f"{title} {body}"
    scored = [(cat, compute_overlap_score(text, cat)) for cat in categories]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [cat for cat, score in scored if score > 0][:max_suggestions]
