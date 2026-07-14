"""Graph integration for memory nodes.

Metadata: v0.1.0 | Scout Contributors | 2026-07-13
Change rationale: add-memory-api — link memories into the scout graph.

Note: Uses direct JSON modification of graph.bin (no Rust changes needed).
# ponytail: graph.bin lock is file-level via fcntl; per-account locks if throughput matters
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from scout.config import graph_bin_path

logger = logging.getLogger("scout.memory.graph")

# Node kinds that can be referenced by file path
REFERENCABLE_KINDS = {"file", "module", "directory", "class", "function", "method"}


def _load_graph_snapshot(path: Path) -> dict[str, Any]:
    """Load graph.bin as a JSON dict."""
    if not path.exists():
        return {"nodes": [], "edges": [], "index_version": ""}
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


def _save_graph_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    """Save graph.bin as formatted JSON."""
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def _find_node_ids_by_path(
    snapshot: dict[str, Any], rel_path: str
) -> list[str]:
    """Find node IDs whose rel_path matches the given path."""
    return [
        n["node_id"]
        for n in snapshot.get("nodes", [])
        if n.get("rel_path") == rel_path and n.get("kind") in REFERENCABLE_KINDS
    ]


def add_memory_node(
    home: Path,
    space: str,
    memory_id: str,
    title: str,
    rel_path: str,
) -> dict[str, Any] | None:
    """Add a memory node to the graph index.

    Returns the created node dict, or None if graph.bin doesn't exist.
    """
    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        logger.info("graph.bin not found for space %s, skipping memory node", space)
        return None

    snapshot = _load_graph_snapshot(graph_path)

    # Create the memory node
    node = {
        "node_id": f"mem-{memory_id}",
        "kind": "memory",
        "symbol": title,
        "rel_path": rel_path,
        "start_line": 0,
        "end_line": 0,
        "location_ref": "",
    }

    # Avoid duplicates
    existing_ids = {n["node_id"] for n in snapshot.get("nodes", [])}
    if node["node_id"] in existing_ids:
        return node

    snapshot.setdefault("nodes", []).append(node)
    _save_graph_snapshot(graph_path, snapshot)
    return node


def link_memory_edges(
    home: Path,
    space: str,
    memory_id: str,
    body: str,
) -> list[dict[str, Any]]:
    """Create `contains` edges from referenced file nodes to the memory node.

    Scans the memory body for file paths and creates edges from matching
    graph nodes to the memory node.

    Returns list of created edges.
    """
    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        return []

    snapshot = _load_graph_snapshot(graph_path)

    # Extract file paths from body (look for patterns like scout/api/app.py)
    paths = _extract_file_paths(body)
    edges: list[dict[str, Any]] = []

    for file_path in paths:
        node_ids = _find_node_ids_by_path(snapshot, file_path)
        for from_id in node_ids:
            edge = {
                "from_id": from_id,
                "to_id": f"mem-{memory_id}",
                "kind": "contains",
            }
            # Avoid duplicate edges
            existing_edges = {
                (e["from_id"], e["to_id"], e["kind"])
                for e in snapshot.get("edges", [])
            }
            if (edge["from_id"], edge["to_id"], edge["kind"]) not in existing_edges:
                snapshot.setdefault("edges", []).append(edge)
                edges.append(edge)

    if edges:
        _save_graph_snapshot(graph_path, snapshot)

    return edges


def _extract_file_paths(body: str) -> list[str]:
    """Extract file paths from memory body text.

    Looks for patterns like: scout/api/app.py, src/utils.py, etc.
    """
    # Match paths starting with a directory component and ending in .py/.ts/.js/.rs/.md
    pattern = r"(?:^|\n)\s*(?:scout/|src/|lib/|tests/|app/|pkg/)[\w./-]+\.(?:py|ts|js|rs|md)"
    matches = re.findall(pattern, body)
    return [m.strip() for m in matches]
