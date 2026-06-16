"""In-memory graph snapshot cache for embed serve mode.

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import scout_core

from scout.api.path_safety import rel_path_matches_prefix
from scout.config import ScoutConfig, graph_bin_path

ALLOWED_EDGES = {"contains", "imports", "calls"}


class GraphCache:
    """Per-space graph snapshots loaded once at embed serve startup."""

    def __init__(self, home: Path, config: ScoutConfig) -> None:
        self._home = home
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._nodes_by_id: dict[str, dict[str, dict[str, Any]]] = {}
        self._outgoing: dict[str, dict[str, list[tuple[str, str]]]] = {}
        for space in config.spaces:
            self._load_space(space)

    def _load_space(self, space: str) -> None:
        path = graph_bin_path(self._home, space)
        if not path.exists():
            self._snapshots[space] = {"nodes": [], "edges": [], "index_version": ""}
            self._nodes_by_id[space] = {}
            self._outgoing[space] = {}
            return
        raw = scout_core.py_load_graph(str(path))
        snapshot = json.loads(raw)
        self._snapshots[space] = snapshot
        nodes_by_id = {n["node_id"]: n for n in snapshot.get("nodes", [])}
        self._nodes_by_id[space] = nodes_by_id
        outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for edge in snapshot.get("edges", []):
            kind = str(edge.get("kind", ""))
            if kind not in ALLOWED_EDGES:
                continue
            outgoing[edge["from_id"]].append((edge["to_id"], kind))
        self._outgoing[space] = dict(outgoing)

    def list_symbols(
        self,
        space: str,
        path_prefix: str,
        kinds: list[str] | None,
    ) -> dict[str, Any]:
        nodes = self._snapshots.get(space, {}).get("nodes", [])
        kind_set = set(kinds or [])
        symbols = []
        for node in nodes:
            rel_path = node.get("rel_path") or ""
            if not rel_path_matches_prefix(rel_path, path_prefix):
                continue
            kind = str(node.get("kind", ""))
            if kind_set and kind not in kind_set:
                continue
            symbols.append(
                {
                    "node_id": node["node_id"],
                    "kind": kind,
                    "symbol": node.get("symbol"),
                    "rel_path": rel_path,
                    "location_ref": node.get("location_ref") or "",
                    "start_line": node.get("start_line") or 0,
                    "end_line": node.get("end_line") or 0,
                }
            )
        return {"symbols": symbols}

    def expand_neighbors(
        self,
        space: str,
        node_id: str,
        depth: int,
        max_nodes: int,
    ) -> dict[str, Any]:
        nodes_by_id = self._nodes_by_id.get(space, {})
        if node_id not in nodes_by_id:
            raise KeyError(node_id)
        depth = max(1, min(depth, 5))
        max_nodes = max(1, min(max_nodes, 100))
        outgoing = self._outgoing.get(space, {})
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        seen = {node_id}
        neighbors: list[dict[str, Any]] = []

        while queue and len(neighbors) < max_nodes:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for target_id, edge_kind in outgoing.get(current, []):
                if target_id in seen:
                    continue
                seen.add(target_id)
                node = nodes_by_id.get(target_id)
                if not node:
                    continue
                neighbor_depth = current_depth + 1
                neighbors.append(
                    {
                        "node_id": target_id,
                        "kind": str(node.get("kind", "")),
                        "symbol": node.get("symbol"),
                        "rel_path": node.get("rel_path") or "",
                        "location_ref": node.get("location_ref") or "",
                        "edge": edge_kind,
                        "depth": neighbor_depth,
                    }
                )
                if len(neighbors) >= max_nodes:
                    break
                queue.append((target_id, neighbor_depth))

        return {"node_id": node_id, "neighbors": neighbors}

    def nodes_for_file(self, space: str, rel_path: str) -> list[dict]:
        return [
            n
            for n in self._snapshots.get(space, {}).get("nodes", [])
            if n.get("rel_path") == rel_path
        ]
