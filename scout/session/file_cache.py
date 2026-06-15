"""In-memory workspace source cache for embed serve mode.

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
Change rationale: bulk-read gitignore-filtered files at serve --embed warm.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import scout_core

from scout.config import SpaceEntry, space_scan_kwargs

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 512 * 1024


@dataclass
class CacheStats:
    file_count: int
    bytes: int
    warm_seconds: float


class FileCache:
    """Per-space RAM cache of full file text keyed by rel_path + mtime."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[str, int]] = {}
        self._warm_seconds: float = 0.0

    def warm(self, entry: SpaceEntry) -> None:
        """Bulk-read all scan-eligible files under space root."""
        if scout_core is None:
            raise RuntimeError("scout_core not built; run maturin develop")

        started = time.monotonic()
        files = scout_core.py_scan_workspace(str(entry.root), **space_scan_kwargs(entry))
        files_json = json.dumps(
            [
                {
                    "rel_path": f.rel_path,
                    "size": f.size,
                    "mtime_secs": f.mtime_secs,
                    "language": f.language,
                    "is_binary": False,
                }
                for f in files
            ]
        )
        raw = scout_core.py_bulk_read_workspace_files(str(entry.root), files_json)
        for item in json.loads(raw):
            self._entries[item["rel_path"]] = (item["text"], int(item["mtime_secs"]))
        self._warm_seconds = time.monotonic() - started
        logger.info(
            "file cache warm for %s: %d files in %.2fs",
            entry.name,
            len(self._entries),
            self._warm_seconds,
        )

    def stats(self) -> CacheStats:
        total_bytes = sum(len(text.encode("utf-8")) for text, _ in self._entries.values())
        return CacheStats(
            file_count=len(self._entries),
            bytes=total_bytes,
            warm_seconds=self._warm_seconds,
        )

    def get(self, root: Path, rel_path: str) -> str | None:
        """Return cached full file text when mtime still matches disk."""
        cached = self._entries.get(rel_path)
        if cached is None:
            return None
        text, cached_mtime = cached
        current_mtime = _file_mtime(root, rel_path)
        if current_mtime is None or current_mtime != cached_mtime:
            self._entries.pop(rel_path, None)
            return None
        return text

    def put(self, rel_path: str, text: str, mtime_secs: int) -> None:
        self._entries[rel_path] = (text, mtime_secs)

    def read_response(
        self,
        root: Path,
        rel_path: str,
        start_line: int | None,
        end_line: int | None,
    ) -> dict[str, object] | None:
        """Build GET /file response from cache when entry is fresh."""
        full_text = self.get(root, rel_path)
        if full_text is None:
            return None
        return _slice_file_text(full_text, rel_path, start_line, end_line)


def _file_mtime(root: Path, rel_path: str) -> int | None:
    path = root / rel_path
    if not path.is_file():
        return None
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return None


def _slice_file_text(
    text: str,
    rel_path: str,
    start_line: int | None,
    end_line: int | None,
) -> dict[str, object]:
    lines = text.splitlines(keepends=True)
    total_lines = max(1, len(lines)) if lines else 1
    start = max(1, start_line or 1)
    end = min(end_line or total_lines, total_lines)
    if start > end:
        raise ValueError(f"start_line {start} > end_line {end}")
    if not lines:
        slice_text = text if start <= 1 else ""
    else:
        slice_text = "".join(lines[start - 1 : end])
    if len(slice_text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(
            f"response exceeds {MAX_FILE_BYTES} bytes; narrow line range"
        )
    return {
        "rel_path": rel_path,
        "start_line": start,
        "end_line": end,
        "text": slice_text,
        "total_lines": total_lines,
    }
