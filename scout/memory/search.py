"""Ask memory — search global memories by natural language query.

Metadata: v0.2.0 | Scout Contributors | 2026-07-14
Change rationale: global-memories-graph-index — search global store.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scout.memory.storage import _memory_root, _parse_memory_file, memory_rel_path

logger = logging.getLogger("scout.memory.search")


@dataclass
class MemoryHit:
    """A single memory match with its relevance score."""

    memory: dict[str, Any]
    score: float


def ask_memories(
    home: Path,
    query: str,
    *,
    top_k: int = 10,
    embed_fn: Any = None,
) -> list[dict[str, Any]]:
    """Search global memories by query and return the most relevant ones."""
    mem_dir = _memory_root(home)
    if not mem_dir.exists():
        return []

    query_lower = query.lower().strip()
    query_terms = _tokenize(query_lower)

    all_memories: list[dict[str, Any]] = []
    for md_file in sorted(mem_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            frontmatter, body = _parse_memory_file(content)
            if not frontmatter.get("id"):
                continue
            mid = frontmatter["id"]
            all_memories.append(
                {
                    "id": mid,
                    "title": frontmatter.get("title", ""),
                    "body": body,
                    "category": frontmatter.get("category", ""),
                    "tags": frontmatter.get("tags", []),
                    "created_at": frontmatter.get("created_at", ""),
                    "rel_path": memory_rel_path(mid),
                }
            )
        except Exception:
            logger.warning("failed to parse memory %s", md_file.name, exc_info=True)

    if not all_memories:
        return []

    scored: list[MemoryHit] = []
    for mem in all_memories:
        score = _score_memory(mem, query, query_terms, embed_fn)
        if score > 0:
            scored.append(MemoryHit(memory=mem, score=score))

    scored.sort(key=lambda h: h.score, reverse=True)
    return [h.memory for h in scored[:top_k]]


def _tokenize(text: str) -> set[str]:
    """Tokenize text into words, filtering short tokens."""
    words = re.findall(r"[a-z0-9]+", text)
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need",
        "dare", "ought", "used", "to", "of", "in", "for", "on",
        "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "out", "off",
        "over", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "each", "few",
        "more", "most", "other", "some", "such", "no", "nor", "not",
        "only", "own", "same", "so", "than", "too", "very", "just",
        "because", "but", "and", "or", "if", "while", "about",
    }
    return {w for w in words if len(w) >= 2 and w not in stop_words}


def _score_memory(
    mem: dict[str, Any],
    query: str,
    query_terms: set[str],
    embed_fn: Any = None,
) -> float:
    """Score a memory against the query."""
    title_lower = mem.get("title", "").lower()
    body_lower = mem.get("body", "").lower()
    combined = f"{title_lower} {body_lower}"

    score = 0.0
    query_clean = query.strip().lower()
    if query_clean in combined:
        score += 10.0

    for term in query_terms:
        if term in title_lower:
            score += 5.0
        if term in body_lower:
            score += 1.0

    category = mem.get("category", "").lower()
    for term in query_terms:
        if term in category:
            score += 3.0

    if embed_fn is not None:
        try:
            query_vec = embed_fn(query)
            body_vec = embed_fn(mem.get("body", ""))
            if query_vec and body_vec:
                vec_score = _cosine_similarity(query_vec, body_vec)
                score += vec_score * 8.0
        except Exception:
            logger.warning("vector embedding failed, falling back to text", exc_info=True)

    return score


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
