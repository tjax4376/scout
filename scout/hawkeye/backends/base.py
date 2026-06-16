"""Review backend protocol — graph (Scout REST) or filesystem (local disk)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class ReviewBackend(Protocol):
    """Data provider for Hawkeye review playbook."""

    name: str
    stale: bool
    repo_root: Path

    def list_symbols(self, path_prefix: str = "") -> list[dict[str, Any]]:
        ...

    def neighbors(self, node_id: str, *, depth: int = 2, max_nodes: int = 50) -> list[dict[str, Any]]:
        ...

    def read_file(
        self,
        rel_path: str,
        *,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        ...
