"""Filesystem review backend — local disk reads, no Scout REST."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scout.hawkeye.trace.store import TraceStore, content_hash


class FilesystemReviewBackend:
    """Read files from repo_root; no symbol/neighbor graph."""

    name = "filesystem"

    def __init__(self, *, repo_root: Path, trace: TraceStore | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self._trace = trace
        self.stale = False

    def _resolve_path(self, rel_path: str) -> Path:
        candidate = Path(rel_path)
        if candidate.is_absolute():
            path = candidate.resolve()
        else:
            path = (self.repo_root / rel_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"file not found: {rel_path}")
        try:
            path.relative_to(self.repo_root)
        except ValueError as exc:
            raise FileNotFoundError(f"file outside repo root: {rel_path}") from exc
        return path

    def list_symbols(self, path_prefix: str = "") -> list[dict[str, Any]]:
        return []

    def neighbors(self, node_id: str, *, depth: int = 2, max_nodes: int = 50) -> list[dict[str, Any]]:
        return []

    def read_file(
        self,
        rel_path: str,
        *,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        path = self._resolve_path(rel_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if start_line is not None or end_line is not None:
            lines = text.splitlines()
            start = max(1, int(start_line or 1))
            end = int(end_line or len(lines) or start)
            text = "\n".join(lines[start - 1 : end])
            if text:
                text += "\n"
        if self._trace is not None:
            self._trace.log_step(
                "file_read",
                rel_path=rel_path,
                start_line=start_line,
                end_line=end_line,
                content_hash=content_hash(text),
                source="filesystem",
            )
        return text
