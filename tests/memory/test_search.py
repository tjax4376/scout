"""Tests for memory search (ask_memories)."""

from __future__ import annotations

from pathlib import Path

from scout.memory.search import ask_memories
from scout.memory.storage import create_memory_file


def test_ask_memories_returns_relevant_results(tmp_path: Path) -> None:
    create_memory_file(
        tmp_path,
        "Auth Middleware Pattern",
        "Use FastAPI middleware for authentication checks. "
        "The middleware validates Bearer tokens and injects the user context.",
        "api-patterns",
        ["auth", "middleware"],
    )
    create_memory_file(
        tmp_path,
        "Database Configuration",
        "PostgreSQL connection uses asyncpg with connection pooling. "
        "Configure via environment variables.",
        "config",
        ["database", "postgresql"],
    )

    results = ask_memories(tmp_path, "authentication middleware")
    assert len(results) >= 1
    assert results[0]["title"] == "Auth Middleware Pattern"


def test_ask_memories_title_match(tmp_path: Path) -> None:
    create_memory_file(
        tmp_path,
        "API Rate Limiting",
        "Different content that does not mention rate limiting.",
        "api-patterns",
        ["api"],
    )

    results = ask_memories(tmp_path, "rate limiting")
    assert len(results) >= 1
    assert results[0]["title"] == "API Rate Limiting"


def test_ask_memories_no_results(tmp_path: Path) -> None:
    results = ask_memories(tmp_path, "nonexistent topic xyz123")
    assert results == []


def test_ask_memories_empty_space(tmp_path: Path) -> None:
    results = ask_memories(tmp_path, "any query")
    assert results == []


def test_ask_memories_body_match(tmp_path: Path) -> None:
    create_memory_file(
        tmp_path,
        "Generic Title",
        "This memory body discusses vector embeddings and similarity search "
        "for semantic matching of text documents.",
        "ml",
        ["embeddings"],
    )

    results = ask_memories(tmp_path, "semantic similarity search")
    assert len(results) >= 1
    assert results[0]["title"] == "Generic Title"


def test_ask_memories_limits_to_top_k(tmp_path: Path) -> None:
    for i in range(5):
        create_memory_file(
            tmp_path,
            f"Memory {i}",
            f"This is memory number {i} about a topic.",
            "general",
            [],
        )

    results = ask_memories(tmp_path, "memory", top_k=3)
    assert len(results) <= 3


def test_ask_memories_ranking_relevance(tmp_path: Path) -> None:
    # High relevance: matches both title and body
    create_memory_file(
        tmp_path,
        "User Authentication",
        "How to implement user authentication with JWT tokens.",
        "security",
        ["auth"],
    )
    # Low relevance: only mentions auth in body, not title
    create_memory_file(
        tmp_path,
        "Project Structure",
        "The project has a separate user authentication module.",
        "architecture",
        [],
    )

    results = ask_memories(tmp_path, "user authentication")
    assert len(results) >= 2
    # Higher relevance should rank first
    assert results[0]["title"] == "User Authentication"


def test_ask_memories_with_embed_fn(tmp_path: Path) -> None:
    """Test that embed_fn is accepted (doesn't need to actually work for text test)."""
    create_memory_file(
        tmp_path,
        "Embed Test",
        "Content for embedding test.",
        "test",
        [],
    )

    # Pass a dummy embed_fn — text search should still work
    results = ask_memories(
        tmp_path, "embed test", embed_fn=lambda x: [0.1, 0.2]
    )
    assert len(results) >= 1
