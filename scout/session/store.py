"""Session sqlite-vec index store.

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
"""

from __future__ import annotations

import json
from pathlib import Path

import scout_core

from scout.config import ScoutConfig, session_index_path, validate_embed


class SessionIndexStore:
    """Wraps scout_core session index paths; cleared on serve start."""

    def __init__(self, home: Path, space: str, config: ScoutConfig) -> None:
        self.home = home
        self.space = space
        self.config = config
        self.path = session_index_path(home, space)

    def prepare_fresh(self) -> None:
        """Drop and recreate session index for a new serve session."""
        embed = validate_embed(self.config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()
        scout_core.py_session_prepare_index(
            str(self.path),
            embed.model,
            embed.dimensions,
        )

    def append(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        scout_core.py_session_append_chunks(
            str(self.path),
            json.dumps(chunks),
            json.dumps(embeddings),
        )

    def stats(self) -> tuple[int, int]:
        if not self.path.exists():
            return 0, 0
        return scout_core.py_session_index_stats(str(self.path))

    def exists(self) -> bool:
        return self.path.is_file()
