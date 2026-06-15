"""Aggregate graph symbols and neighbors for a single file.

Metadata: v0.1.1 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import json
from typing import Any

import scout_core

DEFAULT_MAX_NODES = 200
MAX_GRAPH_FILE_NODES = 200


def aggregate_file_graph(
    graph_path: str,
    rel_path: str,
    *,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> dict[str, Any]:
    """Return symbols in *rel_path* plus depth-1 neighbors and connecting edges."""
    if scout_core is None:
        raise RuntimeError("scout_core not built; run maturin develop")

    cap = max(1, min(int(max_nodes), MAX_GRAPH_FILE_NODES))
    raw = scout_core.py_list_symbols(graph_path, rel_path, None)
    payload = json.loads(raw)
    symbols = [
        sym
        for sym in payload.get("symbols", [])
        if str(sym.get("rel_path") or "") == rel_path
        and str(sym.get("kind") or "").lower() not in {"file", "directory"}
    ]

    symbol_ids = {str(sym["node_id"]) for sym in symbols}
    nodes_by_id: dict[str, dict[str, Any]] = {
        str(sym["node_id"]): dict(sym) for sym in symbols
    }
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    truncated = False

    for sym in symbols:
        if len(nodes_by_id) >= cap:
            truncated = True
            break

        node_id = str(sym["node_id"])
        remaining = cap - len(nodes_by_id)
        neighbor_cap = max(1, min(remaining, 50))
        neighbor_raw = scout_core.py_expand_neighbors(
            graph_path,
            node_id,
            1,
            neighbor_cap,
        )
        neighbor_payload = json.loads(neighbor_raw)

        for nb in neighbor_payload.get("neighbors", []):
            nb_id = str(nb.get("node_id") or "")
            if not nb_id:
                continue

            edge_type = str(nb.get("edge") or "")
            edge_key = (node_id, nb_id, edge_type)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append(
                    {
                        "source": node_id,
                        "target": nb_id,
                        "edge": edge_type,
                    }
                )

            if nb_id in nodes_by_id:
                continue
            if len(nodes_by_id) >= cap:
                truncated = True
                break
            nodes_by_id[nb_id] = dict(nb)

        if truncated:
            break

    neighbors = [
        node for node_id, node in nodes_by_id.items() if node_id not in symbol_ids
    ]

    return {
        "rel_path": rel_path,
        "symbols": symbols,
        "neighbors": neighbors,
        "edges": edges,
        "truncated": truncated,
    }
