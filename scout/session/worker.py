"""Background session embed worker (daemon thread).

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
Change rationale: embed only files read via GET /file during serve --embed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import defaultdict
from pathlib import Path

import scout_core

from scout.config import ScoutConfig, get_embed_api_key, load_secrets, validate_embed, validate_space
from scout.embed.compress import prepare_chunks_for_embed
from scout.embed.registry import build_provider
from scout.indexing import DEFAULT_EMBED_BATCH, embed_texts_batched
from scout.session.chunks import build_file_chunks
from scout.session.file_cache import FileCache
from scout.session.graph_cache import GraphCache
from scout.session.queue import EmbedJob, EmbedQueue
from scout.session.store import SessionIndexStore

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_BACKOFF_SEC = 2.0


class SessionEmbedWorker:
    """Single consumer; retries failed embeds with exponential backoff."""

    def __init__(
        self,
        home: Path,
        config: ScoutConfig,
        queue: EmbedQueue,
        graph_cache: GraphCache,
        file_caches: dict[str, FileCache],
    ) -> None:
        self._home = home
        self._config = config
        self._queue = queue
        self._graph_cache = graph_cache
        self._file_caches = file_caches
        self._stores: dict[str, SessionIndexStore] = {}
        self._stop = threading.Event()
        self._running = False
        self._thread: threading.Thread | None = None
        self._embedded_files: dict[str, set[str]] = defaultdict(set)
        self._retry_counts: dict[tuple[str, str], int] = defaultdict(int)
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def embedded_file_count(self, space: str) -> int:
        return len(self._embedded_files.get(space, set()))

    def clear_space(self, space: str) -> None:
        self._embedded_files[space].clear()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, name="session-embed", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.stop()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _store_for(self, space: str) -> SessionIndexStore:
        if space not in self._stores:
            self._stores[space] = SessionIndexStore(self._home, space, self._config)
        return self._stores[space]

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        while not self._stop.is_set():
            job = self._queue.get(timeout=0.5)
            if job is None:
                continue
            try:
                self._loop.run_until_complete(self._process(job))
            except Exception as exc:  # noqa: BLE001 — worker must survive per-job failures
                logger.exception("session embed failed for %s/%s: %s", job.space, job.rel_path, exc)
                self._schedule_retry(job, str(exc))

    async def _process(self, job: EmbedJob) -> None:
        embed = validate_embed(self._config)
        entry = validate_space(self._home, job.space)
        root = Path(entry.root)
        source: str | None = None
        cache = self._file_caches.get(job.space)
        if cache is not None:
            source = cache.get(root, job.rel_path)
        if source is None:
            raw = scout_core.py_read_workspace_file(str(root), job.rel_path, None, None)
            payload = json.loads(raw)
            source = payload["text"]
            if cache is not None:
                mtime = int((root / job.rel_path).stat().st_mtime)
                cache.put(job.rel_path, source, mtime)
        nodes = self._graph_cache.nodes_for_file(job.space, job.rel_path)
        chunks = build_file_chunks(
            job.rel_path,
            source,
            nodes,
            start_line=job.start_line,
            end_line=job.end_line,
        )
        if not chunks:
            logger.warning("no chunks for %s/%s; skipping embed", job.space, job.rel_path)
            self._embedded_files[job.space].add(job.rel_path)
            return

        secrets = load_secrets(self._home)
        provider = build_provider(
            embed.provider,
            api_key=get_embed_api_key(secrets, embed.provider),
            endpoint=embed.endpoint or None,
        )
        prepare_chunks_for_embed(chunks, embed)
        texts = [c["text"] for c in chunks]
        batch_size = embed.embed_batch_size if embed.embed_batch_size > 0 else DEFAULT_EMBED_BATCH
        vectors = await embed_texts_batched(
            provider, embed.model, texts, batch_size=batch_size
        )
        self._store_for(job.space).append(chunks, vectors)
        self._embedded_files[job.space].add(job.rel_path)
        self._retry_counts.pop((job.space, job.rel_path), None)
        logger.info(
            "session embedded %s/%s (%d chunks)",
            job.space,
            job.rel_path,
            len(chunks),
        )

    def _schedule_retry(self, job: EmbedJob, reason: str) -> None:
        key = (job.space, job.rel_path)
        attempt = self._retry_counts[key] + 1
        if attempt > MAX_RETRIES:
            logger.error(
                "session embed dropped after %d retries for %s/%s: %s",
                MAX_RETRIES,
                job.space,
                job.rel_path,
                reason,
            )
            self._embedded_files[job.space].add(job.rel_path)
            return
        self._retry_counts[key] = attempt
        self._queue.release_for_retry(job)
        delay = BASE_BACKOFF_SEC * (2 ** (attempt - 1))

        def _reenqueue() -> None:
            if self._stop.is_set():
                return
            if not self._queue.enqueue(job):
                return
            logger.warning(
                "retry session embed %s/%s attempt %d in %.1fs",
                job.space,
                job.rel_path,
                attempt,
                delay,
            )

        timer = threading.Timer(delay, _reenqueue)
        timer.daemon = True
        timer.start()
