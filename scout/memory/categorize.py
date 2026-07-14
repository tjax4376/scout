"""Category recommendation for memories.

Metadata: v0.1.0 | Scout Contributors | 2026-07-13
"""

from __future__ import annotations

import re
from pathlib import Path

from scout.memory.storage import _memory_dir


def get_existing_categories(home: Path, space: str) -> list[str]:
    """Return the set of existing category names from memory files in the space."""
    mem_dir = _memory_dir(home, space)
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
            import yaml

            frontmatter = yaml.safe_load(content[3:fm_end]) or {}
            cat = frontmatter.get("category")
            if cat:
                categories.add(cat)
        except (ValueError, yaml.YAMLError):
            continue

    return sorted(categories)


def compute_overlap_score(text: str, category: str) -> float:
    """Compute a keyword overlap score between text and a category name.

    Uses word-boundary matching: counts how many words from the category
    appear in the text. Normalized by category word count.
    """
    text_lower = text.lower()
    # Split category into words (handle hyphens, underscores)
    category_words = set(re.split(r"[-_\s]+", category.lower()))
    if not category_words or "" in category_words:
        return 0.0

    # Count matching words
    matches = sum(1 for word in category_words if word in text_lower)
    return matches / len(category_words)


def recommend_categories(
    home: Path,
    space: str,
    title: str,
    body: str,
    max_suggestions: int = 3,
) -> list[str]:
    """Recommend up to `max_suggestions` categories ranked by relevance.

    Uses keyword overlap between title+body and existing category names.
    Returns empty list if no categories exist or no overlap found.
    """
    categories = get_existing_categories(home, space)
    if not categories:
        return []

    text = f"{title} {body}"
    scored = [
        (cat, compute_overlap_score(text, cat)) for cat in categories
    ]
    # Sort by score descending, return top N
    scored.sort(key=lambda x: x[1], reverse=True)
    return [cat for cat, score in scored if score > 0][:max_suggestions]
