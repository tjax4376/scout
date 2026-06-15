"""Unit tests for session embed queue."""

from __future__ import annotations

from scout.session.queue import EmbedJob, EmbedQueue


def test_queue_dedupes_by_space_and_path() -> None:
    q = EmbedQueue()
    job = EmbedJob(space="demo", rel_path="src/auth.py")
    assert q.enqueue(job) is True
    assert q.enqueue(job) is False
    assert q.depth() == 1


def test_queue_release_for_retry_allows_reenqueue() -> None:
    q = EmbedQueue()
    job = EmbedJob(space="demo", rel_path="src/main.py")
    assert q.enqueue(job) is True
    q.release_for_retry(job)
    assert q.enqueue(job) is True
