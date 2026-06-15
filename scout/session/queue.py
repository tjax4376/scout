"""Embed job queue with dedupe by (space, rel_path).

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbedJob:
    space: str
    rel_path: str
    start_line: int | None = None
    end_line: int | None = None


class EmbedQueue:
    """Thread-safe queue; at most one pending/completed job per (space, rel_path)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: queue.Queue[EmbedJob | None] = queue.Queue()
        self._tracked: set[tuple[str, str]] = set()

    def enqueue(self, job: EmbedJob) -> bool:
        key = (job.space, job.rel_path)
        with self._lock:
            if key in self._tracked:
                return False
            self._tracked.add(key)
        self._queue.put(job)
        return True

    def get(self, timeout: float | None = None) -> EmbedJob | None:
        try:
            item = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        if item is None:
            return None
        return item

    def release_for_retry(self, job: EmbedJob) -> None:
        """Allow re-enqueue after a failed embed attempt."""
        with self._lock:
            self._tracked.discard((job.space, job.rel_path))

    def depth(self) -> int:
        return self._queue.qsize()

    def stop(self) -> None:
        self._queue.put(None)
