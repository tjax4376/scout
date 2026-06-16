"""Graph review backend — Scout REST via ScoutTraceClient."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scout.hawkeye.trace.client import ScoutTraceClient
from scout.hawkeye.trace.store import TraceStore


class GraphReviewBackend:
    """Wrap ScoutTraceClient as a ReviewBackend."""

    name = "graph"

    def __init__(self, client: ScoutTraceClient, *, repo_root: Path) -> None:
        self._client = client
        self.repo_root = repo_root.resolve()

    @property
    def stale(self) -> bool:
        return self._client.stale

    def list_symbols(self, path_prefix: str = "") -> list[dict[str, Any]]:
        return self._client.list_symbols(path_prefix)

    def neighbors(self, node_id: str, *, depth: int = 2, max_nodes: int = 50) -> list[dict[str, Any]]:
        return self._client.neighbors(node_id, depth=depth, max_nodes=max_nodes)

    def read_file(
        self,
        rel_path: str,
        *,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        return self._client.read_file(rel_path, start_line=start_line, end_line=end_line)


def graph_backend(
    *,
    scout_api: str,
    space: str,
    session_id: str,
    trace: TraceStore,
    repo_root: Path,
    token: str = "",
) -> GraphReviewBackend:
    client = ScoutTraceClient(scout_api, space, session_id, trace, token=token)
    return GraphReviewBackend(client, repo_root=repo_root)
