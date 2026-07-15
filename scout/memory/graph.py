"""Graph integration for memory nodes (bincode via scout_core).

Metadata: v0.2.0 | Scout Contributors | 2026-07-14
Change rationale: global-memories-graph-index — py_load/save, Memory kind,
outbound mem→target contains edges, relink after reindex.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import scout_core

from scout.config import graph_bin_path
from scout.memory.storage import _memory_root, _parse_memory_file, memory_rel_path

logger = logging.getLogger("scout.memory.graph")

REFERENCABLE_KINDS = {"file", "module", "directory", "class", "function", "method"}


def _load_graph_snapshot(path: Path) -> dict[str, Any]:
    """Load graph.bin via scout_core bincode → JSON snapshot dict."""
    raw = scout_core.py_load_graph(str(path))
    return json.loads(raw)


def _save_graph_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    """Save graph snapshot via scout_core (bincode)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    scout_core.py_save_graph(str(path), json.dumps(snapshot))


def _find_node_ids_by_path(
    snapshot: dict[str, Any], rel_path: str
) -> list[str]:
    """Find node IDs whose rel_path matches the given path."""
    return [
        n["node_id"]
        for n in snapshot.get("nodes", [])
        if n.get("rel_path") == rel_path and n.get("kind") in REFERENCABLE_KINDS
    ]


def link_memory_into_graph(
    home: Path,
    space: str,
    memory_id: str,
    title: str,
    rel_path: str,
    body: str,
) -> dict[str, Any] | None:
    """Add mem-* node and outbound contains edges into space graph.bin.

    Returns summary dict, or None if graph.bin missing (non-fatal skip).
    """
    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        logger.info("graph.bin not found for space %s, skipping memory link", space)
        return None

    snapshot = _load_graph_snapshot(graph_path)
    node_id = f"mem-{memory_id}"
    node = {
        "node_id": node_id,
        "kind": "memory",
        "symbol": title,
        "rel_path": rel_path,
        "start_line": 0,
        "end_line": 0,
        "location_ref": "",
    }

    existing_ids = {n["node_id"] for n in snapshot.get("nodes", [])}
    if node_id not in existing_ids:
        snapshot.setdefault("nodes", []).append(node)
    else:
        # Refresh title/path on existing memory node
        for n in snapshot["nodes"]:
            if n["node_id"] == node_id:
                n["symbol"] = title
                n["rel_path"] = rel_path
                n["kind"] = "memory"
                break

    paths = _extract_file_paths(body)
    edges_added: list[dict[str, Any]] = []
    existing_edges = {
        (e["from_id"], e["to_id"], e["kind"]) for e in snapshot.get("edges", [])
    }

    for file_path in paths:
        for to_id in _find_node_ids_by_path(snapshot, file_path):
            edge = {
                "from_id": node_id,
                "to_id": to_id,
                "kind": "contains",
            }
            key = (edge["from_id"], edge["to_id"], edge["kind"])
            if key not in existing_edges:
                snapshot.setdefault("edges", []).append(edge)
                existing_edges.add(key)
                edges_added.append(edge)

    _save_graph_snapshot(graph_path, snapshot)
    return {"node": node, "edges": edges_added}


def add_memory_node(
    home: Path,
    space: str,
    memory_id: str,
    title: str,
    rel_path: str,
) -> dict[str, Any] | None:
    """Add a memory node only (no body path edges). Prefers link_memory_into_graph."""
    return link_memory_into_graph(home, space, memory_id, title, rel_path, body="")


def link_memory_edges(
    home: Path,
    space: str,
    memory_id: str,
    body: str,
) -> list[dict[str, Any]]:
    """Create outbound contains edges from memory to cited file nodes."""
    # Need title/rel_path from existing node or defaults
    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        return []
    title = memory_id
    rel_path = memory_rel_path(memory_id)
    snapshot = _load_graph_snapshot(graph_path)
    node_id = f"mem-{memory_id}"
    for n in snapshot.get("nodes", []):
        if n.get("node_id") == node_id:
            title = n.get("symbol") or title
            rel_path = n.get("rel_path") or rel_path
            break
    result = link_memory_into_graph(home, space, memory_id, title, rel_path, body)
    if result is None:
        return []
    return list(result.get("edges") or [])


def relink_all_memories(home: Path, space: str) -> int:
    """Re-apply all global memories into a space graph after reindex.

    Returns number of memories successfully linked (including zero-edge links).
    """
    mem_dir = _memory_root(home)
    if not mem_dir.exists():
        return 0
    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        return 0

    linked = 0
    for md_file in sorted(mem_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            frontmatter, body = _parse_memory_file(content)
            memory_id = frontmatter.get("id")
            if not memory_id:
                continue
            title = frontmatter.get("title") or memory_id
            rel_path = memory_rel_path(memory_id)
            result = link_memory_into_graph(
                home, space, memory_id, title, rel_path, body
            )
            if result is not None:
                linked += 1
        except Exception:
            logger.warning("relink failed for %s", md_file.name, exc_info=True)
    return linked


def _extract_file_paths(body: str) -> list[str]:
    """Extract file paths from memory body text."""
    if not body:
        return []
    pattern = (
        r"(?:^|[\s`(\"'=])"
        r"((?:scout/|src/|lib/|tests/|app/|pkg/)[\w./-]+\.(?:py|ts|js|rs|md))"
    )
    return list(dict.fromkeys(m.group(1) for m in re.finditer(pattern, body, re.M)))
