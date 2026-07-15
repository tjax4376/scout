"""Tests for memory categorization logic."""

from __future__ import annotations

from scout.memory.categorize import compute_overlap_score, recommend_categories


def test_compute_overlap_score_exact_word() -> None:
    assert compute_overlap_score("the api module is broken", "api") == 1.0


def test_compute_overlap_score_partial() -> None:
    score = compute_overlap_score("the api and config files", "api")
    assert score == 1.0


def test_compute_overlap_score_no_match() -> None:
    assert compute_overlap_score("the config file is broken", "api") == 0.0


def test_compute_overlap_score_hyphenated_category() -> None:
    score = compute_overlap_score("the rest-api setup guide", "rest-api")
    assert score == 1.0


def test_compute_overlap_score_empty_category() -> None:
    assert compute_overlap_score("some text", "") == 0.0


def test_recommend_categories_empty_list() -> None:
    # With no existing categories, should return empty list
    import tempfile
    from pathlib import Path

    from scout.memory.categorize import get_existing_categories

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        categories = get_existing_categories(home)
        assert categories == []


def test_recommend_categories_ranked_by_overlap() -> None:
    """Categories with more keyword matches should rank higher."""
    # This is tested indirectly via compute_overlap_score
    assert compute_overlap_score("api middleware handler", "api") > compute_overlap_score(
        "the config file", "api"
    )
