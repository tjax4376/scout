"""Session embed runtime singleton for serve --embed.

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
"""

from __future__ import annotations

import logging
from pathlib import Path

from scout.config import ScoutConfig, validate_embed, validate_space
from scout.prescan.runner import check_capacity, run_prescan
from scout.session.file_cache import FileCache
from scout.session.graph_cache import GraphCache
from scout.session.queue import EmbedJob, EmbedQueue
from scout.session.store import SessionIndexStore
from scout.session.worker import SessionEmbedWorker

logger = logging.getLogger(__name__)


class SessionRuntime:
    """Owns queue, worker, graph cache, and per-space session indexes."""

    def __init__(self, home: Path, config: ScoutConfig) -> None:
        self.home = home
        self.config = config
        self.queue = EmbedQueue()
        self.graph_cache = GraphCache(home, config)
        self._file_caches: dict[str, FileCache] = {}
        self.worker = SessionEmbedWorker(
            home, config, self.queue, self.graph_cache, self._file_caches
        )
        self._embed_ready = False
        self._stores: dict[str, SessionIndexStore] = {}

    @property
    def embed_ready(self) -> bool:
        return self._embed_ready

    def start(self, *, warm_cache: bool = True) -> None:
        try:
            validate_embed(self.config)
        except ValueError as exc:
            logger.warning("embed mode without valid embed config: %s", exc)
            self._embed_ready = False
            return

        if warm_cache:
            for space_name in self.config.spaces:
                entry = validate_space(self.home, space_name)
                prescan = run_prescan(
                    Path(entry.root),
                    entry.skip_globs,
                    entry.skip_paths,
                    respect_gitignore=entry.respect_gitignore,
                    include_file_cache=True,
                )
                check_capacity(prescan)
                cache = FileCache()
                cache.warm(entry)
                self._file_caches[space_name] = cache
                logger.info(
                    "file cache ready for %s (%d files)",
                    space_name,
                    cache.stats().file_count,
                )

        for space in self.config.spaces:
            store = SessionIndexStore(self.home, space, self.config)
            store.prepare_fresh()
            self._stores[space] = store
            logger.info("session index prepared for space %s", space)

        self._embed_ready = True
        self.worker.start()

    def shutdown(self) -> None:
        self.worker.stop()

    def enqueue_file_read(
        self,
        space: str,
        rel_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> bool:
        if not self._embed_ready:
            return False
        return self.queue.enqueue(
            EmbedJob(
                space=space,
                rel_path=rel_path,
                start_line=start_line,
                end_line=end_line,
            )
        )

    def store_for(self, space: str) -> SessionIndexStore | None:
        return self._stores.get(space)

    def status(self, space: str) -> dict:
        store = self._stores.get(space)
        chunk_count, file_count = store.stats() if store else (0, 0)
        cache = self._file_caches.get(space)
        cache_stats = cache.stats() if cache else None
        return {
            "space": space,
            "embed_ready": self._embed_ready,
            "worker_running": self.worker.running,
            "queue_depth": self.queue.depth(),
            "embedded_file_count": self.worker.embedded_file_count(space),
            "indexed_file_count": file_count,
            "chunk_count": chunk_count,
            "cache_file_count": cache_stats.file_count if cache_stats else 0,
            "cache_bytes": cache_stats.bytes if cache_stats else 0,
            "cache_warm_seconds": cache_stats.warm_seconds if cache_stats else 0.0,
        }

    def file_cache(self, space: str) -> FileCache | None:
        return self._file_caches.get(space)

    def clear_index(self, space: str) -> None:
        if space not in self.config.spaces:
            raise ValueError(f"unknown space: {space}")
        if not self._embed_ready:
            raise RuntimeError("embed mode not ready")
        store = SessionIndexStore(self.home, space, self.config)
        store.prepare_fresh()
        self._stores[space] = store
        self.worker.clear_space(space)
